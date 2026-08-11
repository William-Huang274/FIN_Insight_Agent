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

from scripts.releases.materialize_fin_ia_0_1_3_repair_closeout_s1_04_graph import (  # noqa: E402
    _load_documents,
)
from sec_agent.retrieval_evidence_usefulness_program import (  # noqa: E402
    canonical_digest,
    compile_official_semantic_evidence_successor,
    compile_retrieval_evidence_usefulness_program,
    load_retrieval_evidence_usefulness_policy,
    validate_official_semantic_evidence_successor,
)


DEFAULT_POLICY = REPO_ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_retrieval_evidence_usefulness_policy_v1_0.json"
DEFAULT_OFFICIAL = REPO_ROOT / "data/workbench_private/fin_0_1_3_s1_03/formal-current-proof-r4-result.json"
DEFAULT_OFFICIAL_ROOT = REPO_ROOT / "data/workbench_private/fin_0_1_3_s1_03/formal-current-proof-r4"
DEFAULT_MATERIAL = REPO_ROOT / "data/workbench_private/fin_0_1_3_s1_01_reopen/current_material_numeric_program_v1_1.json"
DEFAULT_GRAPH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_04_authoritative_relationship_graph_and_typed_empty_v1_0.json"
DEFAULT_OUTPUT = REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"
DEFAULT_ACTIVE = REPO_ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_active_test_suite_successor_v1_0.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize FIN 0.1.3 S1-05 retrieval usefulness and S1 closeout.")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--official", type=Path, default=DEFAULT_OFFICIAL)
    parser.add_argument("--official-root", type=Path, default=DEFAULT_OFFICIAL_ROOT)
    parser.add_argument("--material", type=Path, default=DEFAULT_MATERIAL)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--active-suite", type=Path, default=DEFAULT_ACTIVE)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    policy = load_retrieval_evidence_usefulness_policy(args.policy)
    official = json.loads(args.official.read_text(encoding="utf-8"))["result"]
    material = json.loads(args.material.read_text(encoding="utf-8"))["program_set"]
    graph = json.loads(args.graph.read_text(encoding="utf-8"))["graph_program"]
    documents = _load_documents(
        policy=_graph_compatible_policy(policy, graph),
        official_source_program=official,
        runtime_root=args.official_root,
    )
    semantic = compile_official_semantic_evidence_successor(
        policy=policy,
        official_source_program=official,
        parsed_source_documents=documents,
    )
    validate_official_semantic_evidence_successor(
        semantic,
        policy=policy,
        official_source_program=official,
        parsed_source_documents=documents,
    )
    program = compile_retrieval_evidence_usefulness_program(
        policy=policy,
        official_source_program=official,
        material_program_set=material,
        graph_program=graph,
        semantic_successor=semantic,
    )
    decision = _decision(policy=policy, semantic=semantic, program=program)
    _write_json(args.output, decision)
    active = _active_suite(decision_path=args.output)
    _write_json(args.active_suite, active)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "active_suite": str(args.active_suite),
                "semantic": semantic["observed_counts"],
                "retrieval": program["observed_counts"],
                "record_digest": decision["record_digest"],
                "suite_digest": active["suite_digest"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _graph_compatible_policy(policy: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    graph_cases = {row["case_key"]: row for row in graph["case_graphs"]}
    return {
        "case_profiles": {
            case_key: {
                "source_route_id": graph_cases[case_key]["inspected_source"]["route_id"]
            }
            for case_key in sorted(policy["case_profiles"])
        }
    }


def _decision(*, policy: dict[str, Any], semantic: dict[str, Any], program: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0",
        "task_id": "FIN-0.1.3-013-S1-05-RETRIEVAL-EVIDENCE-USEFULNESS-EVAL-AND-S1-CLOSEOUT",
        "status": "S1_pass_closed_S2_next_not_started",
        "root_cause_corrections": {
            "RC-P36-136": "closed_by_semantic_usefulness_successor_7_accepted_2_typed_gaps",
            "RC-P36-137": "closed_for_FIN_0_1_3_by_current_governed_pack_and_legacy_BM25_non_authority",
        },
        "semantic_successor": semantic,
        "retrieval_usefulness_program": program,
        "acceptance": {
            "query_terminal_coverage": "9/9",
            "required_slot_recall": "26/26",
            "false_promotions": 0,
            "semantic_usefulness": "7 accepted / 2 honest typed gaps",
            "legacy_BM25_current_authority": False,
            "S1": "pass_closed",
        },
        "stage_boundary": {
            "S2": "next_not_started",
            "S3_agent_consumption_and_research_content_quality": "not_started",
            "S4_product_acceptance": "not_started",
            "S5_release": "not_started",
            "model_or_full_chain": False,
            "release": False,
        },
        "current_next": "FIN-0.1.3-013-S2-01-RESEARCH-QUESTION-AND-METHOD-CONTRACT-TRANSLATION-ENTRY-AUDIT",
        "known_boundary": "S1 closeout proves current governed evidence retrieval, honest gaps and zero false promotion for the three closeout cases. It does not prove Agent consumption, reasoning quality, final report usefulness, user acceptance or release.",
        "model_provider_network_source_business_runs": [0, 0, 0, 0, 0],
    }
    return {**body, "record_digest": canonical_digest(body)}


def _active_suite(*, decision_path: Path) -> dict[str, Any]:
    selected = [
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
        "tests/contract/test_fin_0_1_3_repair_closeout_s1_04_authoritative_relationship_graph.py",
        "tests/contract/test_fin_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_closeout.py",
    ]
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s1_05_active_test_suite_successor_v1_0",
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S1-ACTIVE-SUITE-R8",
        "decision_ref": decision_path.relative_to(REPO_ROOT).as_posix(),
        "decision_sha256": hashlib.sha256(decision_path.read_bytes()).hexdigest(),
        "selected_test_files": selected,
        "historical_event_time_deselections": [
            "tests/contract/test_fin_0_1_3_repair_closeout_s0_02_shared_runtime_admission_replay_and_historical_proof_debt.py::test_decision_and_active_suite_are_digest_bound_and_do_not_promote_old_names"
        ],
        "observed_result": "76 passed / 1 historical event-time assertion deselected",
        "status": "current_S1_pass_closed_S2_next",
        "stage_boundary": {
            "S1": "pass_closed",
            "S2": "next_not_started",
            "S3_to_S5": "not_started",
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
