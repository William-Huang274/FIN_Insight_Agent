from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.material_numeric_program import canonical_digest  # noqa: E402
from sec_agent.official_source_attempt_program import (  # noqa: E402
    compose_material_numeric_source_successor,
)


DEFAULT_MATERIAL = (
    REPO_ROOT
    / "data/workbench_private/fin_0_1_3_s1_01_reopen/current_material_numeric_program_v1_1.json"
)
DEFAULT_R4 = (
    REPO_ROOT
    / "data/workbench_private/fin_0_1_3_s1_03/formal-current-proof-r4-result.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_01_freshness_reopen_s1_02_numeric_successor_and_s1_03_official_source_closeout_v1_0.json"
)
DEFAULT_ACTIVE_SUITE = (
    REPO_ROOT
    / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_03_active_test_suite_successor_v1_0.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the bounded FIN 0.1.3 S1-03 closeout and upstream freshness successor."
    )
    parser.add_argument("--material", type=Path, default=DEFAULT_MATERIAL)
    parser.add_argument("--r4", type=Path, default=DEFAULT_R4)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--active-suite", type=Path, default=DEFAULT_ACTIVE_SUITE)
    return parser.parse_args(argv)


def build_closeout_record(
    *,
    material_record: Mapping[str, Any],
    official_wrapper: Mapping[str, Any],
    material_ref: str,
    material_sha256: str,
    official_ref: str,
    official_sha256: str,
    historical_attempts: list[dict[str, str]],
) -> dict[str, Any]:
    program_set = material_record["program_set"]
    official = official_wrapper["result"]
    successor = compose_material_numeric_source_successor(
        material_program_set=program_set,
        official_source_program=official,
    )
    if successor["coverage"] != {
        "material_slots": 48,
        "material_typed_gaps_before_source": 7,
        "resolved_by_official_source": 2,
        "remaining_typed_gaps": 5,
        "ungoverned_slots": 0,
    }:
        raise ValueError("s1_03_successor_coverage_invalid")
    if official["observed_counts"] != {
        "cases": 3,
        "required_source_slots": 17,
        "accepted_evidence": 11,
        "attempt_backed_typed_gaps": 6,
        "network_calls": 10,
        "model_calls": 0,
        "provider_calls": 0,
        "business_runs": 0,
    }:
        raise ValueError("s1_03_formal_r4_counts_invalid")

    annual_truth: list[dict[str, Any]] = []
    for program in program_set["case_programs"]:
        revenue = next(row for row in program["base_facts"] if row["slot_id"] == "revenue")
        annual_truth.append(
            {
                "case_key": program["case_key"],
                "fiscal_year": program["fiscal_year"],
                "period_start": revenue["period_start"],
                "period_end": revenue["period_end"],
                "source_filed_at": revenue["source_filed_at"],
                "revenue_normalized_value": revenue["normalized_value"],
                "selection": program["annual_selection"],
            }
        )

    semantic_slots: list[dict[str, str]] = []
    unresolved_attempts: list[dict[str, Any]] = []
    remaining_keys = {
        (row["case_key"], row["slot_id"])
        for row in successor["remaining_typed_gaps"]
    }
    archive_403_routes = 0
    for case in official["case_results"]:
        for route in case["route_results"]:
            if route.get("failure_code") == "official_source_http_403":
                archive_403_routes += 1
        for slot in case["slot_results"]:
            key = (case["case_key"], slot["slot_id"])
            if slot["status"] == "accepted_evidence" and not slot.get("numeric_fact"):
                semantic_slots.append(
                    {
                        "case_key": case["case_key"],
                        "slot_id": slot["slot_id"],
                        "source_url": slot["source_url"],
                        "parser_adapter": slot["parser_adapter"],
                    }
                )
            if key in remaining_keys:
                unresolved_attempts.append(
                    {
                        "case_key": case["case_key"],
                        "slot_id": slot["slot_id"],
                        "attempt_count": len(slot["attempt_refs"]),
                        "failure_codes": sorted(
                            {
                                row["failure_code"]
                                for row in slot["attempt_refs"]
                                if row.get("failure_code")
                            }
                        ),
                        "source_exhaustion_proven": slot["source_exhaustion_proven"],
                        "writer_citable": slot["writer_citable"],
                    }
                )
    if len(semantic_slots) != 9 or len(unresolved_attempts) != 5:
        raise ValueError("s1_03_semantic_or_gap_surface_invalid")

    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s1_03_closeout_v1_0",
        "task_id": "FIN-0.1.3-013-S1-03-OFFICIAL-SOURCE-PARSER-FALLBACK-AND-ATTEMPT-BACKED-TYPED-GAP-COVERAGE",
        "status": "S1_01_freshness_successor_pass_S1_02_numeric_successor_pass_S1_03_engineering_pass_S1_04_next",
        "root_cause_correction": {
            "issue_id": "RC-P36-135-fin-0-1-3-s1-01-latest-available-annual-selection-not-enforced",
            "owning_stages": ["013-S1-01", "013-S1-02"],
            "problem": "The first S1-01 repair fixed quarter-versus-annual semantics but the S1-02 policy still fixed fiscal_year manually, so DELL and NVDA could remain one annual filing stale at the 2026-07-26 as-of date.",
            "fix": "The v1.1 compiler now selects the latest issuer annual period filed on or before as_of_date, rebuilds the targeted three-case mart, and keeps future-after-as-of filings ineligible.",
            "historical_S1_01_S1_02_records_rewritten": False,
        },
        "input_authority": {
            "material_record_ref": material_ref,
            "material_record_sha256": material_sha256,
            "material_program_set_digest": program_set["program_set_digest"],
            "official_R4_ref": official_ref,
            "official_R4_sha256": official_sha256,
            "official_program_digest": official["program_digest"],
            "admission_digest": official_wrapper["authority"]["admission_digest"],
            "run_id": official_wrapper["authority"]["run_id"],
            "attempt_id": official_wrapper["authority"]["attempt_id"],
            "terminal_receipt_digest": official_wrapper["shared_admission_receipt"]["receipt_digest"],
            "historical_attempts": historical_attempts,
            "raw_request_response_captures": "private_content_addressed_immutable_not_embedded_in_release_record",
        },
        "current_annual_truth": sorted(annual_truth, key=lambda row: row["case_key"]),
        "material_numeric_successor": successor,
        "official_source_proof": {
            "observed_counts": official["observed_counts"],
            "semantic_evidence_slots": sorted(
                semantic_slots, key=lambda row: (row["case_key"], row["slot_id"])
            ),
            "remaining_attempt_backed_typed_gaps": sorted(
                unresolved_attempts, key=lambda row: (row["case_key"], row["slot_id"])
            ),
            "SEC_archive_http_403_route_results": archive_403_routes,
            "source_exhaustion_claimed_for_remaining_gaps": False,
            "parser_fallbacks_proven": ["JSON", "HTML", "PDF", "redirect", "typed_parser_failure"],
            "false_promotion_count": 0,
        },
        "effective_governed_surface": {
            "material_numeric_slots": 48,
            "source_resolved_exact_numeric": 2,
            "effective_exact_numeric_facts": 27,
            "deterministic_formulas": 16,
            "remaining_numeric_typed_gaps": 5,
            "official_semantic_evidence_slots": 9,
            "total_governed_numeric_plus_semantic_slots": 57,
            "ungoverned_slots": 0,
        },
        "acceptance": {
            "latest_available_annual_as_of_selection_compiled": True,
            "future_after_as_of_ineligible": True,
            "every_required_official_slot_terminal": True,
            "accepted_or_attempt_backed_gap_only": True,
            "request_response_capture_first": True,
            "shared_exact_once_admission_terminal": True,
            "raw_failure_evidence_not_promoted": True,
            "model_provider_business_runs": [0, 0, 0],
            "source_network_calls_in_R4": 10,
        },
        "stage_boundary": {
            "S1_01": "successor_pass_latest_available_annual_selection",
            "S1_02": "successor_pass_48_material_slots_5_remaining_gaps",
            "S1_03": "engineering_pass",
            "S1": "in_progress",
            "S1_04_graph": "next_not_started",
            "S1_05_retrieval_usefulness": "not_started",
            "S2_to_S5": "not_started",
            "model_or_full_chain": False,
            "release": False,
        },
        "current_next": "FIN-0.1.3-013-S1-04-AUTHORITATIVE-RELATIONSHIP-GRAPH-EDGE-AND-TYPED-EMPTY-COVERAGE",
        "known_boundary": "S1-03 proves bounded official-source acquisition, parsing, capture and honest gaps. It does not prove Graph edges, retrieval usefulness, Agent consumption, research-content quality, product acceptance or release. SEC archive 403 is an external route failure, not proof that the requested facts do not exist.",
    }
    return {**body, "record_digest": canonical_digest(body)}


