"""General assistant on native Agent Server resources and checkpoints."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime
from pydantic import SecretStr

from .conversation_agent import build_conversation_agent
from .conversation_tools import conversation_tools
from .deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
from .dell_case_review_agent import CaseModelAudit, case_chat_model
from .dell_report_session import session_audit_sinks


@asynccontextmanager
async def conversation_session_graph(config: RunnableConfig, runtime: ServerRuntime):
    if runtime.execution_runtime is None:
        yield build_conversation_agent(model=FakeMessagesListChatModel(responses=[]), grants=[],
                                       permission_mode="request_standard", checkpointer=None)
        return
    from .dell_agent_server_entry import _require_langsmith_execution_environment
    _require_langsmith_execution_environment(config)
    if os.environ.get("FINSIGHT_RESEARCH_SESSION_ENABLED") != "1":
        raise ValueError("conversation_execution_not_enabled")
    ids = config["configurable"]
    thread_id, run_id = str(UUID(str(ids["thread_id"]))), str(UUID(str(ids["run_id"])))
    root = Path(os.environ["FIN_REPO_ROOT"])
    settings = json.loads(Path(os.environ["FINSIGHT_REPORT_SESSION_SETTINGS"]).read_text(encoding="utf-8"))
    specification = json.loads((root / "configs/research/runtime/conversation.json").read_text(encoding="utf-8"))
    profile = DeepSeekModelProfile.model_validate({**specification["profile"],
        **({"model": ids["conversation_model"]} if ids.get("conversation_model") else {})})
    basis = TokenBudgetBasis.model_validate_json(json.dumps(specification["budget"]))
    public, private = session_audit_sinks(Path(settings["audit_root"]) / thread_id / run_id)
    from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
    store = TaskAttachmentStore(Path(os.environ["FINSIGHT_TASK_ATTACHMENTS_ROOT"])) if os.environ.get("FINSIGHT_TASK_ATTACHMENTS_ROOT") else None
    grants = conversation_tools(thread_id=thread_id, attachment_store=store,
        fact_mart=Path(settings["conversation_fact_mart"]) if settings.get("conversation_fact_mart") else None)
    if store is not None:
        from hashlib import sha256
        from .conversation_web import public_web_tool
        grants.append(public_web_tool(thread_id=thread_id,run_id=run_id,
            method_digest=sha256((root / "configs/research/runtime/conversation.json").read_bytes()).hexdigest(),
            cache_root=Path(os.environ["FINSIGHT_TASK_ATTACHMENTS_ROOT"]) / "public-source-cache"))
    if settings.get("conversation_sandbox_url"):
        from .sandbox_mcp import remote_sandbox_tool
        grants.append(remote_sandbox_tool(endpoint=settings["conversation_sandbox_url"],
            token=settings["conversation_sandbox_token"], thread_id=thread_id))
    # The in-process native SDK resolves only host-owned metadata. A deep link
    # in model text cannot select a thread or grant access.
    from langgraph_sdk import get_client
    from .conversation_handoff import handoff_tools
    sdk = get_client(api_key=None)
    audit = CaseModelAudit(actor="conversation", profile=profile, basis=basis, public_sink=public, private_sink=private, stream_public=True)
    model = case_chat_model(profile, basis, SimpleNamespace(base_url="https://api.deepseek.com"), SecretStr(os.environ["DEEPSEEK_API_KEY"]), streaming=True,
                            context_editing=specification.get("context_editing"))
    try:
        thread = await sdk.threads.get(thread_id)
        metadata = thread.get("metadata", {})
        from .working_memory_tools import working_memory_tools
        from .conversation_agent import GrantedTool
        grants.extend(GrantedTool(t, "working_note_write" if t.name == "WriteWorkingNote" else "read",
            "当前对话的工作底稿；不改用户原文件、不写入已核验事实库") for t in working_memory_tools(
                "conversation", owner=metadata.get("owner_id", "local-pilot"), workspace=thread_id))
        from .conversation_knowledge import knowledge_tools
        grants.extend(knowledge_tools(sdk=sdk, owner_id=metadata.get("owner_id", "local-pilot"), thread_id=thread_id))
        if metadata.get("handoff"):
            grants.extend(handoff_tools(reference=metadata["handoff"], sdk=sdk,
                                       owner_id=metadata.get("owner_id", "local-pilot")))
        yield build_conversation_agent(model=model, grants=grants,
            permission_mode=ids.get("permission_mode", "request_standard"), checkpointer=None,
            middleware=[audit], server_managed_persistence=True, **specification["limits"])
    except Exception as exc:
        from langgraph.errors import GraphInterrupt
        if not isinstance(exc, GraphInterrupt):
            objective = ("当前请求超过宿主上下文输入限额，已在发模型前停止；原始消息和来源仍保存在本对话，可缩小问题或交接到新窗口。"
                         if str(exc) == "case_review_input_ceiling_before_transport" else
                         "本轮尚未完成；原生checkpoint和已产生输出保留。请检查工具、权限或上下文容量后继续。")
            public({"kind": "stage", "actor": "conversation", "event": "failure", "status": "error",
                "error_type": type(exc).__name__, "objective": objective,
                "recorded_at": datetime.now(timezone.utc).isoformat(), "run_id": run_id})
        raise
    finally:
        await sdk.aclose()
