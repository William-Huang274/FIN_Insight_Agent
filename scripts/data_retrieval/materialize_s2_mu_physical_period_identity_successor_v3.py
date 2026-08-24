from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC_ROOT)]

from financial_facts.executor import execute_fact_lookup  # noqa: E402
from retrieval.query_plan import canonical_digest  # noqa: E402
from scripts.data_retrieval.materialize_s2_mu_physical_period_identity_successor import (  # noqa: E402
    AUDIT_RESEARCH_AS_OFS,
    EXPECTED_CURRENT_FACT_INVENTORY,
    EXPECTED_CURRENT_Q3_PERIODS,
    ORIGINAL_REQUEST_ID,
    _audit_lookup,
    _bound_ref,
    _fact_inventory,
    _original_lookup,
    _read_json,
    _resolve,
    _sha256,
    _write_json,
)
from scripts.data_retrieval.materialize_s2_mu_physical_period_identity_successor_v2 import (  # noqa: E402
    _no_origin_probe,
    _origin_population,
)


PREDECESSOR_RESULT = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_mu_physical_period_identity_successor_result_v1_1.json"
)
SELF_AUDIT_FAILURE = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_unverified_origin_identity_self_audit_failure_v1_0.json"
)
FAILED_ATTEMPT_RESULT = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_mu_physical_period_identity_successor_result_v1_2.json"
)
OUTPUT = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_mu_physical_period_identity_successor_result_v1_3.json"
)
SQLITE = (
    "data/workbench_private/fin_0_1_3_s2_company_financial_fact_mart/v1/"
    "company_financial_facts.sqlite"
)
EXPECTED_POPULATION = {
    "physical_groups": 728,
    "groups_without_timely_origin": 40,
    "groups_without_timely_origin_and_one_unanimous_label": 34,
    "unanimous_groups_with_period_role_and_label_inconsistency": 19,
    "quarter_discrete_labelled_FY": 12,
    "fiscal_ytd_labelled_FY": 7,
}
FAILED_ATTEMPT_SHA256 = (
    "2a0c37b50bbc82c2d0897c39bbb20b7fb657421290006aad8d6df2e452b988a6"
)
FAILED_ATTEMPT_DIGEST = (
    "0dd624b28f88d020b98c334a90c210429ae307d8f5a530c1085d9ea0ddbff41d"
)
FAILED_MATERIALIZER_SHA256 = (
    "36e94da50536b2bab1be34ef481d4f5e6346731f0d84b53b5f88121474d7ba51"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the strict timely-origin S2 successor after "
            "preserving the v1.2 receipt-shape failure."
        )
    )
    parser.add_argument("--sqlite", default=SQLITE)
    parser.add_argument("--predecessor-result", default=PREDECESSOR_RESULT)
    parser.add_argument("--self-audit-failure", default=SELF_AUDIT_FAILURE)
    parser.add_argument("--failed-attempt-result", default=FAILED_ATTEMPT_RESULT)
    parser.add_argument("--output", default=OUTPUT)
    return parser.parse_args()


def _failure_scan_matches(
    failure: dict[str, object], population: dict[str, int], sqlite_sha: str
) -> bool:
    scan = failure.get("bound_mart_scan")
    if not isinstance(scan, dict):
        return False
    return scan == {
        "sqlite_ref": SQLITE,
        "sqlite_sha256": sqlite_sha,
        "physical_groups": population["physical_groups"],
        "groups_without_timely_origin": population[
            "groups_without_timely_origin"
        ],
        "groups_without_timely_origin_and_one_unanimous_label": population[
            "groups_without_timely_origin_and_one_unanimous_label"
        ],
        "unanimous_groups_with_period_role_and_label_inconsistency": population[
            "unanimous_groups_with_period_role_and_label_inconsistency"
        ],
        "inconsistent_shapes": {
            "quarter_discrete_labelled_FY": population[
                "quarter_discrete_labelled_FY"
            ],
            "fiscal_ytd_labelled_FY": population["fiscal_ytd_labelled_FY"],
        },
    }


