from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore


RESULT_SCHEMA = "fin_ia_0_1_3_s1_residual_gap_external_readjudication_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.residual_gap_external_capture_readjudication:v1"
RUN_SCOPE = "S1_RESIDUAL_GAP_EXTERNAL_SUPPLEMENT"
CASES = ("DELL", "MU", "NVDA", "ORCL", "ASML", "ANET")

_GENERIC_PAGE_TOKENS = (
    "annual meeting",
    "financial info",
    "financials",
    "financial strategy",
    "latest news",
    "press releases",
)
_SHELL_MARKERS = (
    "function ",
    "window.",
    "document.",
    "jquery",
    "googleanalytics",
    "{{",
    "q4inc",
    "toggle navigation",
    "cookie",
)
_DISCLOSURE_MARKERS = (
    "quarter ended",
    "net revenue was",
    "revenue increased",
    "gross margin was",
    "cash flow from operations",
    "guidance for",
    "backlog was",
    "orders were",
    "shipments were",
    "inventory was",
)


class ResidualGapExternalReadjudicationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ResidualGapExternalReadjudicationError(code)


def _without_digest(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    body = deepcopy(dict(payload))
    digest = body.pop(key, None)
    _require(isinstance(digest, str) and digest == canonical_digest(body), f"{key}_invalid")
    return body


def _load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "readjudication_input_not_object")
    return value


