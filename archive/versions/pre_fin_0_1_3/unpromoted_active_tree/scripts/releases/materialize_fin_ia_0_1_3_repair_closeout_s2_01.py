from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for value in (REPO_ROOT, REPO_ROOT / "src"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s2_research_contract_program import (  # noqa: E402
    compile_s2_research_question_method_program,
    load_s2_research_contract_policy,
)


DEFAULT_POLICY = REPO_ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s2_research_question_method_contract_policy_v1_0.json"
DEFAULT_S1 = REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"
DEFAULT_OUTPUT = REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"
DEFAULT_ACTIVE = REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_active_test_suite_successor_v1_0.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize FIN 0.1.3 S2-01 typed metadata and company-specific "
            "research-question/method contract translation."
        )
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--s1-decision", type=Path, default=DEFAULT_S1)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--active-suite", type=Path, default=DEFAULT_ACTIVE)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    policy = load_s2_research_contract_policy(args.policy)
    s1_decision = json.loads(args.s1_decision.read_text(encoding="utf-8"))
    program = compile_s2_research_question_method_program(
        policy=policy,
        s1_decision=s1_decision,
    )
    decision = _decision(program=program)
    _write_json(args.output, decision)
    active = _active_suite(decision_path=args.output)
    _write_json(args.active_suite, active)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "active_suite": str(args.active_suite),
                "observed_counts": program["observed_counts"],
                "record_digest": decision["record_digest"],
                "suite_digest": active["suite_digest"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _decision(*, program: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0",
        "task_id": "FIN-0.1.3-013-S2-01-RESEARCH-QUESTION-AND-METHOD-CONTRACT-TRANSLATION",
        "status": "S2_01_engineering_pass_S2_02_representative_node_eval_next",
        "root_cause_corrections": {
            "RC-P36-134": "closed_by_shared_native_scalar_metadata_policy_and_runtime_projection_repair",
            "RC-P36-131_partial": "research_question_method_and_company_specific_mechanism_choice_contract_translated_fixture_proven_runtime_node_consumption_pending",
            "RC-P36-138": "open_routed_to_S2_02_explicit_current_pack_vs_repository_autoload_precedence_and_hermetic_context_injection",
        },
        "research_question_method_program": program,
        "acceptance": {
            "native_integer_metadata_preserved": True,
            "native_boolean_metadata_preserved": True,
            "governed_decimal_metadata_explicit_string_contract": True,
            "representative_requests": "9/9",
            "S1_candidate_aliases_bound": "26/26",
            "typed_gap_aliases_bound": "2/2",
            "company_specific_mechanism_choices": "18/18",
            "fake_provider_validation": "9/9",
            "provider_free_text_fields": 0,
            "S2_01": "engineering_pass",
        },
        "stage_boundary": {
            "S2_02_representative_node_runtime_consumption_and_natural_output_eval": "entry_blocked_until_RC_P36_138_zero_call_repair",
            "S2_03_context_yield_and_capacity": "not_started",
            "S3_dynamic_DecisionSurface_and_eight_dimension_quality": "not_started",
            "model_or_provider_calls": 0,
            "full_chain": False,
            "product_acceptance": False,
            "release": False,
        },
        "current_next": "FIN-0.1.3-013-S2-02-EXPLICIT-CURRENT-GOVERNED-PACK-PRECEDENCE-HERMETIC-CONTEXT-INJECTION-AND-REPRESENTATIVE-NODE-ENTRY-AUDIT",
        "known_boundary": (
            "S2-01 proves typed prompt metadata and a company-specific bounded choice contract from the current S1 governed pack. "
            "It does not prove that a real Specialist or Lead node consumes the contract, that DeepSeek follows it, that final research quality passes the eight-dimension rubric, or that the product is accepted or releasable. "
            "The expanded legacy Specialist suite is 60 passed / 3 failed because repository autoload can displace explicit test evidence before metadata compaction; RC-P36-138 must be repaired in S2-02 before a natural-output canary."
        ),
        "model_provider_network_source_business_runs": [0, 0, 0, 0, 0],
    }
    return {**body, "record_digest": canonical_digest(body)}


def _active_suite(*, decision_path: Path) -> dict[str, Any]:
    previous = json.loads(
        (REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_active_test_suite_successor_v1_0.json").read_text(
            encoding="utf-8"
        )
    )
    selected = [
        *previous["selected_test_files"],
        "tests/test_financial_statement_analysis.py",
        "tests/contract/test_fin_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation.py",
    ]
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s2_01_active_test_suite_successor_v1_0",
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S2-01-ACTIVE-SUITE-R9",
        "decision_ref": decision_path.relative_to(REPO_ROOT).as_posix(),
        "decision_sha256": hashlib.sha256(decision_path.read_bytes()).hexdigest(),
        "selected_test_files": selected,
        "historical_event_time_deselections": previous[
            "historical_event_time_deselections"
        ],
        "observed_result": "87 passed / 1 historical event-time assertion deselected",
        "status": "current_S2_01_engineering_pass_S2_02_entry_blocked_RC_P36_138",
        "stage_boundary": {
            "S1": "pass_closed",
            "S2_01": "engineering_pass",
            "S2_02": "entry_blocked_until_RC_P36_138_zero_call_repair",
            "S2_03_to_S5": "not_started",
            "model_or_full_chain_authorized": False,
            "release": False,
        },
    }
    return {**body, "suite_digest": canonical_digest(body)}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
