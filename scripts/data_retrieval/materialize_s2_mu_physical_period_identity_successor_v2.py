from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC_ROOT)]

from financial_facts.executor import FactLookup, execute_fact_lookup  # noqa: E402
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


PREDECESSOR_RESULT = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_mu_physical_period_identity_successor_result_v1_1.json"
)
SELF_AUDIT_FAILURE = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_unverified_origin_identity_self_audit_failure_v1_0.json"
)
OUTPUT = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_mu_physical_period_identity_successor_result_v1_2.json"
)
SQLITE = (
    "data/workbench_private/fin_0_1_3_s2_company_financial_fact_mart/v1/"
    "company_financial_facts.sqlite"
)
_MAX_LAG = {"10-Q": 45, "10-K": 90}


def _no_origin_probe() -> FactLookup:
    return FactLookup(
        fact_request_id="AUDIT::DELL-QD-WITHOUT-TIMELY-ORIGIN",
        ticker="DELL",
        metric_id="revenue",
        research_as_of="2026-08-06",
        period={
            "start_date": "2022-01-29",
            "end_date": "2022-04-29",
            "fiscal_years": [2023],
        },
        granularity="quarter_discrete",
        requested_unit="reported_source_unit",
        unit_family="currency",
    )


def _origin_population(sqlite_path: Path) -> dict[str, int]:
    uri = sqlite_path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        rows = [
            dict(row)
            for row in connection.execute(
                "SELECT ticker, metric_id, period_start, period_end, "
                "period_role, unit, fiscal_year, fiscal_period, form, "
                "accepted_at FROM company_fact_observations"
            ).fetchall()
        ]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(
            (
                row["ticker"],
                row["metric_id"],
                row["period_start"],
                row["period_end"],
                row["period_role"],
                row["unit"],
            ),
            [],
        ).append(row)

    without_origin = 0
    unanimous_without_origin = 0
    role_label_inconsistent = 0
    quarter_discrete_fy = 0
    fiscal_ytd_fy = 0
    for key, values in groups.items():
        timely = []
        for row in values:
            maximum_lag = _MAX_LAG.get(str(row["form"]))
            if maximum_lag is None:
                continue
            lag = (
                date.fromisoformat(str(row["accepted_at"])[:10])
                - date.fromisoformat(str(row["period_end"]))
            ).days
            if 0 <= lag <= maximum_lag:
                timely.append(row)
        if timely:
            continue
        without_origin += 1
        labels = {
            (row["fiscal_year"], row["fiscal_period"]) for row in values
        }
        if len(labels) != 1:
            continue
        unanimous_without_origin += 1
        fiscal_period = next(iter(labels))[1]
        if key[4] == "quarter_discrete" and fiscal_period == "FY":
            quarter_discrete_fy += 1
            role_label_inconsistent += 1
        elif key[4] == "fiscal_ytd" and fiscal_period == "FY":
            fiscal_ytd_fy += 1
            role_label_inconsistent += 1
    return {
        "physical_groups": len(groups),
        "groups_without_timely_origin": without_origin,
        "groups_without_timely_origin_and_one_unanimous_label": (
            unanimous_without_origin
        ),
        "unanimous_groups_with_period_role_and_label_inconsistency": (
            role_label_inconsistent
        ),
        "quarter_discrete_labelled_FY": quarter_discrete_fy,
        "fiscal_ytd_labelled_FY": fiscal_ytd_fy,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the strict timely-origin S2 successor."
    )
    parser.add_argument("--sqlite", default=SQLITE)
    parser.add_argument("--predecessor-result", default=PREDECESSOR_RESULT)
    parser.add_argument("--self-audit-failure", default=SELF_AUDIT_FAILURE)
    parser.add_argument("--output", default=OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sqlite_path = _resolve(args.sqlite)
    predecessor_path = _resolve(args.predecessor_result)
    failure_path = _resolve(args.self_audit_failure)
    predecessor = _read_json(predecessor_path)
    failure = _read_json(failure_path)

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
            and failure.get("bound_mart_scan") == {
                "sqlite_ref": SQLITE,
                "sqlite_sha256": _sha256(sqlite_path),
                **population,
                "inconsistent_shapes": {
                    "quarter_discrete_labelled_FY": 12,
                    "fiscal_ytd_labelled_FY": 7,
                },
            }
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
        "full_mart_counterexample_population_preserved": population
        == {
            "physical_groups": 728,
            "groups_without_timely_origin": 40,
            "groups_without_timely_origin_and_one_unanimous_label": 34,
            "unanimous_groups_with_period_role_and_label_inconsistency": 19,
            "quarter_discrete_labelled_FY": 12,
            "fiscal_ytd_labelled_FY": 7,
        },
    }
    status = (
        "s2_mu_strict_timely_origin_identity_successor_pass"
        if all(checks.values())
        else "s2_mu_strict_timely_origin_identity_successor_failed"
    )
    unsigned = {
        "schema_version": (
            "fin_ia_s2_mu_physical_period_identity_successor_result_v1_2"
        ),
        "status": status,
        "recorded_at": "2026-08-24",
        "issue_id": (
            "RC-S2-013-unverified-origin-unanimity-is-not-period-identity-authority"
        ),
        "scope": "executor_only_strict_timely_origin_zero_call_successor",
        "bound_inputs": {
            "sqlite": _bound_ref(sqlite_path),
            "predecessor_result": _bound_ref(predecessor_path),
            "self_audit_failure": _bound_ref(failure_path),
            "fact_request_id": ORIGINAL_REQUEST_ID,
        },
        "implementation_refs": [
            _bound_ref(ROOT / "src/financial_facts/executor.py"),
            _bound_ref(
                ROOT
                / "scripts/data_retrieval/"
                "materialize_s2_mu_physical_period_identity_successor_v2.py"
            ),
        ],
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
            "The bound current MU request and six-asof group have timely "
            "origins. Forty mart groups do not; they now remain unavailable "
            "rather than receiving identity from repeated late copies. This "
            "does not rebuild the mart or close product-level S2 bridges."
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
