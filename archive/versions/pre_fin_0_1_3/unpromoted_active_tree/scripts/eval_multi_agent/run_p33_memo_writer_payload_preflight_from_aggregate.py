from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.memo_llm import (  # noqa: E402
    _compact_judgment_for_memo,
    _compact_memo_logic_plan_for_writer_prompt,
    _compact_shared_memo_context_for_prompt,
    _memo_profile_spec_from_name,
    _memo_writer_budget_spec_from_profile,
    build_shared_memo_context,
    memo_writer_input_pack_fingerprint_for_state,
)


DEFAULT_AGGREGATE_NODE = (
    REPO_ROOT
    / "eval"
    / "sec_cases"
    / "outputs"
    / "p33_gold_case_runs"
    / "p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7"
    / "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"
    / "aggregate_judgment_plan_node_result.json"
)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "p33_gold_case_runs"
SUMMARY_SCHEMA_VERSION = "p33_memo_writer_payload_preflight_summary_v0_1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a no-paid P33 Memo Writer payload preflight from an accepted aggregate_judgment_plan checkpoint. "
            "This verifies writer input projection only; it must not call an LLM."
        )
    )
    parser.add_argument("--aggregate-node-result", type=Path, default=DEFAULT_AGGREGATE_NODE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--max-prompt-chars", type=int, default=70000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    state = _read_json(args.aggregate_node_result)
    run_id = args.run_id or _default_run_id()
    case_id = _case_id_from_state(state, fallback=args.aggregate_node_result.parent.name)
    case_dir = args.output_root / run_id / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    summary = build_preflight_summary(
        state,
        run_id=run_id,
        case_id=case_id,
        aggregate_node_result=args.aggregate_node_result,
        case_dir=case_dir,
        elapsed_sec=round(time.time() - started, 4),
        max_prompt_chars=args.max_prompt_chars,
    )
    _write_summary(case_dir, summary)
    print(json.dumps(_stdout_summary(summary, case_dir), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def build_preflight_summary(
    state: Mapping[str, Any],
    *,
    run_id: str,
    case_id: str,
    aggregate_node_result: Path,
    case_dir: Path,
    elapsed_sec: float,
    max_prompt_chars: int,
) -> dict[str, Any]:
    shared_context = _compact_shared_memo_context_for_prompt(build_shared_memo_context(state))
    profile = _memo_profile_spec_from_name(
        ((shared_context.get("memo_profile") or {}) if isinstance(shared_context.get("memo_profile"), Mapping) else {}).get("profile")
    )
    budget = _memo_writer_budget_spec_from_profile(profile)
    memo_logic_plan = state.get("memo_logic_plan") if isinstance(state.get("memo_logic_plan"), Mapping) else {}
    compact_plan = _compact_memo_logic_plan_for_writer_prompt(memo_logic_plan, budget=budget)
    judgment = state.get("verified_judgment_plan") if isinstance(state.get("verified_judgment_plan"), Mapping) else state.get("judgment_plan") or {}
    compact_judgment = _compact_judgment_for_memo(judgment, memo_profile=profile, budget=budget)
    fingerprint = memo_writer_input_pack_fingerprint_for_state(
        state,
        capture_source="p33_memo_writer_payload_preflight_from_aggregate",
    )

    original_required_ids = [
        str(row.get("question_item_id") or "")
        for row in memo_logic_plan.get("required_item_answer_plan") or []
        if isinstance(row, Mapping) and str(row.get("question_item_id") or "")
    ]
    compact_required_ids = [
        str(row.get("question_item_id") or "")
        for row in compact_plan.get("required_item_answer_plan") or []
        if isinstance(row, Mapping) and str(row.get("question_item_id") or "")
    ]
    original_sections = _string_list(memo_logic_plan.get("section_order"))
    compact_sections = _string_list(compact_plan.get("section_order"))
    prompt_policy = shared_context.get("prompt_policy") if isinstance(shared_context.get("prompt_policy"), Mapping) else {}
    response_language = shared_context.get("response_language") if isinstance(shared_context.get("response_language"), Mapping) else {}
    component_summaries = fingerprint.get("component_summaries") if isinstance(fingerprint.get("component_summaries"), Mapping) else {}
    allowed_components = {
        "shared_memo_context",
        "supervising_analyst_pack",
        "memo_logic_plan",
        "verified_judgment_plan",
        "specialist_verification",
    }
    component_names = set(str(name) for name in component_summaries.keys())
    supported_claims = [row for row in judgment.get("supported_claims") or [] if isinstance(row, Mapping)]
    compact_claims = [row for row in compact_judgment.get("supported_claims") or [] if isinstance(row, Mapping)]

    checks = {
        "aggregate_checkpoint_present": bool(judgment) and bool(memo_logic_plan),
        "memo_logic_plan_validation_pass": ((memo_logic_plan.get("validation") or {}) if isinstance(memo_logic_plan.get("validation"), Mapping) else {}).get("status") == "pass",
        "response_language_zh_cn": response_language.get("language") == "zh-CN",
        "execution_mode_deep_research": str(shared_context.get("execution_mode") or "") == "deep_research",
        "memo_profile_deep_research": profile.profile == "deep_research",
        "required_item_answer_plan_complete": bool(original_required_ids) and set(original_required_ids).issubset(set(compact_required_ids)),
        "section_order_complete": bool(original_sections) and set(original_sections).issubset(set(compact_sections)),
        "compact_judgment_claims_present": len(compact_claims) >= min(8, len(supported_claims)),
        "evidence_refs_present": int(fingerprint.get("known_evidence_ref_count") or 0) >= 5,
        "raw_rows_excluded": prompt_policy.get("raw_evidence_rows") == "excluded"
        and prompt_policy.get("bounded_evidence_rows") == "excluded"
        and prompt_policy.get("private_operator_context") == "excluded",
        "only_allowed_components": component_names == allowed_components,
        "writer_prompt_chars_under_budget": int(fingerprint.get("approx_total_prompt_chars_with_scaffold") or 0) <= max_prompt_chars,
    }
    errors = [
        {"type": key, "status": "failed"}
        for key, passed in checks.items()
        if not passed
    ]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "created_at": _utc_now(),
        "gate_status": "pass" if not errors else "fail",
        "elapsed_sec": elapsed_sec,
        "checks": checks,
        "errors": errors,
        "writer_payload": {
            "memo_profile": profile.profile,
            "response_language": response_language,
            "execution_mode": str(shared_context.get("execution_mode") or ""),
            "user_query_prefix": str(shared_context.get("user_query") or "")[:120],
            "original_required_item_count": len(original_required_ids),
            "compact_required_item_count": len(compact_required_ids),
            "dropped_required_item_ids": [item for item in original_required_ids if item not in compact_required_ids],
            "original_section_count": len(original_sections),
            "compact_section_count": len(compact_sections),
            "dropped_sections": [item for item in original_sections if item not in compact_sections],
            "original_supported_claim_count": len(supported_claims),
            "compact_supported_claim_count": len(compact_claims),
            "known_evidence_ref_count": int(fingerprint.get("known_evidence_ref_count") or 0),
            "approx_prompt_payload_chars": int(fingerprint.get("approx_prompt_payload_chars") or 0),
            "approx_total_prompt_chars_with_scaffold": int(fingerprint.get("approx_total_prompt_chars_with_scaffold") or 0),
            "max_prompt_chars": max_prompt_chars,
            "writer_budget": dict(fingerprint.get("writer_budget") or {}),
            "component_summaries": component_summaries,
            "prompt_policy": dict(prompt_policy),
        },
        "artifact_refs": {
            "case_dir": str(case_dir.resolve()),
            "summary": str((case_dir / "memo_writer_payload_preflight_summary.json").resolve()),
            "aggregate_node_result": str(Path(aggregate_node_result).resolve()),
        },
        "boundary": {
            "scope": "node_level_memo_writer_input_projection_only",
            "not_run": ["memo_writer_llm", "verifier", "renderer", "broad_full_chain", "model_comparison"],
            "acceptance_meaning": "writer payload is shaped correctly; this does not prove prose quality or verifier pass.",
        },
    }


def _write_summary(case_dir: Path, summary: Mapping[str, Any]) -> None:
    (case_dir / "memo_writer_payload_preflight_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _stdout_summary(summary: Mapping[str, Any], case_dir: Path) -> dict[str, Any]:
    payload = summary.get("writer_payload") if isinstance(summary.get("writer_payload"), Mapping) else {}
    return {
        "schema_version": summary.get("schema_version"),
        "run_id": summary.get("run_id"),
        "case_id": summary.get("case_id"),
        "gate_status": summary.get("gate_status"),
        "checks": summary.get("checks"),
        "writer_payload": {
            "memo_profile": payload.get("memo_profile"),
            "response_language": payload.get("response_language"),
            "compact_required_item_count": payload.get("compact_required_item_count"),
            "compact_section_count": payload.get("compact_section_count"),
            "compact_supported_claim_count": payload.get("compact_supported_claim_count"),
            "approx_total_prompt_chars_with_scaffold": payload.get("approx_total_prompt_chars_with_scaffold"),
        },
        "summary_path": str((case_dir / "memo_writer_payload_preflight_summary.json").resolve()),
    }


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    return [str(value)] if str(value) else []


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _case_id_from_state(state: Mapping[str, Any], *, fallback: str) -> str:
    case_contract = state.get("case_contract") if isinstance(state.get("case_contract"), Mapping) else {}
    research_contract = (
        state.get("research_objective_contract")
        if isinstance(state.get("research_objective_contract"), Mapping)
        else {}
    )
    return str(
        state.get("case_id")
        or case_contract.get("case_id")
        or research_contract.get("case_id")
        or fallback
        or "p33_case"
    )


def _default_run_id() -> str:
    return f"p33_stepwise_memo_writer_payload_preflight_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
