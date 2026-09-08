"""Native Assistant persistence for user-owned research configurations."""
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from sec_agent.agent_runtime.studio_configuration import (
    StudioConfiguration, default_configuration, ROLE_TITLES,
)

STUDIO_SURFACE = "finsight_research_studio_v1"


async def owned_configuration(service, assistant_id):
    value = await service.sdk.assistants.get(str(assistant_id))
    if value.get("metadata", {}).get("surface") != STUDIO_SURFACE or value.get("graph_id") != "research_session":
        raise HTTPException(404, "研究配置不存在")
    config = StudioConfiguration.model_validate(value["config"]["configurable"]["finsight_studio"])
    if config.digest != value["metadata"].get("configuration_digest"):
        raise HTTPException(409, "配置已在外部改变，请重新保存为新版本")
    return value, config


async def run_configuration(service, thread, execution=None):
    from sec_agent.agent_runtime.execution_options import ExecutionOptions
    selection = execution or thread.get("metadata", {}).get("execution")
    values = {"finsight_execution": ExecutionOptions.model_validate(selection).model_dump()} if selection else {}
    assistant_id = thread.get("metadata", {}).get("studio_assistant_id")
    if not assistant_id:
        return {"configurable": values} if values else {}
    _, config = await owned_configuration(service, assistant_id)
    # Native run owns a full immutable config snapshot. Later task selection
    # cannot alter an in-flight request or an old checkpoint's configuration.
    return {"configurable": {**values, "finsight_studio": config.model_dump(), "finsight_studio_assistant_id": assistant_id}}


class ApplyConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thread_id: UUID


def build_studio_router(service, browser_write):
    router = APIRouter(prefix="/research-studio/configurations")

    @router.get("")
    async def configurations():
        rows = await service.sdk.assistants.search(metadata={"surface": STUDIO_SURFACE}, limit=100)
        return {"default": default_configuration().model_dump(), "roles": ROLE_TITLES,
            "versions": [{"assistant_id": r["assistant_id"], "title": r.get("name"), "created_at": r.get("created_at"),
                "digest": r.get("metadata", {}).get("configuration_digest")} for r in rows],
            "notice": "保存创建独立的原生配置版本；应用到任务后，从下一次运行生效。"}

    @router.get("/{assistant_id}")
    async def configuration(assistant_id: UUID):
        _, config = await owned_configuration(service, assistant_id)
        return {"assistant_id": str(assistant_id), "configuration": config.model_dump(), "digest": config.digest}

    @router.post("")
    async def save(body: StudioConfiguration, request: Request):
        browser_write(request)
        # Each save creates a new native Assistant, never updates an existing
        # version or default graph. No application DB or publication lock.
        assistant_id = str(uuid4())
        result = await service.sdk.assistants.create("research_session", assistant_id=assistant_id,
            name=body.title, config={"configurable": {"finsight_studio": body.model_dump()}},
            metadata={"surface": STUDIO_SURFACE, "configuration_digest": body.digest})
        return {"assistant_id": result["assistant_id"], "digest": body.digest, "configuration": body.model_dump()}

    @router.post("/{assistant_id}/apply")
    async def apply(assistant_id: UUID, body: ApplyConfiguration, request: Request):
        browser_write(request)
        _, config = await owned_configuration(service, assistant_id)
        thread = await service.owned_thread(body.thread_id)
        if thread.get("metadata", {}).get("graph") != "research_session":
            raise HTTPException(409, "当前配置适用于完整研究及其后续追问、修订")
        if thread.get("status") == "busy":
            raise HTTPException(409, "请等当前运行结束后再切换任务配置")
        await service.sdk.threads.update(str(body.thread_id), metadata={"studio_assistant_id": str(assistant_id),
            "studio_configuration_title": config.title, "studio_configuration_digest": config.digest})
        return {"applied": True, "notice": "已应用到任务；下一次运行固定读取此版本，历史报告不变。", "digest": config.digest}

    return router
