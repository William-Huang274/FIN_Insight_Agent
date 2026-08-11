from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


TOOL_CAPABILITY_REGISTRY_SCHEMA_VERSION = "finsight_tool_capability_registry_v0_1"


@dataclass(frozen=True)
class ToolCapability:
    tool_id: str
    category: str
    owner_agent: str
    allowed_nodes: tuple[str, ...]
    input_schema: str
    output_artifact_schema: str
    source_boundary: str
    provenance_required: bool
    audit_required: bool
    forbidden_use: tuple[str, ...]


DEFAULT_TOOL_CAPABILITIES = (
    ToolCapability(
        "database_query",
        "data_retrieval",
        "evidence_operator",
        ("research_lead", "lead_review_checkpoint", "evidence_operator", "specialist"),
        "sql_query_request_v0_1",
        "sql_result_artifact_v0_1",
        "query_results_keep_original_source_authority",
        True,
        True,
        ("memo_writer_fact_lookup",),
    ),
    ToolCapability(
        "live_web_snapshot",
        "live_web",
        "web_evidence_operator",
        ("lead_review_checkpoint", "evidence_operator"),
        "allowlisted_web_snapshot_request_v0_1",
        "web_evidence_snapshot_v0_1",
        "context_only_until_snapshot_parser_authority_gate",
        True,
        True,
        ("unsupported_financial_fact_promotion", "identity_impersonation", "login_bypass", "fake_order"),
    ),
    ToolCapability(
        "document_parser",
        "input_parser",
        "input_parser",
        ("input_parser", "research_lead"),
        "uploaded_file_ref_v0_1",
        "user_provided_evidence_pack_v0_1",
        "user_provided_context_until_parser_gate",
        True,
        True,
        ("raw_upload_prompt_injection_without_provenance",),
    ),
    ToolCapability(
        "report_renderer",
        "output_renderer",
        "memo_writer",
        ("memo_writer", "report_renderer"),
        "verified_memo_payload_v0_1",
        "report_artifact_ref_v0_1",
        "render_only_no_new_facts",
        True,
        True,
        ("fact_retrieval", "database_query", "live_web_search"),
    ),
    ToolCapability(
        "graph_visualizer",
        "analysis_artifact",
        "research_lead",
        ("research_lead", "report_renderer"),
        "graph_edges_v0_1",
        "visual_artifact_ref_v0_1",
        "visualization_of_existing_claims_only",
        True,
        True,
        ("new_claim_generation",),
    ),
    ToolCapability(
        "multimodal_preprocess",
        "input_parser",
        "input_parser",
        ("input_parser",),
        "media_file_ref_v0_1",
        "parsed_media_artifact_v0_1",
        "parsed_context_requires_model_capability_and_provenance",
        True,
        True,
        ("claim_promotion_without_ocr_or_vision_gate",),
    ),
)


def default_tool_capability_registry() -> dict[str, Any]:
    return {
        "schema_version": TOOL_CAPABILITY_REGISTRY_SCHEMA_VERSION,
        "capabilities": [asdict(item) for item in DEFAULT_TOOL_CAPABILITIES],
        "policy": "agent_tools_are_permissioned_and_audited_no_writer_fact_tools_v0_1",
    }


def validate_tool_invocation(
    tool_id: str,
    *,
    node: str,
    agent_id: str = "",
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    reg = registry or default_tool_capability_registry()
    capabilities = {str(item.get("tool_id")): item for item in reg.get("capabilities") or [] if isinstance(item, Mapping)}
    capability = capabilities.get(tool_id)
    errors: list[dict[str, Any]] = []
    if not capability:
        errors.append({"type": "unknown_tool", "tool_id": tool_id})
        return _result(tool_id, node, agent_id, capability={}, errors=errors)
    allowed_nodes = set(capability.get("allowed_nodes") or [])
    if node not in allowed_nodes:
        errors.append({"type": "tool_node_not_allowed", "tool_id": tool_id, "node": node, "allowed_nodes": sorted(allowed_nodes)})
    owner = str(capability.get("owner_agent") or "")
    if agent_id and owner not in {agent_id, "evidence_operator", "input_parser", "web_evidence_operator"} and node != "report_renderer":
        errors.append({"type": "tool_owner_mismatch", "tool_id": tool_id, "agent_id": agent_id, "owner_agent": owner})
    if node == "memo_writer" and tool_id != "report_renderer":
        errors.append({"type": "memo_writer_tool_forbidden", "tool_id": tool_id})
    return _result(tool_id, node, agent_id, capability=capability, errors=errors)


def _result(tool_id: str, node: str, agent_id: str, *, capability: Mapping[str, Any], errors: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "finsight_tool_permission_gate_v0_1",
        "status": "fail" if errors else "pass",
        "tool_id": tool_id,
        "node": node,
        "agent_id": agent_id,
        "capability": dict(capability),
        "errors": errors,
    }