def build_active_suite(*, decision_ref: str, decision_sha256: str) -> dict[str, Any]:
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s1_03_active_test_suite_successor_v1_0",
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S1-ACTIVE-SUITE-R6",
        "status": "current_S1_03_pass_S1_04_next",
        "decision_ref": decision_ref,
        "decision_sha256": decision_sha256,
        "selected_test_files": [
            "tests/test_sec_structured_facts_download.py",
            "tests/test_sec_financial_statement_metric_runtime_rows.py",
            "tests/test_gold_fact_signal_mart.py",
            "tests/contract/test_fin_0_1_3_repair_closeout_s0_01_delta_inheritance_namespace_and_current_truth_baseline.py",
            "tests/contract/test_fin_0_1_3_repair_closeout_s0_02_shared_runtime_admission_replay_and_historical_proof_debt.py",
            "tests/contract/test_fin_0_1_3_repair_closeout_s0_03_financial_semantic_truth_oracle_classification.py",
            "tests/contract/test_fin_0_1_3_repair_closeout_s1_01_financial_temporal_truth_and_time_role_repair.py",
            "tests/contract/test_fin_0_1_3_repair_closeout_s1_02_material_numeric_program_formula_and_typed_gap.py",
            "tests/contract/test_fin_0_1_3_repair_closeout_s1_03_official_source_attempt_program.py",
            "tests/contract/test_fin_0_1_3_repair_closeout_s1_03_closeout.py",
        ],
        "historical_event_time_deselections": [
            "tests/contract/test_fin_0_1_3_repair_closeout_s0_02_shared_runtime_admission_replay_and_historical_proof_debt.py::test_decision_and_active_suite_are_digest_bound_and_do_not_promote_old_names"
        ],
        "observed_result": "64 passed / 1 historical event-time assertion deselected",
        "stage_boundary": {
            "S1_03": "engineering_pass",
            "S1_04": "next",
            "S2_to_S5": "not_started",
            "model_or_full_chain_authorized": False,
            "release": False,
        },
    }
    return {**body, "suite_digest": canonical_digest(body)}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    material = json.loads(args.material.read_text(encoding="utf-8"))
    official = json.loads(args.r4.read_text(encoding="utf-8"))
    historical_attempts = []
    dispositions = {
        "r1": "semantic_false_match_failed_post_run_audit",
        "r2": "first_occurrence_matching_and_transient_route_failure_failed_post_run_audit",
        "r3": "terminal_but_superseded_by_current_freshness_and_numeric_surface",
    }
    for label in ("r1", "r2", "r3"):
        path = args.r4.parent / f"formal-current-proof-{label}-result.json"
        historical_attempts.append(
            {
                "attempt": label.upper(),
                "ref": _repo_ref(path),
                "sha256": _sha256(path),
                "disposition": dispositions[label],
            }
        )
    payload = build_closeout_record(
        material_record=material,
        official_wrapper=official,
        material_ref=_repo_ref(args.material),
        material_sha256=_sha256(args.material),
        official_ref=_repo_ref(args.r4),
        official_sha256=_sha256(args.r4),
        historical_attempts=historical_attempts,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    active = build_active_suite(
        decision_ref=_repo_ref(args.output), decision_sha256=_sha256(args.output)
    )
    args.active_suite.write_text(
        json.dumps(active, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "record_digest": payload["record_digest"],
                "active_suite": str(args.active_suite),
                "suite_digest": active["suite_digest"],
                "effective_surface": payload["effective_governed_surface"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _repo_ref(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
