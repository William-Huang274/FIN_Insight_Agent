from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402


DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_"
    "three_family_natural_canary_result_v1_0.json"
)
EXPECTED_REQUEST_IDS = (
    "FIN013-S2-DELL-demand_authenticity_and_sustainability",
    "FIN013-S2-MU-value_and_profit_capture",
    "FIN013-S2-NVDA-bottleneck_counterevidence_and_what_would_change",
)
FORBIDDEN_PRIVATE_TEXT = (
    "authorization",
    "deepseek_api_key",
    "cookie",
)


class NaturalCanaryResultError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise NaturalCanaryResultError(code)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "natural_canary_json_object_required")
    return value


def _digest_without(record: Mapping[str, Any], key: str) -> str:
    return canonical_digest({name: value for name, value in record.items() if name != key})


def materialize(*, admission_path: Path, terminal_path: Path) -> dict[str, Any]:
    admission = _load(admission_path)
    terminal = _load(terminal_path)
    runtime_root = terminal_path.parent.resolve()

    _require(
        admission.get("admission_digest")
        == _digest_without(admission, "admission_digest"),
        "natural_canary_admission_digest_mismatch",
    )
    _require(
        terminal.get("terminal_result_digest")
        == _digest_without(terminal, "terminal_result_digest"),
        "natural_canary_terminal_digest_mismatch",
    )
    _require(
        terminal.get("admission_digest") == admission.get("admission_digest")
        and terminal.get("run_id") == admission.get("run_id")
        and terminal.get("attempt_id") == admission.get("attempt_id"),
        "natural_canary_execution_identity_mismatch",
    )
    _require(
        terminal.get("status") == "terminal_succeeded_exact_once"
        and terminal.get("terminal_code") == "three_family_canary_pass"
        and terminal.get("completed_calls") == 3
        and terminal.get("retry_count") == 0
        and terminal.get("fallback_count") == 0
        and terminal.get("business_artifact_promotions") == 0,
        "natural_canary_terminal_not_successful",
    )

    rows = list(terminal.get("family_results") or ())
    _require(
        [row.get("request_id") for row in rows] == list(EXPECTED_REQUEST_IDS),
        "natural_canary_request_order_or_count_invalid",
    )
    public_rows: list[dict[str, Any]] = []
    for row in rows:
        capture_ref = str(row.get("capture_ref") or "")
        capture_path = (runtime_root / capture_ref).resolve()
        _require(
            runtime_root in capture_path.parents and capture_path.is_file(),
            "natural_canary_capture_ref_invalid",
        )
        capture = _load(capture_path)
        _require(
            canonical_digest(capture) == row.get("capture_digest")
            and capture.get("request_id") == row.get("request_id")
            and capture.get("gateway_result", {}).get("raw_response") is not None,
            "natural_canary_capture_digest_or_raw_retention_invalid",
        )
        capture_text = capture_path.read_text(encoding="utf-8").lower()
        _require(
            not any(token in capture_text for token in FORBIDDEN_PRIVATE_TEXT)
            and re.search(r"sk-[a-z0-9_-]{12,}", capture_text) is None,
            "natural_canary_capture_contains_forbidden_secret_surface",
        )
        rubric = row.get("rubric") or {}
        provider_output = row.get("provider_output") or {}
        claim = row.get("claim") or {}
        _require(
            row.get("status") == "pass"
            and row.get("gateway_status") == "ok"
            and row.get("finish_reason") == "stop"
            and rubric.get("pass") is True
            and rubric.get("total") == 10
            and claim.get("provider_free_text_fields") == [],
            "natural_canary_family_result_invalid",
        )
        public_rows.append(
            {
                "request_id": row["request_id"],
                "case_key": claim["case_key"],
                "program_cell_id": claim["program_cell_id"],
                "provider_output": provider_output,
                "provider_output_digest": row["provider_output_digest"],
                "claim_digest": claim["claim_digest"],
                "capture_digest": row["capture_digest"],
                "finish_reason": row["finish_reason"],
                "usage": row["usage"],
                "rubric": rubric,
            }
        )

    total_usage = {
        key: sum(int(row["usage"][key]) for row in public_rows)
        for key in ("input_tokens", "output_tokens", "total_tokens")
    }
    result = {
        "schema_version": "fin_ia_0_1_3_s2_02_three_family_natural_canary_public_result_v1_0",
        "recorded_at": terminal["observed_at"],
        "execution_git_commit": admission["execution_git_commit"],
        "admission_digest": admission["admission_digest"],
        "terminal_result_digest": terminal["terminal_result_digest"],
        "shared_admission_receipt_state": "terminal",
        "provider": {
            "backend": admission["provider"]["backend"],
            "model": admission["provider"]["model"],
            "model_ref": admission["provider"]["model_ref"],
            "base_url": admission["provider"]["base_url"],
            "chat_completions_path": admission["provider"]["chat_completions_path"],
        },
        "execution": {
            "status": terminal["status"],
            "terminal_code": terminal["terminal_code"],
            "provider_calls": terminal["completed_calls"],
            "captures": len(public_rows),
            "retry_count": terminal["retry_count"],
            "fallback_count": terminal["fallback_count"],
            "business_artifact_promotions": terminal["business_artifact_promotions"],
            "skipped_request_ids": terminal["skipped_request_ids"],
            "total_usage": total_usage,
        },
        "family_results": public_rows,
        "disposition": {
            "S2_02": "pass_closed",
            "natural_contract_adherence": "3/3 pass at 10/10",
            "model_capability_failure_established": False,
            "S2_03": "next_context_yield_capacity",
            "S3_dynamic_decision_surface": "not_proven",
            "eight_dimension_research_content_quality": "not_proven",
            "product_acceptance": False,
            "release": False,
        },
        "known_boundary": (
            "This exact-once canary proves natural DeepSeek contract adherence for three "
            "representative alias-only Specialist families. It does not prove context economy, "
            "dynamic 10-20 Cell planning, final Lead/Writer/Verifier research depth, human content "
            "acceptance, product usability or release."
        ),
    }
    return {**result, "record_digest": canonical_digest(result)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admission-path", type=Path, required=True)
    parser.add_argument("--terminal-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = materialize(
        admission_path=args.admission_path.resolve(),
        terminal_path=args.terminal_path.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "output": str(args.output),
        "record_digest": result["record_digest"],
        "calls": result["execution"]["provider_calls"],
        "family_passes": len(result["family_results"]),
        "S2_02": result["disposition"]["S2_02"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
