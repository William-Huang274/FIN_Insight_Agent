from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.llm_gateway import chat_completion  # noqa: E402


CONTRACT_PATH = REPO_ROOT / "configs" / "releases" / "fin_ia_0_1_p36_three_cell_deepseek_vertical_contract_v1_1.json"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8765"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / ".codex_runtime" / "fin0.1-real-run"
READ_HEADERS = {
    "Accept": "application/json",
    "X-Fin-Case-Tenant": "fixture_internal",
    "X-Fin-Case-Project": "workbench_internal",
    "X-Fin-Case-Actor": "analyst_internal",
    "X-Fin-Case-Permissions": "case:read,evidence:read",
}


class VerticalRunError(RuntimeError):
    pass


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_json(url: str, *, timeout_s: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=READ_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return json.loads(response.read().decode("utf-8"))


def build_frozen_input_pack(
    contract: Mapping[str, Any],
    research: Mapping[str, Any],
    analysis: Mapping[str, Any],
) -> dict[str, Any]:
    binding = dict(contract["case_binding"])
    if research.get("case_id") != binding["case_id"] or analysis.get("case_id") != binding["case_id"]:
        raise VerticalRunError("case_binding_mismatch")
    if research.get("preview_digest") != binding["research_preview_digest"]:
        raise VerticalRunError("research_preview_digest_mismatch")
    if analysis.get("analysis_digest") != binding["analysis_digest"]:
        raise VerticalRunError("analysis_digest_mismatch")
    if analysis.get("source_preview_digest") != research.get("preview_digest"):
        raise VerticalRunError("analysis_source_preview_digest_mismatch")
    forbidden_counts = {
        "network_calls",
        "model_calls",
        "provider_calls",
        "external_tool_calls",
        "canonical_store_writes",
        "case_mutations",
        "evidence_promotions",
        "writer_source_access_calls",
        "release_admission",
    }
    _assert_forbidden_counts_zero(
        research.get("execution_counts"),
        "research.execution_counts",
        forbidden_counts,
    )
    _assert_forbidden_counts_zero(
        analysis.get("execution_counts"),
        "analysis.execution_counts",
        forbidden_counts,
    )
    _assert_forbidden_counts_zero(
        analysis.get("hard_boundaries"),
        "analysis.hard_boundaries",
        forbidden_counts,
    )

    selected_roles = list(binding["selected_roles"])
    cells_by_role = {str(row.get("evidence_role")): dict(row) for row in research.get("cells") or []}
    repairs_by_role = {str(row.get("evidence_role")): dict(row) for row in analysis.get("repairs") or []}
    missing = [role for role in selected_roles if role not in cells_by_role or role not in repairs_by_role]
    if missing:
        raise VerticalRunError(f"selected_role_missing:{','.join(missing)}")

    cells = []
    for role in selected_roles:
        source = cells_by_role[role]
        candidates = []
        for row in source.get("candidates") or []:
            candidate = {
                key: row.get(key)
                for key in (
                    "candidate_id",
                    "retrieval_lane",
                    "rank",
                    "ticker",
                    "title",
                    "excerpt",
                    "source_name",
                    "source_type",
                    "published_at",
                    "citation_url",
                    "citation_span",
                    "evidence_ref",
                    "authority_mode",
                    "claim_boundary",
                    "exact_value_authority",
                    "numeric_eligible",
                    "promotion_status",
                )
            }
            if candidate["promotion_status"] != "candidate_not_promoted":
                raise VerticalRunError("unexpected_candidate_promotion")
            candidates.append(candidate)
        if not candidates:
            raise VerticalRunError(f"selected_role_has_no_candidates:{role}")
        cells.append(
            {
                "cell_key": source.get("cell_key"),
                "evidence_role": role,
                "decision_question": source.get("decision_question"),
                "retrieval_lane": source.get("retrieval_lane"),
                "status": source.get("status"),
                "typed_gap": source.get("typed_gap"),
                "candidates": candidates,
                "deterministic_repair": repairs_by_role[role],
            }
        )

    numeric = dict(analysis.get("numeric") or {})
    if numeric.get("status") != "exact_local_facts_computed":
        raise VerticalRunError("numeric_not_exact_local_facts_computed")
    pack = {
        "schema_version": "fin_ia_0_1_p36_three_cell_model_input_v1_0",
        "contract_id": contract["contract_id"],
        "case_id": binding["case_id"],
        "case_version": research.get("case_version"),
        "query": research.get("query"),
        "as_of": research.get("as_of"),
        "research_preview_digest": research.get("preview_digest"),
        "analysis_digest": analysis.get("analysis_digest"),
        "selected_roles": selected_roles,
        "cells": cells,
        "numeric": {
            "status": numeric.get("status"),
            "facts": numeric.get("facts") or [],
            "derived_metrics": numeric.get("derived_metrics") or [],
        },
        "source_inventory": research.get("source_inventory") or [],
        "boundaries": {
            "candidate_evidence_not_promoted": True,
            "model_must_not_infer_beyond_claim_boundary": True,
            "canonical_case_writes": 0,
            "evidence_promotions": 0,
            "release_admission": False,
        },
    }
    return {"input_digest": canonical_digest(pack), **pack}


def build_writer_no_source_pack(
    input_pack: Mapping[str, Any],
    lead_review: Mapping[str, Any],
) -> dict[str, Any]:
    lead_synthesis = dict(lead_review["lead_synthesis"])
    reviewed_judgments = []
    for row in lead_review["reviewed_judgments"]:
        reviewed_judgments.append(
            {
                key: row.get(key)
                for key in (
                    "evidence_role",
                    "confidence",
                    "reviewed_judgment",
                    "evidence_refs",
                    "numeric_refs",
                    "counter_thesis",
                    "what_would_change",
                    "remaining_gap",
                )
            }
        )
    return {
        "schema_version": "fin_ia_0_1_p36_writer_no_source_input_v1_0",
        "case_id": input_pack["case_id"],
        "query": input_pack["query"],
        "as_of": input_pack["as_of"],
        "research_preview_digest": input_pack["research_preview_digest"],
        "analysis_digest": input_pack["analysis_digest"],
        "reviewed_judgments": reviewed_judgments,
        "lead_synthesis": {
            key: lead_synthesis.get(key)
            for key in ("primary_thesis", "decision_usefulness", "material_boundaries")
        },
        "numeric": _writer_numeric_projection(input_pack["numeric"]),
        "source_access_calls": 0,
        "forbidden_fields": ["cells", "candidates", "excerpt", "citation_url", "citation_span"],
    }


def _writer_numeric_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    fact_fields = (
        "candidate_id",
        "metric_family",
        "metric_name",
        "value",
        "unit",
        "period",
        "fiscal_year",
        "authority_mode",
        "claim_boundary",
    )
    derived_fields = (
        "metric",
        "value",
        "unit",
        "formula",
        "input_refs",
    )
    return {
        "status": value.get("status"),
        "facts": [
            {key: row.get(key) for key in fact_fields}
            for row in value.get("facts") or []
        ],
        "derived_metrics": [
            {key: row.get(key) for key in derived_fields}
            for row in value.get("derived_metrics") or []
        ],
    }


def validate_domain_output(value: Mapping[str, Any], input_pack: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(value)
    judgments = output.get("judgments")
    if not isinstance(judgments, list) or len(judgments) != 3:
        raise VerticalRunError("domain_judgment_count_mismatch")
    expected = set(input_pack["selected_roles"])
    actual = {str(row.get("evidence_role")) for row in judgments if isinstance(row, Mapping)}
    if actual != expected:
        raise VerticalRunError("domain_judgment_role_mismatch")
    allowed_refs = {
        str(candidate["candidate_id"])
        for cell in input_pack["cells"]
        for candidate in cell["candidates"]
    }
    for row in judgments:
        if not isinstance(row, Mapping):
            raise VerticalRunError("domain_judgment_not_object")
        refs = row.get("evidence_refs")
        if not isinstance(refs, list) or not refs or not set(map(str, refs)).issubset(allowed_refs):
            raise VerticalRunError("domain_judgment_invalid_evidence_refs")
        for key in ("judgment", "counter_thesis", "what_would_change", "remaining_gap"):
            if not str(row.get(key) or "").strip():
                raise VerticalRunError(f"domain_judgment_missing_{key}")
    output["status"] = "domain_judgment_validated"
    return output


def validate_lead_output(value: Mapping[str, Any], input_pack: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(value)
    judgments = output.get("reviewed_judgments")
    if not isinstance(judgments, list) or len(judgments) != 3:
        raise VerticalRunError("lead_reviewed_judgment_count_mismatch")
    expected = set(input_pack["selected_roles"])
    actual = {str(row.get("evidence_role")) for row in judgments if isinstance(row, Mapping)}
    if actual != expected:
        raise VerticalRunError("lead_reviewed_judgment_role_mismatch")
    if not isinstance(output.get("lead_synthesis"), Mapping):
        raise VerticalRunError("lead_synthesis_missing")
    for row in judgments:
        for key in ("reviewed_judgment", "counter_thesis", "what_would_change", "remaining_gap"):
            if not str(row.get(key) or "").strip():
                raise VerticalRunError(f"lead_review_missing_{key}")
    output["status"] = "lead_review_and_bounded_repair_validated"
    return output


def validate_writer_output(value: Mapping[str, Any], input_pack: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(value)
    sections = output.get("sections")
    if not isinstance(sections, list) or len(sections) != 3:
        raise VerticalRunError("writer_section_count_mismatch")
    expected = set(input_pack["selected_roles"])
    actual = {str(row.get("evidence_role")) for row in sections if isinstance(row, Mapping)}
    if actual != expected:
        raise VerticalRunError("writer_section_role_mismatch")
    if not str(output.get("executive_summary") or "").strip():
        raise VerticalRunError("writer_executive_summary_missing")
    if any(key in json.dumps(output, ensure_ascii=False) for key in ('"citation_url"', '"citation_span"', '"excerpt"')):
        raise VerticalRunError("writer_source_boundary_violated")
    output["source_access_calls"] = 0
    output["status"] = "model_vertical_ready_for_exact_human_senior_review"
    return output


def _assert_forbidden_counts_zero(value: Any, name: str, forbidden: set[str]) -> None:
    if not isinstance(value, Mapping):
        raise VerticalRunError(f"{name}_missing")
    nonzero = {
        str(key): item
        for key, item in value.items()
        if str(key) in forbidden and int(item or 0) != 0
    }
    if nonzero:
        raise VerticalRunError(f"{name}_nonzero:{json.dumps(nonzero, sort_keys=True)}")


def _stage_prompts(stage_id: str, payload: Mapping[str, Any]) -> tuple[str, str]:
    common = (
        "You are operating an internal financial-research candidate workflow. Return one JSON object only. "
        "Never invent evidence, dates, quantities, or source authority. Preserve every unresolved boundary. "
        "This is not investment advice and is not release-admitted."
    )
    if stage_id == "domain_judgment":
        instruction = (
            "For each of the three evidence_role values, produce one bounded analyst judgment. "
            "Schema: {judgments:[{evidence_role,confidence,judgment,evidence_refs,numeric_refs,"
            "counter_thesis,what_would_change,remaining_gap}]}. evidence_refs must use candidate_id values from input."
        )
    elif stage_id == "lead_review_and_bounded_repair":
        instruction = (
            "Act as Research Lead. Review the three domain judgments against the frozen evidence and claim boundaries. "
            "Perform one bounded wording/boundary repair in this response; do not request another model round. "
            "Schema: {lead_synthesis:{primary_thesis,decision_usefulness,material_boundaries},"
            "review_findings:[{evidence_role,finding,repair_applied}],reviewed_judgments:[{evidence_role,"
            "confidence,reviewed_judgment,evidence_refs,numeric_refs,counter_thesis,what_would_change,remaining_gap}]}"
        )
    else:
        instruction = (
            "Act as a no-source Writer. You may use only reviewed_judgments, lead_synthesis, and numeric in the input. "
            "Do not emit citations or source excerpts. Produce Chinese research prose, not a list of copied judgments. "
            "Schema: {title,executive_summary,decision_implications,sections:[{evidence_role,heading,narrative,"
            "boundary,what_would_change}],unresolved_gaps:[string],review_note}."
        )
    return common, instruction + "\nINPUT_JSON:\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _parse_json_content(content: str, *, stage_id: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise VerticalRunError(f"{stage_id}_invalid_json:{exc.msg}") from exc
    if not isinstance(value, dict):
        raise VerticalRunError(f"{stage_id}_output_not_object")
    return value


def _usage_summary(result: Mapping[str, Any], pricing: Mapping[str, Any]) -> dict[str, Any]:
    raw_usage = ((result.get("raw_response") or {}).get("usage") or {}) if isinstance(result.get("raw_response"), Mapping) else {}
    cache_hit = int(raw_usage.get("prompt_cache_hit_tokens") or 0)
    cache_miss = int(raw_usage.get("prompt_cache_miss_tokens") or result.get("input_tokens") or 0)
    output = int(result.get("output_tokens") or 0)
    cost = (
        cache_hit * float(pricing["input_cache_hit_usd_per_million"])
        + cache_miss * float(pricing["input_cache_miss_usd_per_million"])
        + output * float(pricing["output_usd_per_million"])
    ) / 1_000_000
    return {
        "call_id": result.get("call_id"),
        "model": result.get("model"),
        "finish_reason": result.get("finish_reason"),
        "latency_ms": result.get("latency_ms"),
        "input_tokens": int(result.get("input_tokens") or 0),
        "input_cache_hit_tokens": cache_hit,
        "input_cache_miss_tokens": cache_miss,
        "output_tokens": output,
        "total_tokens": int(result.get("total_tokens") or 0),
        "estimated_cost_usd": round(cost, 8),
        "transport_attempt_count": int(result.get("transport_attempt_count") or 0),
    }


def _call_provider_preflight(
    *,
    contract: Mapping[str, Any],
    event_log_path: Path,
) -> dict[str, Any]:
    model = dict(contract["model_profile"])
    preflight = dict(contract["provider_preflight"])
    system = "You are a connectivity preflight endpoint. Return one compact JSON object only."
    user = '{"status":"ok"}'
    _assert_projected_call_within_cap(
        input_bytes=len((system + user).encode("utf-8")),
        max_output_tokens=int(preflight["max_output_tokens"]),
        spent_usd=0.0,
        cap_usd=float(contract["execution_budget"]["max_total_cost_usd"]),
        pricing=contract["execution_budget"]["pricing_snapshot"],
    )
    old_retry = os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES")
    old_log = os.environ.get("LLM_GATEWAY_EVENT_LOG_PATH")
    os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = "0"
    os.environ["LLM_GATEWAY_EVENT_LOG_PATH"] = str(event_log_path)
    try:
        return chat_completion(
            llm_backend=str(model["provider"]),
            base_url=str(model["base_url"]),
            chat_completions_path=str(model["chat_completions_path"]),
            model=str(model["model"]),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": str(model["response_format"])},
            api_key_env=str(model["api_key_env"]),
            temperature=0.0,
            max_tokens=int(preflight["max_output_tokens"]),
            timeout_s=60,
            stream=False,
            enable_thinking=False,
            role="provider_preflight",
            profile="fin_ia_0_1_p36_three_cell_model_vertical",
            trace_tags={"contract_id": contract["contract_id"], "preflight": True},
        )
    finally:
        if old_retry is None:
            os.environ.pop("LLM_GATEWAY_TRANSPORT_RETRIES", None)
        else:
            os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = old_retry
        if old_log is None:
            os.environ.pop("LLM_GATEWAY_EVENT_LOG_PATH", None)
        else:
            os.environ["LLM_GATEWAY_EVENT_LOG_PATH"] = old_log


def _call_stage(
    *,
    contract: Mapping[str, Any],
    stage: Mapping[str, Any],
    payload: Mapping[str, Any],
    event_log_path: Path,
    spent_usd: float,
) -> dict[str, Any]:
    model = dict(contract["model_profile"])
    system, user = _stage_prompts(str(stage["stage_id"]), payload)
    _assert_projected_call_within_cap(
        input_bytes=len((system + user).encode("utf-8")),
        max_output_tokens=int(stage["max_output_tokens"]),
        spent_usd=spent_usd,
        cap_usd=float(contract["execution_budget"]["max_total_cost_usd"]),
        pricing=contract["execution_budget"]["pricing_snapshot"],
    )
    old_retry = os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES")
    old_log = os.environ.get("LLM_GATEWAY_EVENT_LOG_PATH")
    os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = "0"
    os.environ["LLM_GATEWAY_EVENT_LOG_PATH"] = str(event_log_path)
    try:
        return chat_completion(
            llm_backend=str(model["provider"]),
            base_url=str(model["base_url"]),
            chat_completions_path=str(model["chat_completions_path"]),
            model=str(model["model"]),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": str(model["response_format"])},
            api_key_env=str(model["api_key_env"]),
            temperature=float(model["temperature"]),
            max_tokens=int(stage["max_output_tokens"]),
            timeout_s=300,
            stream=False,
            enable_thinking=model["thinking"] == "enabled",
            reasoning_effort=str(model["reasoning_effort"]),
            role=str(stage["stage_id"]),
            profile="fin_ia_0_1_p36_three_cell_model_vertical",
            trace_tags={"contract_id": contract["contract_id"], "input_digest": payload.get("input_digest", "")},
        )
    finally:
        if old_retry is None:
            os.environ.pop("LLM_GATEWAY_TRANSPORT_RETRIES", None)
        else:
            os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = old_retry
        if old_log is None:
            os.environ.pop("LLM_GATEWAY_EVENT_LOG_PATH", None)
        else:
            os.environ["LLM_GATEWAY_EVENT_LOG_PATH"] = old_log


def _provider_preflight_projection(result: Mapping[str, Any], usage: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "fin_ia_0_1_provider_preflight_v1_0",
        "status": "ok" if result.get("status") == "ok" else "fail",
        "model": result.get("model"),
        "call_id": result.get("call_id"),
        "finish_reason": result.get("finish_reason"),
        "failure_reason": str(result.get("failure_reason") or "")[:1000],
        "latency_ms": result.get("latency_ms"),
        "transport_attempt_count": result.get("transport_attempt_count"),
        "usage": dict(usage),
        "api_key_saved": False,
        "raw_response_saved": False,
    }


def _write_execution_progress(
    artifact_dir: Path,
    *,
    status: str,
    last_attempted_call: str,
    usage_rows: list[Mapping[str, Any]],
    semantic_model_calls_completed: int,
    stop_reason: str = "",
) -> dict[str, Any]:
    progress = {
        "schema_version": "fin_ia_0_1_p36_three_cell_model_execution_progress_v1_0",
        "status": status,
        "last_attempted_call": last_attempted_call,
        "provider_preflight_call_count": sum(
            1 for row in usage_rows if row.get("stage_id") == "provider_preflight"
        ),
        "semantic_model_call_count": sum(
            1 for row in usage_rows if row.get("stage_id") != "provider_preflight"
        ),
        "semantic_model_calls_completed": semantic_model_calls_completed,
        "total_paid_call_count": len(usage_rows),
        "network_model_call_count": len(usage_rows),
        "estimated_total_cost_usd": round(
            sum(float(row.get("estimated_cost_usd") or 0.0) for row in usage_rows), 8
        ),
        "canonical_case_write_count": 0,
        "evidence_promotion_count": 0,
        "business_case_mutation_count": 0,
        "usage": [dict(row) for row in usage_rows],
        "stop_reason": stop_reason,
    }
    _write_json(artifact_dir / "execution_progress.json", progress)
    return progress


def execute_vertical(
    contract: Mapping[str, Any],
    input_pack: Mapping[str, Any],
    artifact_dir: Path,
) -> dict[str, Any]:
    if not os.environ.get(str(contract["model_profile"]["api_key_env"])):
        raise VerticalRunError("deepseek_api_key_missing")
    stages = {str(row["stage_id"]): dict(row) for row in contract["stages"]}
    expected_stages = {
        "domain_judgment",
        "lead_review_and_bounded_repair",
        "writer_no_source",
    }
    budget = dict(contract["execution_budget"])
    if set(stages) != expected_stages:
        raise VerticalRunError("semantic_stage_set_mismatch")
    if int(budget["max_provider_preflight_calls"]) != 1:
        raise VerticalRunError("provider_preflight_budget_mismatch")
    if int(budget["max_semantic_model_calls"]) != 3 or int(budget["max_total_paid_calls"]) != 4:
        raise VerticalRunError("paid_call_budget_mismatch")
    usage_rows: list[dict[str, Any]] = []
    pricing = budget["pricing_snapshot"]
    cost_cap = float(budget["max_total_cost_usd"])
    event_log_path = artifact_dir / "model_events.jsonl"
    semantic_completed = 0

    preflight_result = _call_provider_preflight(
        contract=contract,
        event_log_path=event_log_path,
    )
    preflight_usage = {
        "stage_id": "provider_preflight",
        **_usage_summary(preflight_result, pricing),
    }
    usage_rows.append(preflight_usage)
    preflight_projection = _provider_preflight_projection(preflight_result, preflight_usage)
    _write_json(artifact_dir / "provider_preflight.json", preflight_projection)
    _write_execution_progress(
        artifact_dir,
        status="provider_preflight_attempted",
        last_attempted_call="provider_preflight",
        usage_rows=usage_rows,
        semantic_model_calls_completed=semantic_completed,
    )
    _assert_cost_within_cap(usage_rows, cost_cap)
    if preflight_result.get("status") != "ok":
        raise VerticalRunError(
            f"provider_preflight_failure:{preflight_result.get('failure_reason') or preflight_result.get('status')}"
        )

    domain_result = _call_stage(
        contract=contract,
        stage=stages["domain_judgment"],
        payload=input_pack,
        event_log_path=event_log_path,
        spent_usd=sum(float(row["estimated_cost_usd"]) for row in usage_rows),
    )
    usage_rows.append({"stage_id": "domain_judgment", **_usage_summary(domain_result, pricing)})
    _write_execution_progress(
        artifact_dir,
        status="semantic_call_attempted",
        last_attempted_call="domain_judgment",
        usage_rows=usage_rows,
        semantic_model_calls_completed=semantic_completed,
    )
    _assert_cost_within_cap(usage_rows, cost_cap)
    if domain_result.get("status") != "ok":
        raise VerticalRunError(
            f"domain_judgment_provider_failure:{domain_result.get('failure_reason') or domain_result.get('status')}"
        )
    domain_raw = _parse_json_content(str(domain_result.get("content") or ""), stage_id="domain_judgment")
    domain = validate_domain_output(domain_raw, input_pack)
    _write_json(artifact_dir / "domain_judgment.json", domain)
    semantic_completed += 1

    lead_payload = {"input_pack": input_pack, "domain_judgment": domain}
    lead_result = _call_stage(
        contract=contract,
        stage=stages["lead_review_and_bounded_repair"],
        payload=lead_payload,
        event_log_path=event_log_path,
        spent_usd=sum(float(row["estimated_cost_usd"]) for row in usage_rows),
    )
    usage_rows.append({
        "stage_id": "lead_review_and_bounded_repair",
        **_usage_summary(lead_result, pricing),
    })
    _write_execution_progress(
        artifact_dir,
        status="semantic_call_attempted",
        last_attempted_call="lead_review_and_bounded_repair",
        usage_rows=usage_rows,
        semantic_model_calls_completed=semantic_completed,
    )
    _assert_cost_within_cap(usage_rows, cost_cap)
    if lead_result.get("status") != "ok":
        raise VerticalRunError(
            "lead_review_and_bounded_repair_provider_failure:"
            f"{lead_result.get('failure_reason') or lead_result.get('status')}"
        )
    lead_raw = _parse_json_content(
        str(lead_result.get("content") or ""),
        stage_id="lead_review_and_bounded_repair",
    )
    lead = validate_lead_output(lead_raw, input_pack)
    _write_json(artifact_dir / "lead_review.json", lead)
    semantic_completed += 1

    writer_input = build_writer_no_source_pack(input_pack, lead)
    _write_json(artifact_dir / "writer_no_source_input.json", writer_input)
    writer_result = _call_stage(
        contract=contract,
        stage=stages["writer_no_source"],
        payload=writer_input,
        event_log_path=event_log_path,
        spent_usd=sum(float(row["estimated_cost_usd"]) for row in usage_rows),
    )
    usage_rows.append({"stage_id": "writer_no_source", **_usage_summary(writer_result, pricing)})
    _write_execution_progress(
        artifact_dir,
        status="semantic_call_attempted",
        last_attempted_call="writer_no_source",
        usage_rows=usage_rows,
        semantic_model_calls_completed=semantic_completed,
    )
    _assert_cost_within_cap(usage_rows, cost_cap)
    if writer_result.get("status") != "ok":
        raise VerticalRunError(
            f"writer_no_source_provider_failure:{writer_result.get('failure_reason') or writer_result.get('status')}"
        )
    writer_raw = _parse_json_content(str(writer_result.get("content") or ""), stage_id="writer_no_source")
    writer = validate_writer_output(writer_raw, input_pack)
    _write_json(artifact_dir / "writer_draft.json", writer)
    semantic_completed += 1
    _write_execution_progress(
        artifact_dir,
        status="model_vertical_ready_for_exact_human_senior_review",
        last_attempted_call="writer_no_source",
        usage_rows=usage_rows,
        semantic_model_calls_completed=semantic_completed,
    )

    return {
        "status": "model_vertical_ready_for_exact_human_senior_review",
        "provider_preflight_call_count": 1,
        "semantic_model_call_count": 3,
        "total_paid_call_count": len(usage_rows),
        "model_call_count": len(usage_rows),
        "network_call_count": len(usage_rows),
        "canonical_case_write_count": 0,
        "evidence_promotion_count": 0,
        "business_case_mutation_count": 0,
        "writer_source_access_calls": 0,
        "usage": usage_rows,
        "estimated_total_cost_usd": round(sum(float(row["estimated_cost_usd"]) for row in usage_rows), 8),
        "artifacts": {
            "provider_preflight": "provider_preflight.json",
            "domain_judgment": "domain_judgment.json",
            "lead_review": "lead_review.json",
            "writer_no_source_input": "writer_no_source_input.json",
            "writer_draft": "writer_draft.json",
            "model_events": "model_events.jsonl",
            "execution_progress": "execution_progress.json",
        },
        "artifact_digests": {
            "provider_preflight": canonical_digest(preflight_projection),
            "domain_judgment": canonical_digest(domain),
            "lead_review": canonical_digest(lead),
            "writer_no_source_input": canonical_digest(writer_input),
            "writer_draft": canonical_digest(writer),
        },
    }


def _assert_cost_within_cap(rows: list[Mapping[str, Any]], cap: float) -> None:
    total = sum(float(row["estimated_cost_usd"]) for row in rows)
    if total > cap:
        raise VerticalRunError(f"paid_llm_cost_cap_exceeded:{total:.8f}>{cap:.8f}")


def _assert_projected_call_within_cap(
    *,
    input_bytes: int,
    max_output_tokens: int,
    spent_usd: float,
    cap_usd: float,
    pricing: Mapping[str, Any],
) -> None:
    # UTF-8 byte count is a conservative upper bound for input token count.
    projected = (
        input_bytes * float(pricing["input_cache_miss_usd_per_million"])
        + max_output_tokens * float(pricing["output_usd_per_million"])
    ) / 1_000_000
    if spent_usd + projected > cap_usd:
        raise VerticalRunError(
            f"projected_paid_llm_cost_cap_exceeded:{spent_usd + projected:.8f}>{cap_usd:.8f}"
        )


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or execute the FIN 0.1 P36 three-cell DeepSeek model vertical.")
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute one paid provider preflight plus three paid semantic model calls after freezing the input pack.",
    )
    parser.add_argument("--approve-paid-llm", action="store_true", help="Explicit acknowledgement required together with --execute.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.execute != args.approve_paid_llm:
        raise VerticalRunError("paid_execution_requires_both_execute_and_approve_paid_llm")
    contract = load_json(args.contract.resolve())
    binding = contract["case_binding"]
    case_id = str(binding["case_id"])
    base = str(args.api_base_url).rstrip("/")
    research = fetch_json(f"{base}/api/v1/cases/{case_id}/local-research-preview")
    analysis = fetch_json(f"{base}/api/v1/cases/{case_id}/local-analysis-preview")
    input_pack = build_frozen_input_pack(contract, research, analysis)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}_p36_three_cell_deepseek_v4_pro_internal_r1"
    artifact_dir = args.artifact_root.resolve() / run_id
    artifact_dir.mkdir(parents=True, exist_ok=False)
    _write_json(artifact_dir / "input_pack.json", input_pack)
    manifest: dict[str, Any] = {
        "schema_version": "fin_ia_0_1_p36_three_cell_model_vertical_run_v1_0",
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_id": contract["contract_id"],
        "contract_digest": canonical_digest(contract),
        "input_digest": input_pack["input_digest"],
        "case_id": case_id,
        "selected_roles": input_pack["selected_roles"],
        "mode": "paid_model_vertical" if args.execute else "freeze_only",
        "status": "frozen_pending_explicit_paid_llm_approval",
        "execution_budget": {
            "provider_preflight_calls": contract["execution_budget"]["max_provider_preflight_calls"],
            "semantic_model_calls": contract["execution_budget"]["max_semantic_model_calls"],
            "total_paid_calls": contract["execution_budget"]["max_total_paid_calls"],
            "max_total_cost_usd": contract["execution_budget"]["max_total_cost_usd"],
        },
        "execution_counts": {
            "provider_preflight_calls": 0,
            "semantic_model_calls": 0,
            "total_paid_calls": 0,
            "model_calls": 0,
            "network_model_calls": 0,
            "canonical_case_writes": 0,
            "evidence_promotions": 0,
            "business_case_mutations": 0,
        },
        "artifact_dir": str(artifact_dir),
    }
    _write_json(artifact_dir / "run_manifest.json", manifest)
    if args.execute:
        try:
            result = execute_vertical(contract, input_pack, artifact_dir)
            manifest.update(result)
            manifest["execution_counts"].update(
                {
                    "provider_preflight_calls": result["provider_preflight_call_count"],
                    "semantic_model_calls": result["semantic_model_call_count"],
                    "total_paid_calls": result["total_paid_call_count"],
                    "model_calls": result["model_call_count"],
                    "network_model_calls": result["network_call_count"],
                }
            )
            _write_json(artifact_dir / "run_manifest.json", manifest)
        except VerticalRunError as exc:
            progress_path = artifact_dir / "execution_progress.json"
            progress = load_json(progress_path) if progress_path.exists() else {}
            manifest.update(
                {
                    "status": "stopped_fail_closed",
                    "stop_reason": str(exc),
                    "estimated_total_cost_usd": progress.get("estimated_total_cost_usd", 0.0),
                    "usage": progress.get("usage", []),
                }
            )
            manifest["execution_counts"].update(
                {
                    "provider_preflight_calls": progress.get("provider_preflight_call_count", 0),
                    "semantic_model_calls": progress.get("semantic_model_call_count", 0),
                    "total_paid_calls": progress.get("total_paid_call_count", 0),
                    "model_calls": progress.get("total_paid_call_count", 0),
                    "network_model_calls": progress.get("network_model_call_count", 0),
                }
            )
            _write_json(artifact_dir / "run_manifest.json", manifest)
            raise
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerticalRunError as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