def main() -> int:
    args = parse_args()
    sqlite_path = _resolve(args.sqlite)
    predecessor_path = _resolve(args.predecessor_result)
    failure_path = _resolve(args.self_audit_failure)
    failed_attempt_path = _resolve(args.failed_attempt_result)
    predecessor = _read_json(predecessor_path)
    failure = _read_json(failure_path)
    failed_attempt = _read_json(failed_attempt_path)

    current = execute_fact_lookup(sqlite_path, _original_lookup())
    current_facts = [fact.as_dict() for fact in current.facts]
    current_q3_periods = {
        (
            fact["fiscal_year"],
            fact["fiscal_period"],
            fact["period_start"],
            fact["period_end"],
        )
        for fact in current_facts
        if fact["period_role"] == "quarter_discrete"
    }
    audit_replay = []
    audit_results = []
    for research_as_of in AUDIT_RESEARCH_AS_OFS:
        result = execute_fact_lookup(sqlite_path, _audit_lookup(research_as_of))
        audit_results.append(result)
        audit_replay.append(
            {"research_as_of": research_as_of, "result": result.as_dict()}
        )
    no_origin = execute_fact_lookup(sqlite_path, _no_origin_probe())
    population = _origin_population(sqlite_path)
    no_origin_conflicts = (
        no_origin.typed_conflict.get("conflicts")
        if no_origin.typed_conflict
        else []
    )
    failed_refs = failed_attempt.get("implementation_refs")
    checks = {
        "predecessor_result_preserved_and_bound": (
            predecessor.get("status")
            == "s2_mu_physical_period_identity_successor_pass"
            and predecessor.get("result_digest")
            == "6823104ce6e99688f18173215e585261e68c8601f969f7a05930bc377461abd7"
            and _sha256(predecessor_path)
            == "a5bd60c47beea65972aab2fa6f74d309d598f85c84aa419ab181a917908a72c1"
        ),
        "self_audit_failure_preserved_and_bound": (
            failure.get("status") == "failed_preserved_successor_required"
            and failure.get("bound_predecessor", {}).get("commit")
            == "5f35b116ba8e906a7e0c73ed1972679699c6ab1c"
            and _failure_scan_matches(
                failure, population, _sha256(sqlite_path)
            )
        ),
        "failed_v1_2_receipt_shape_attempt_preserved_and_bound": (
            _sha256(failed_attempt_path) == FAILED_ATTEMPT_SHA256
            and failed_attempt.get("result_digest") == FAILED_ATTEMPT_DIGEST
            and failed_attempt.get("status")
            == "s2_mu_strict_timely_origin_identity_successor_failed"
            and failed_attempt.get("checks", {}).get(
                "self_audit_failure_preserved_and_bound"
            )
            is False
            and all(
                value is True
                for key, value in failed_attempt.get("checks", {}).items()
                if key != "self_audit_failure_preserved_and_bound"
            )
            and isinstance(failed_refs, list)
            and {
                "path": (
                    "scripts/data_retrieval/"
                    "materialize_s2_mu_physical_period_identity_successor_v2.py"
                ),
                "sha256": FAILED_MATERIALIZER_SHA256,
            }
            in failed_refs
        ),
        "original_request_exact_fact_inventory_preserved": (
            current.status == "resolved"
            and len(current_facts) == 3
            and _fact_inventory(current_facts) == EXPECTED_CURRENT_FACT_INVENTORY
            and current_q3_periods == EXPECTED_CURRENT_Q3_PERIODS
        ),
        "six_asof_timely_origin_identity_preserved": all(
            result.status == "resolved"
            and len(result.facts) == 1
            and result.facts[0].fiscal_year == 2023
            and result.facts[0].fiscal_period == "Q1"
            for result in audit_results
        ),
        "unanimous_no_origin_group_fails_closed": (
            no_origin.status == "typed_conflict"
            and not no_origin.facts
            and len(no_origin_conflicts) == 1
            and no_origin_conflicts[0].get("code")
            == "typed_fact_physical_period_identity_source_unavailable"
        ),
        "full_mart_counterexample_population_preserved": (
            population == EXPECTED_POPULATION
        ),
    }
    status = (
        "s2_mu_strict_timely_origin_identity_successor_pass"
        if all(checks.values())
        else "s2_mu_strict_timely_origin_identity_successor_failed"
    )
    unsigned = {
        "schema_version": (
            "fin_ia_s2_mu_physical_period_identity_successor_result_v1_3"
        ),
        "status": status,
        "recorded_at": "2026-08-24",
        "issue_ids": [
            "RC-S2-013-unverified-origin-unanimity-is-not-period-identity-authority",
            "RC-S2-014-strict-origin-successor-receipt-shape-mismatch",
        ],
        "scope": "executor_only_strict_timely_origin_zero_call_successor",
        "bound_inputs": {
            "sqlite": _bound_ref(sqlite_path),
            "predecessor_result": _bound_ref(predecessor_path),
            "self_audit_failure": _bound_ref(failure_path),
            "failed_v1_2_attempt": _bound_ref(failed_attempt_path),
            "fact_request_id": ORIGINAL_REQUEST_ID,
        },
        "implementation_refs": [
            _bound_ref(ROOT / "src/financial_facts/executor.py"),
            _bound_ref(
                ROOT
                / "scripts/data_retrieval/"
                "materialize_s2_mu_physical_period_identity_successor_v2.py"
            ),
            _bound_ref(
                ROOT
                / "scripts/data_retrieval/"
                "materialize_s2_mu_physical_period_identity_successor_v3.py"
            ),
        ],
        "failure_chain": {
            "v1_2_failure_class": "receipt_shape_comparison_bug",
            "v1_2_substantive_executor_checks_passed": True,
            "v1_2_calls": {"network": 0, "provider": 0, "model": 0},
            "v1_2_was_not_overwritten": True,
        },
        "method": {
            "period_identity_authority": (
                "unique same-physical-period 10-Q accepted within 45 days or "
                "10-K accepted within 90 days"
            ),
            "no_timely_origin_policy": (
                "typed_fail_closed_even_when_all_late_copy_labels_agree"
            ),
            "numeric_vintage_policy": (
                "later value remains eligible only under the admitted identity"
            ),
            "mart_superseded_by_pointer_used_as_period_identity": False,
        },
        "full_mart_origin_population": population,
        "original_request_after": current.as_dict(),
        "timely_origin_six_asof_replay": audit_replay,
        "no_origin_counterexample_after": no_origin.as_dict(),
        "checks": checks,
        "calls": {"network": 0, "provider": 0, "model": 0},
        "authority": {
            "numeric_fact_authority_is_source_bound_executor_only": True,
            "s2_stage_qualification_authorized": False,
            "qualified_human_review_pass": False,
            "publication_or_release_authorized": False,
        },
        "known_boundary": (
            "The bound MU current request and six-asof group have timely "
            "origins. Forty mart groups do not and now remain unavailable. "
            "This executor successor does not rebuild the mart or close the "
            "remaining product-level S2 bridges."
        ),
    }
    output = {**unsigned, "result_digest": canonical_digest(unsigned)}
    _write_json(_resolve(args.output), output)
    print(
        json.dumps(
            {
                "status": status,
                "checks": checks,
                "population": population,
                "calls": output["calls"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status.endswith("_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