def load_inputs(
    *,
    external_result_path: str | Path,
    local_pack_result_path: str | Path,
    priority_plan_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    external = _load_json(external_result_path)
    local_pack = _load_json(local_pack_result_path)
    plan = _load_json(priority_plan_path)
    _without_digest(external, "result_digest")
    _without_digest(local_pack, "result_digest")
    _without_digest(plan, "plan_digest")
    _require(
        external.get("schema_version")
        == "fin_ia_0_1_3_s1_residual_gap_external_live_result_v1_0"
        and external.get("status") == "terminal_completed_with_candidates_and_typed_gaps"
        and external.get("admission_consumed") is True,
        "external_live_result_identity_invalid",
    )
    _require(
        local_pack.get("schema_version")
        == "fin_ia_0_1_3_s1_six_case_local_evidence_pack_result_v1_0"
        and local_pack.get("status")
        == "terminal_succeeded_six_case_local_evidence_packs_with_declared_gaps",
        "local_pack_result_identity_invalid",
    )
    _require(
        plan.get("schema_version")
        == "fin_ia_0_1_3_s1_residual_gap_external_priority_plan_v1_0"
        and plan.get("plan_digest") == external.get("priority_plan_digest")
        and plan.get("local_evidence_pack_result_digest")
        == local_pack.get("result_digest"),
        "readjudication_input_binding_invalid",
    )
    return external, local_pack, plan


def readjudicate_external_capture(
    *,
    external_result: Mapping[str, Any],
    local_pack_result: Mapping[str, Any],
    priority_plan: Mapping[str, Any],
    private_object_root: str | Path,
) -> dict[str, Any]:
    external_body = _without_digest(external_result, "result_digest")
    local_body = _without_digest(local_pack_result, "result_digest")
    plan_body = _without_digest(priority_plan, "plan_digest")
    _require(
        external_body.get("priority_plan_digest") == priority_plan.get("plan_digest")
        and priority_plan.get("local_evidence_pack_result_digest")
        == local_pack_result.get("result_digest"),
        "readjudication_input_binding_invalid",
    )
    intents = list(external_body.get("intent_results") or ())
    _require(
        len(intents) == 12
        and Counter(str(row.get("case_key")) for row in intents)
        == Counter({case_key: 2 for case_key in CASES}),
        "readjudication_intent_shape_invalid",
    )
    expected_intents = {
        str(row["intent_id"]): row for row in plan_body.get("selected_intents") or ()
    }
    _require(set(expected_intents) == {str(row.get("intent_id")) for row in intents},
             "readjudication_intent_plan_mismatch")
    store = FileCanonicalObjectStore(private_object_root)
    decisions = [
        _readjudicate_intent(row=row, expected=expected_intents[str(row["intent_id"])], store=store)
        for row in intents
    ]
    eligible = [row for row in decisions if row["decision"] == "eligible_for_successor_pack_build"]
    rejected = [row for row in decisions if row["decision"].startswith("rejected_")]
    original_counts = dict(local_body.get("observed_counts") or {})
    _require(int(original_counts.get("evidence_items") or -1) >= 0,
             "local_pack_counts_invalid")
    pack_digests = deepcopy(dict(local_body.get("pack_payload_digests") or {}))
    _require(set(pack_digests) == set(CASES), "local_pack_case_digest_shape_invalid")
    status = (
        "terminal_readjudicated_zero_external_additions_original_pack_reused"
        if not eligible
        else "terminal_readjudicated_successor_pack_build_required"
    )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": status,
        "external_live_result_digest": str(external_result["result_digest"]),
        "local_evidence_pack_result_digest": str(local_pack_result["result_digest"]),
        "priority_plan_digest": str(priority_plan["plan_digest"]),
        "decisions": decisions,
        "successor_pack_decision": {
            "mode": (
                "reuse_original_local_pack_unchanged"
                if not eligible
                else "build_content_addressed_successor_before_model_use"
            ),
            "original_pack_payload_digests": pack_digests,
            "resulting_pack_payload_digests": pack_digests if not eligible else {},
            "original_pack_artifacts": deepcopy(dict(local_body.get("pack_artifacts") or {})),
            "evidence_promoted_during_readjudication": False,
        },
        "observed_counts": {
            "intents_readjudicated": len(decisions),
            "eligible_for_successor_pack_build": len(eligible),
            "rejected_or_typed_gap": len(rejected),
            "external_evidence_additions": 0,
            "evidence_items_before": int(original_counts["evidence_items"]),
            "evidence_items_after": int(original_counts["evidence_items"]),
            "residual_gaps_before": int(original_counts["residual_gaps"]),
            "residual_gaps_after": int(original_counts["residual_gaps"]),
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "embedding_calls": 0,
            "rerank_calls": 0,
        },
        "stage_acceptance": {
            "external_live_preserved": True,
            "external_capture_readjudicated": True,
            "provider_snippet_promoted": False,
            "external_evidence_added": False,
            "fixed_local_pack_ready_for_model_analysis": not eligible,
            "deepseek_research": False,
            "release": False,
        },
        "known_boundary": (
            "Zero external additions means the immutable reviewed local pack is the fixed "
            "model input. It does not close residual gaps or prove report quality."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def _readjudicate_intent(
    *,
    row: Mapping[str, Any],
    expected: Mapping[str, Any],
    store: FileCanonicalObjectStore,
) -> dict[str, Any]:
    _require(
        row.get("intent_digest") == expected.get("intent_digest")
        and list(row.get("selected_gap_ids") or ()) == list(expected.get("selected_gap_ids") or ()),
        "readjudication_intent_binding_invalid",
    )
    base = {
        "intent_id": str(row["intent_id"]),
        "case_key": str(row["case_key"]),
        "intent_key": str(row["intent_key"]),
        "selected_gap_ids": list(row.get("selected_gap_ids") or ()),
        "live_status": str(row.get("status") or ""),
        "live_terminal_code": str(row.get("terminal_code") or ""),
        "selected_url": str((row.get("selected_locator") or {}).get("url") or ""),
        "provider_snippet_used": False,
        "provider_date_used": False,
        "evidence_promoted": False,
    }
    document = row.get("document")
    if not isinstance(document, Mapping) or document.get("status") != "captured_and_parsed":
        reason = (
            "no_qualified_official_locator"
            if not base["selected_url"]
            else str((document or {}).get("code") or row.get("terminal_code") or "document_unavailable")
        )
        return {**base, "decision": "rejected_typed_gap", "reason_codes": [reason], "full_text_read": False}
    parser_ref = document.get("parser_capture") or {}
    _require(
        isinstance(parser_ref, Mapping)
        and isinstance(parser_ref.get("object_key"), str)
        and isinstance(parser_ref.get("digest"), str),
        "readjudication_parser_capture_ref_invalid",
    )
    parser_capture = store.get_json(
        str(parser_ref["object_key"]), expected_digest=str(parser_ref["digest"])
    )
    _require(
        parser_capture.get("schema_version")
        == "fin_ia_0_1_3_s1_residual_document_parser_v1_0"
        and parser_capture.get("case_key") == row.get("case_key")
        and parser_capture.get("response_capture_digest")
        == (document.get("response_capture") or {}).get("digest"),
        "readjudication_parser_capture_binding_invalid",
    )
    text = re.sub(r"\s+", " ", str(parser_capture.get("parsed_text") or "")).strip()
    _require(text and canonical_digest(text) == parser_capture.get("parsed_text_digest"),
             "readjudication_parser_text_digest_invalid")
    lowered = text.lower()
    shell_hits = sorted(marker for marker in _SHELL_MARKERS if marker in lowered)
    disclosure_hits = sorted(marker for marker in _DISCLOSURE_MARKERS if marker in lowered)
    title = str((row.get("selected_locator") or {}).get("title") or "").lower()
    generic_title = any(token in title for token in _GENERIC_PAGE_TOKENS)
    publication = document.get("publication_date") or {}
    date_verified = bool(publication.get("date_value")) and publication.get("conflict_status") == "none"
    business_hits = sorted(set(str(value).lower() for value in row.get("matched_business_terms") or ()))
    reason_codes: list[str] = []
    if not date_verified:
        reason_codes.append("publication_date_unproven")
    if generic_title:
        reason_codes.append("generic_ir_page_not_disclosure")
    if len(shell_hits) >= 3 and len(disclosure_hits) < 2:
        reason_codes.append("navigation_or_script_shell_dominates")
    if len(disclosure_hits) < 2 or len(business_hits) < 2:
        reason_codes.append("insufficient_content_level_slot_fit")
    decision = (
        "eligible_for_successor_pack_build" if not reason_codes else "rejected_content_or_date_gate"
    )
    return {
        **base,
        "decision": decision,
        "reason_codes": reason_codes,
        "full_text_read": True,
        "full_text_digest": canonical_digest(text),
        "full_text_chars": len(text),
        "navigation_shell_markers": shell_hits,
        "financial_disclosure_markers": disclosure_hits,
        "matched_business_terms": business_hits,
        "publication_date_verified": date_verified,
    }


def write_readjudication_result(result: Mapping[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    _require(not path.exists(), "readjudication_result_already_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


__all__ = [
    "CONTRACT_REF",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "ResidualGapExternalReadjudicationError",
    "load_inputs",
    "readjudicate_external_capture",
    "write_readjudication_result",
]
