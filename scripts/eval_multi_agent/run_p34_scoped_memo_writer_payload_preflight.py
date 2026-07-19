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
SCRIPT_ROOT = REPO_ROOT / "scripts" / "eval_multi_agent"
for root in (SRC_ROOT, SCRIPT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from run_p33_memo_writer_payload_preflight_from_aggregate import build_preflight_summary  # noqa: E402
from sec_agent.p34_lane_quality_runtime import build_ai_semis_scoped_writer_payload  # noqa: E402


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "p34_ai_semis_scoped_writer_runs"
SUMMARY_SCHEMA_VERSION = "p34_scoped_memo_writer_payload_preflight_summary_v0_1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the P34 AI/Semis scoped Memo Writer payload and run the no-paid writer input preflight. "
            "This does not call an LLM or run full-chain."
        )
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--max-prompt-chars", type=int, default=70000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    run_id = args.run_id or _default_run_id()
    state = build_ai_semis_scoped_writer_payload()
    case_id = str(state.get("case_id") or "p34_ai_semis_scoped_writer_case_v0_1")
    case_dir = args.output_root / run_id / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    input_state_path = case_dir / "p34_scoped_memo_writer_input_state.json"
    input_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    preflight = build_preflight_summary(
        state,
        run_id=run_id,
        case_id=case_id,
        aggregate_node_result=input_state_path,
        case_dir=case_dir,
        elapsed_sec=round(time.time() - started, 4),
        max_prompt_chars=args.max_prompt_chars,
    )
    summary = _p34_summary(
        state=state,
        preflight=preflight,
        run_id=run_id,
        case_id=case_id,
        case_dir=case_dir,
        input_state_path=input_state_path,
        elapsed_sec=round(time.time() - started, 4),
    )
    (case_dir / "p34_scoped_memo_writer_payload_preflight_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_stdout_summary(summary, case_dir), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def _p34_summary(
    *,
    state: Mapping[str, Any],
    preflight: Mapping[str, Any],
    run_id: str,
    case_id: str,
    case_dir: Path,
    input_state_path: Path,
    elapsed_sec: float,
) -> dict[str, Any]:
    judgment = state.get("verified_judgment_plan") if isinstance(state.get("verified_judgment_plan"), Mapping) else {}
    memo_plan = state.get("memo_logic_plan") if isinstance(state.get("memo_logic_plan"), Mapping) else {}
    payload = state.get("p34_scoped_writer_payload") if isinstance(state.get("p34_scoped_writer_payload"), Mapping) else {}
    claims = [row for row in judgment.get("supported_claims") or [] if isinstance(row, Mapping)]
    fact_blocks = [row for row in state.get("analyst_fact_table_blocks") or [] if isinstance(row, Mapping)]
    fact_rows = [row for block in fact_blocks for row in block.get("rows") or [] if isinstance(row, Mapping)]
    gaps = [row for row in state.get("bounded_gap_register") or [] if isinstance(row, Mapping)]
    required_items = [
        str(row.get("question_item_id") or "")
        for row in memo_plan.get("required_item_answer_plan") or []
        if isinstance(row, Mapping) and str(row.get("question_item_id") or "")
    ]
    required_set = {
        "cloud_capex_read_through",
        "req_accelerator_architecture",
        "req_customer_deployment",
        "req_dell_margin_quality",
        "req_supply_chain",
        "req_market_price_in",
        "req_counter_thesis",
    }
    gap_ids = {str(row.get("gap_id") or "") for row in gaps}
    checks = {
        "p33_writer_payload_preflight_pass": preflight.get("gate_status") == "pass",
        "scoped_writer_allowed": bool(payload) and payload.get("full_chain_allowed") is False,
        "seven_judgment_claims_present": len(claims) >= 7,
        "seven_required_items_present": required_set.issubset(set(required_items)),
        "dell_margin_gap_preserved": "dell_ai_server_margin_bridge_quality_gap" in gap_ids,
        "market_price_in_gap_preserved": "market_price_in_exact_positioning_gap" in gap_ids,
        "analyst_fact_tables_present": len(fact_blocks) >= 6 and len(fact_rows) >= 20,
        "product_spec_fact_table_present": any(
            str(block.get("block_id") or "") == "product_spec_architecture_table" for block in fact_blocks
        ),
        "attempt_backed_gap_table_present": any(
            str(block.get("block_id") or "") == "attempt_backed_gap_table" for block in fact_blocks
        ),
        "full_chain_not_allowed": payload.get("full_chain_allowed") is False and "full_chain" in set(state.get("not_run") or []),
        "memo_logic_validation_pass": ((memo_plan.get("validation") or {}) if isinstance(memo_plan.get("validation"), Mapping) else {}).get("status") == "pass",
    }
    errors = [{"type": key, "status": "failed"} for key, passed in checks.items() if not passed]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "created_at": _utc_now(),
        "elapsed_sec": elapsed_sec,
        "gate_status": "pass" if not errors else "fail",
        "checks": checks,
        "errors": errors,
        "p33_preflight": {
            "gate_status": preflight.get("gate_status"),
            "writer_payload": preflight.get("writer_payload") or {},
            "errors": preflight.get("errors") or [],
        },
        "p34_payload": dict(payload),
        "artifact_refs": {
            "case_dir": str(case_dir.resolve()),
            "input_state": str(input_state_path.resolve()),
            "summary": str((case_dir / "p34_scoped_memo_writer_payload_preflight_summary.json").resolve()),
            "p33_preflight_summary": str((case_dir / "memo_writer_payload_preflight_summary.json").resolve()),
        },
        "boundary": {
            "scope": "p34_scoped_writer_payload_preflight_only",
            "not_run": ["memo_writer_llm", "renderer", "verifier", "full_chain", "model_comparison", "case_expansion"],
            "acceptance_meaning": "P34 source-runtime rows have been projected into writer-ready judgment material; prose quality remains unproven.",
        },
    }


def _stdout_summary(summary: Mapping[str, Any], case_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": summary.get("schema_version"),
        "run_id": summary.get("run_id"),
        "case_id": summary.get("case_id"),
        "gate_status": summary.get("gate_status"),
        "checks": summary.get("checks"),
        "p33_writer_payload": (summary.get("p33_preflight") or {}).get("writer_payload"),
        "summary_path": str((case_dir / "p34_scoped_memo_writer_payload_preflight_summary.json").resolve()),
    }


def _default_run_id() -> str:
    return f"p34_scoped_memo_writer_payload_preflight_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
