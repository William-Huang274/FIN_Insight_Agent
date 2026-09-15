"""A bounded Lead consultation within the existing worker's native execution."""
import json
from typing import Literal, TypedDict, Any
from pydantic import BaseModel, ConfigDict, Field
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, ToolRuntime
from .research_graph_contracts import canonical_sha256, RuntimeReceipt


class ResearchGuidance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    disposition: Literal["continue", "stop"]
    diagnosis: str = Field(min_length=20, max_length=3000)
    next_action: str = Field(min_length=20, max_length=3000)
    expected_progress: str = Field(min_length=20, max_length=2000)


class ProvideResearchGuidanceAction(ResearchGuidance):
    """Help the existing blocked expert: diagnose actual observations, prescribe a different scoped approach or stop. Do not repeat its whole task, mint evidence, add budget, or write its conclusion."""
    context_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason_summary: str = Field(min_length=1, max_length=2000)


class AssistanceState(TypedDict, total=False):
    turns: int
    tool_results: list[dict[str, Any]]
    request: dict[str, Any]
    batch: dict[str, Any]
    guidance: dict[str, Any]


def build_lead_assistance_graph(*, request_base, model_turn, source_reader, source_spaces, turn_source="provider_model"):
    from .specialist_graph import RequestSourceAction, SpecialistNativeToolBatch
    models = {"ProvideResearchGuidanceAction": ProvideResearchGuidanceAction, "RequestSourceAction": RequestSourceAction}
    def decide(state):
        if state.get("turns", 0) >= 4:
            return {"guidance": {"disposition": "stop", "diagnosis": "Lead consultation reached its bounded allowance without an accepted recovery plan.",
                "next_action": "Preserve the original worker and all source records for explicit diagnosis; do not restart automatically.",
                "expected_progress": "A diagnosed recovery approach is required before another execution attempt."}}
        request = {**request_base, "allowed_planning_tools": list(models), "source_read_enabled": True, "lead_assistance": True,
            "tool_results": state.get("tool_results", []), "progress": {"turn_index": state.get("turns", 0) + 1}}
        request["context_digest"] = canonical_sha256(request)
        response = model_turn(request)
        batch = SpecialistNativeToolBatch.model_validate_json(json.dumps(response["action"]))
        if batch.context_digest != request["context_digest"]:
            raise ValueError("lead_assistance_context_mismatch")
        if turn_source == "provider_model":
            receipt = RuntimeReceipt.model_validate_json(json.dumps(response.get("runtime_receipt")))
            if (receipt.actor != request["agent_id"] or receipt.status != "success" or receipt.kind != "model"
                    or receipt.request_digest != canonical_sha256(request) or receipt.output_digest != canonical_sha256(batch)):
                raise ValueError("lead_assistance_receipt_mismatch")
        return {"turns": state.get("turns", 0) + 1, "request": request, "batch": batch.model_dump(mode="json")}
    def execute(state, config: RunnableConfig):
        batch = SpecialistNativeToolBatch.model_validate_json(json.dumps(state["batch"]))
        updates = {}
        def invoke(runtime: ToolRuntime, **kwargs):
            call = next(c for c in batch.tool_calls if c.id == runtime.tool_call_id)
            try:
                if len(batch.tool_calls) != 1:
                    raise ValueError("one_scoped_assistance_action_per_turn")
                action = models[call.name].model_validate_json(json.dumps(call.args))
                if action.context_digest != batch.context_digest:
                    raise ValueError("lead_assistance_tool_context_mismatch")
                if isinstance(action, RequestSourceAction):
                    if action.selection.source_space not in source_spaces or action.selection.operation == "inspect_image":
                        raise ValueError("lead_assistance_source_scope_denied")
                    result = source_reader(action.selection)
                else:
                    result = {key: getattr(action, key) for key in ResearchGuidance.model_fields}
                    updates["guidance"] = result
                return ToolMessage(content=json.dumps(result, ensure_ascii=False), name=call.name, tool_call_id=call.id)
            except (ValueError, KeyError, TypeError) as exc:
                return ToolMessage(content=str(exc), name=call.name, tool_call_id=call.id, status="error")
        tools = [StructuredTool.from_function(invoke, name=k, description=m.__doc__ or k, args_schema=m.model_json_schema()) for k,m in models.items()]
        replies = ToolNode(tools, handle_tool_errors=False).invoke([AIMessage(content="", tool_calls=[c.model_dump(mode="json") for c in batch.tool_calls])], config={**config, "max_concurrency": 1})
        return {**updates, "tool_results": [m.model_dump(mode="json") for m in replies]}
    graph = StateGraph(AssistanceState)
    graph.add_node("lead", decide); graph.add_node("tools", execute)
    graph.add_edge(START, "lead")
    graph.add_conditional_edges("lead", lambda s: END if s.get("guidance") else "tools", [END, "tools"])
    graph.add_conditional_edges("tools", lambda s: END if s.get("guidance") else "lead", [END, "lead"])
    return graph
