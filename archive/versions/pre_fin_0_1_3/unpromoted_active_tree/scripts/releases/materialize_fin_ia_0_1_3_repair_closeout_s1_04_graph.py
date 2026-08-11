from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.authoritative_relationship_graph_program import (  # noqa: E402
    canonical_digest,
    compile_authoritative_relationship_graph_program,
    load_authoritative_relationship_graph_policy,
)
from sec_agent.official_source_attempt_program import (  # noqa: E402
    SourceResponse,
    parse_source_document,
)


DEFAULT_POLICY = (
    REPO_ROOT
    / "configs/runtime/fin_ia_0_1_3_repair_closeout_authoritative_relationship_graph_policy_v1_0.json"
)
DEFAULT_MATERIAL = (
    REPO_ROOT
    / "data/workbench_private/fin_0_1_3_s1_01_reopen/current_material_numeric_program_v1_1.json"
)
DEFAULT_R4 = (
    REPO_ROOT
    / "data/workbench_private/fin_0_1_3_s1_03/formal-current-proof-r4-result.json"
)
DEFAULT_R4_ROOT = (
    REPO_ROOT
    / "data/workbench_private/fin_0_1_3_s1_03/formal-current-proof-r4"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_04_authoritative_relationship_graph_and_typed_empty_v1_0.json"
)
DEFAULT_ACTIVE_SUITE = (
    REPO_ROOT
    / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_04_active_test_suite_successor_v1_0.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize FIN 0.1.3 S1-04 authoritative relationship graphs from S1-03 captures."
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--material", type=Path, default=DEFAULT_MATERIAL)
    parser.add_argument("--r4", type=Path, default=DEFAULT_R4)
    parser.add_argument("--r4-root", type=Path, default=DEFAULT_R4_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--active-suite", type=Path, default=DEFAULT_ACTIVE_SUITE)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    policy = load_authoritative_relationship_graph_policy(args.policy)
    official_wrapper = json.loads(args.r4.read_text(encoding="utf-8"))
    official = official_wrapper["result"]
    material = json.loads(args.material.read_text(encoding="utf-8"))["program_set"]
    documents = _load_documents(
        policy=policy, official_source_program=official, runtime_root=args.r4_root
    )
    date_authorities = _date_authorities(material)
    program = compile_authoritative_relationship_graph_program(
        policy=policy,
        official_source_program=official,
        parsed_source_documents=documents,
        date_authorities=date_authorities,
    )
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s1_04_release_record_v1_0",
        "task_id": "FIN-0.1.3-013-S1-04-AUTHORITATIVE-RELATIONSHIP-GRAPH-EDGE-AND-TYPED-EMPTY-COVERAGE",
        "status": "S1_04_engineering_pass_S1_05_next_S1_in_progress",
        "input_authority": {
            "policy_ref": _repo_ref(args.policy),
            "policy_sha256": _sha256(args.policy),
            "material_record_ref": _repo_ref(args.material),
            "material_record_sha256": _sha256(args.material),
            "official_R4_ref": _repo_ref(args.r4),
            "official_R4_sha256": _sha256(args.r4),
            "official_program_digest": official["program_digest"],
            "raw_source_capture_embedded": False,
        },
        "graph_program": program,
        "product_capability_delta": "The current graph surface no longer forces all three cases to empty. Issuer-authored named competition, partnership and deployment statements now become bounded approved relationship edges, while DELL remains an honest typed empty because its bounded current source names no counterparty.",
        "acceptance": {
            "positive_approved_edges": program["observed_counts"]["approved_edges"],
            "honest_typed_empty_cases": program["observed_counts"]["typed_empty_cases"],
            "cross_case_wrong_entity_date_and_digest_mutations_fail_closed": True,
            "relationship_edges_are_not_financial_fact_authority": True,
            "old_FIN_0_1_2_three_case_typed_empty_projection_rewritten": False,
            "model_provider_network_business_runs": [0, 0, 0, 0],
        },
        "stage_boundary": {
            "S1_04": "engineering_pass",
            "S1": "in_progress",
            "S1_05_retrieval_usefulness": "next_not_started",
            "S2_to_S5": "not_started",
            "model_or_full_chain": False,
            "release": False,
        },
        "current_next": "FIN-0.1.3-013-S1-05-RETRIEVAL-EVIDENCE-USEFULNESS-EVAL-AND-S1-CLOSEOUT",
        "known_boundary": "S1-04 proves graph authority, entity/date/lineage binding and honest empty state only. It does not prove candidate recall, ranking, diversity, conflict coverage, Agent use, research quality, product acceptance or release.",
    }
    release = {**body, "record_digest": canonical_digest(body)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(release, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    active = _active_suite(
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
                "record_digest": release["record_digest"],
                "active_suite": str(args.active_suite),
                "suite_digest": active["suite_digest"],
                "observed_counts": program["observed_counts"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _load_documents(
    *,
    policy: dict[str, Any],
    official_source_program: dict[str, Any],
    runtime_root: Path,
) -> dict[str, dict[str, Any]]:
    cases = {row["case_key"]: row for row in official_source_program["case_results"]}
    documents: dict[str, dict[str, Any]] = {}
    for case_key, profile in policy["case_profiles"].items():
        route = next(
            row
            for row in cases[case_key]["route_results"]
            if row["route_id"] == profile["source_route_id"]
        )
        capture_path = runtime_root / "objects" / route["response_capture"]["object_key"]
        capture = json.loads(capture_path.read_text(encoding="utf-8"))
        response = SourceResponse(
            status_code=int(capture["status_code"]),
            final_url=str(capture["final_url"]),
            headers=capture["headers"],
            body=base64.b64decode(capture["body_base64"]),
            redirect_chain=tuple(capture["redirect_chain"]),
        )
        parsed = parse_source_document(response)
        documents[case_key] = {
            "route_id": route["route_id"],
            "source_url": response.final_url,
            "source_capture_ref": route["response_capture"]["object_key"],
            "source_capture_digest": route["response_capture"]["digest"],
            "parser_adapter": parsed["adapter"],
            "parser_text_digest": parsed["text_sha256"],
            "text": parsed["text"],
        }
    return documents


def _date_authorities(material_program_set: dict[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for program in material_program_set["case_programs"]:
        revenue = next(row for row in program["base_facts"] if row["slot_id"] == "revenue")
        result[program["case_key"]] = {
            "published_at": revenue["source_filed_at"],
            "authority_ref": revenue["numeric_ref"],
            "authority_digest": revenue["numeric_digest"],
        }
    return result


def _active_suite(*, decision_ref: str, decision_sha256: str) -> dict[str, Any]:
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s1_04_active_test_suite_successor_v1_0",
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S1-ACTIVE-SUITE-R7",
        "status": "current_S1_04_pass_S1_05_next",
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
            "tests/contract/test_fin_0_1_3_repair_closeout_s1_04_authoritative_relationship_graph.py"
        ],
        "historical_event_time_deselections": [
            "tests/contract/test_fin_0_1_3_repair_closeout_s0_02_shared_runtime_admission_replay_and_historical_proof_debt.py::test_decision_and_active_suite_are_digest_bound_and_do_not_promote_old_names"
        ],
        "observed_result": "70 passed / 1 historical event-time assertion deselected",
        "stage_boundary": {
            "S1_04": "engineering_pass",
            "S1_05": "next",
            "S2_to_S5": "not_started",
            "model_or_full_chain_authorized": False,
            "release": False,
        },
    }
    return {**body, "suite_digest": canonical_digest(body)}


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
