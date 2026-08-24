from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from financial_facts.executor import FactLookup, execute_fact_lookup  # noqa: E402
from retrieval.query_plan import canonical_digest  # noqa: E402


ORIGINAL_REQUEST_ID = "TFR::916e7ab7802ba4c47059ac2f"
AUDIT_RESEARCH_AS_OFS = (
    "2022-12-31",
    "2023-04-01",
    "2023-07-01",
    "2024-01-01",
    "2024-04-01",
    "2024-07-01",
)
EXPECTED_CURRENT_Q3_PERIODS = {
    (2026, "Q3", "2026-02-27", "2026-05-28"),
    (2025, "Q3", "2025-02-28", "2025-05-29"),
}
EXPECTED_ORIGINAL_FAILURE_PERIODS = {
    ("2024-11-29", "2025-02-27", "quarter_discrete", 2025, "Q3", "USD"),
    ("2025-02-28", "2025-05-29", "quarter_discrete", 2025, "Q3", "USD"),
}
EXPECTED_CURRENT_FACT_INVENTORY = {
    (
        2026,
        "Q3",
        "2026-02-27",
        "2026-05-28",
        "quarter_discrete",
        "28243000000",
        "CFOBS::3b94da5561e0c024872a7bf2bcfc2905",
        "0000723125-26-000015",
    ),
    (
        2025,
        "Q3",
        "2025-02-28",
        "2025-05-29",
        "quarter_discrete",
        "1885000000",
        "CFOBS::b229ee72bf6fe5e47979769e1aa90078",
        "0000723125-26-000015",
    ),
    (
        2026,
        "Q3",
        "2025-08-29",
        "2026-05-28",
        "fiscal_ytd",
        "47268000000",
        "CFOBS::e2990f6e9d52fe2b158850cb3f77feff",
        "0000723125-26-000015",
    ),
}
AUDIT_FINAL_COPY_ID = "CFOBS::70b381e21b4f08c22f218e103a3153fe"


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bound_ref(path: Path) -> dict[str, str]:
    return {"path": _relative(path), "sha256": _sha256(path)}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _find_original_failure_result(value: Any) -> Mapping[str, Any]:
    matches: list[Mapping[str, Any]] = []

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            if (
                item.get("schema_version")
                == "fin_ia_typed_fact_execution_result_v1_0"
                and item.get("fact_request_id") == ORIGINAL_REQUEST_ID
            ):
                matches.append(item)
            for nested in item.values():
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    if len(matches) != 1:
        raise ValueError("original_failure_typed_fact_result_not_unique")
    return matches[0]


def _failure_periods(result: Mapping[str, Any]) -> set[tuple[Any, ...]]:
    typed_conflict = result.get("typed_conflict")
    if not isinstance(typed_conflict, Mapping):
        return set()
    conflicts = typed_conflict.get("conflicts")
    if not isinstance(conflicts, list) or len(conflicts) != 1:
        return set()
    candidate_periods = conflicts[0].get("candidate_periods")
    if not isinstance(candidate_periods, list):
        return set()
    return {tuple(period) for period in candidate_periods}


def _fact_inventory(facts: list[dict[str, Any]]) -> set[tuple[Any, ...]]:
    return {
        (
            fact["fiscal_year"],
            fact["fiscal_period"],
            fact["period_start"],
            fact["period_end"],
            fact["period_role"],
            fact["value_decimal"],
            tuple(fact["source_observation_ids"])[0],
            tuple(fact["accession_numbers"])[0],
        )
        for fact in facts
        if len(fact["source_observation_ids"]) == 1
        and len(fact["accession_numbers"]) == 1
    }


def _original_lookup() -> FactLookup:
    return FactLookup(
        fact_request_id=ORIGINAL_REQUEST_ID,
        ticker="MU",
        metric_id="net_income",
        research_as_of="2026-08-06",
        period={
            "start_date": "2024-09-01",
            "end_date": "2026-08-06",
            "fiscal_years": [2025, 2026],
        },
        granularity="quarter_and_fiscal_year",
        requested_unit="reported_source_unit",
        unit_family="currency",
    )


def _audit_lookup(research_as_of: str) -> FactLookup:
    return FactLookup(
        fact_request_id=f"AUDIT::MU-PHYSICAL-Q1::{research_as_of}",
        ticker="MU",
        metric_id="net_income",
        research_as_of=research_as_of,
        period={
            "start_date": "2022-09-02",
            "end_date": "2022-12-01",
            "fiscal_years": [2022, 2023],
        },
        granularity="quarter_discrete",
        requested_unit="reported_source_unit",
        unit_family="currency",
    )


def _mart_population(sqlite_path: Path) -> dict[str, int]:
    uri = sqlite_path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        groups = connection.execute(
            "SELECT COUNT(*), MAX(vintage_count) FROM ("
            "SELECT COUNT(*) AS vintage_count "
            "FROM company_fact_observations "
            "GROUP BY ticker, metric_id, period_start, period_end, "
            "period_role, unit) WHERE vintage_count > 2"
        ).fetchone()
        varying = connection.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT COUNT(DISTINCT COALESCE(CAST(fiscal_year AS TEXT), '') "
            "|| '|' || COALESCE(fiscal_period, '')) AS label_count "
            "FROM company_fact_observations "
            "GROUP BY ticker, metric_id, period_start, period_end, "
            "period_role, unit) WHERE label_count > 1"
        ).fetchone()
    return {
        "physical_groups_with_more_than_two_rows": int(groups[0]),
        "maximum_rows_in_one_physical_group": int(groups[1]),
        "physical_groups_with_varying_fiscal_labels": int(varying[0]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the RC-S2-010 physical-period identity successor."
    )
    parser.add_argument(
        "--sqlite",
        default="data/workbench_private/fin_0_1_3_s2_company_financial_fact_mart/v1/company_financial_facts.sqlite",
    )
    parser.add_argument(
        "--original-failure-receipt",
        default="data/workbench_private/fin_0_1_3_s1_candidate_provenance_replay/mu-r1/full_result.json",
    )
    parser.add_argument(
        "--predecessor-result",
        default="configs/financial_facts/fin_ia_0_1_3_s2_mu_period_identity_successor_result_v1_0.json",
    )
    parser.add_argument(
        "--audit-failure-receipt",
        default="configs/financial_facts/fin_ia_0_1_3_s2_mu_supersession_pointer_independent_audit_failure_v1_0.json",
    )
    parser.add_argument(
        "--output",
        default="configs/financial_facts/fin_ia_0_1_3_s2_mu_physical_period_identity_successor_result_v1_1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sqlite_path = _resolve(args.sqlite)
    original_failure_path = _resolve(args.original_failure_receipt)
    predecessor_path = _resolve(args.predecessor_result)
    audit_failure_path = _resolve(args.audit_failure_receipt)
    predecessor = _read_json(predecessor_path)
    audit_failure = _read_json(audit_failure_path)
    original_failure = _read_json(original_failure_path)
    original_failure_result = _find_original_failure_result(original_failure)

    original = execute_fact_lookup(sqlite_path, _original_lookup())
    original_facts = [fact.as_dict() for fact in original.facts]
    original_q3_periods = {
        (
            fact["fiscal_year"],
            fact["fiscal_period"],
            fact["period_start"],
            fact["period_end"],
        )
        for fact in original_facts
        if fact["period_role"] == "quarter_discrete"
    }

    audit_replay: list[dict[str, Any]] = []
    audit_results = []
    for research_as_of in AUDIT_RESEARCH_AS_OFS:
        result = execute_fact_lookup(sqlite_path, _audit_lookup(research_as_of))
        audit_results.append(result)
        audit_replay.append(
            {
                "research_as_of": research_as_of,
                "result": result.as_dict(),
            }
        )

    population = _mart_population(sqlite_path)
    predecessor_bound = predecessor.get("bound_inputs") or {}
    predecessor_before = predecessor.get("before") or {}
    audit_bound = audit_failure.get("bound_predecessor") or {}
    audit_mart = audit_failure.get("immutable_mart") or {}
    checks = {
        "predecessor_success_result_preserved": (
            predecessor.get("status") == "s2_mu_period_identity_successor_pass"
        ),
        "predecessor_binds_exact_original_failure_and_mart": (
            predecessor_bound.get("fact_request_id") == ORIGINAL_REQUEST_ID
            and predecessor_bound.get("immutable_failure_receipt_sha256")
            == _sha256(original_failure_path)
            and predecessor_bound.get("sqlite_sha256") == _sha256(sqlite_path)
        ),
        "predecessor_before_matches_immutable_failure": (
            predecessor_before.get("status") == "typed_conflict"
            and predecessor_before.get("code")
            == "typed_fact_comparable_period_ambiguous"
            and {tuple(value) for value in predecessor_before.get("candidate_periods", [])}
            == EXPECTED_ORIGINAL_FAILURE_PERIODS
            and original_failure_result.get("status") == "typed_conflict"
            and original_failure_result.get("facts") == []
            and _failure_periods(original_failure_result)
            == EXPECTED_ORIGINAL_FAILURE_PERIODS
        ),
        "independent_audit_failure_preserved": (
            audit_failure.get("status") == "failed_preserved_successor_required"
            and audit_bound.get("commit")
            == "635c943f8efc562091647838132e2aedcca7f8d4"
            and audit_mart.get("sha256") == _sha256(sqlite_path)
        ),
        "original_failure_receipt_preserved": (
            _sha256(original_failure_path)
            == "1e8b91a1b734e27b333ea10a83a275a2bf8e7f650efad76c863e237f3edeedfc"
        ),
        "original_request_resolved": original.status == "resolved",
        "original_request_conflict_absent": original.typed_conflict is None,
        "original_request_exact_fact_inventory": (
            len(original_facts) == 3
            and _fact_inventory(original_facts) == EXPECTED_CURRENT_FACT_INVENTORY
            and all(
                fact["numeric_fact_authority"] is True
                and fact["authority_mode"]
                == "source_bound_company_reported_numeric_fact"
                and fact["ticker"] == "MU"
                and fact["metric_id"] == "net_income"
                and fact["unit"] == "USD"
                for fact in original_facts
            )
        ),
        "current_and_comparable_q3_exact": (
            original_q3_periods == EXPECTED_CURRENT_Q3_PERIODS
        ),
        "obsolete_q2_range_not_labelled_q3": (
            2025,
            "Q3",
            "2024-11-29",
            "2025-02-27",
        )
        not in original_q3_periods,
        "all_multi_vintage_audit_as_ofs_resolve": all(
            result.status == "resolved" for result in audit_results
        ),
        "audit_identity_stable_as_fy2023_q1": all(
            len(result.facts) == 1
            and result.facts[0].fiscal_year == 2023
            and result.facts[0].fiscal_period == "Q1"
            for result in audit_results
        ),
        "audit_final_wrong_q3_copy_never_selected": all(
            AUDIT_FINAL_COPY_ID not in result.facts[0].source_observation_ids
            for result in audit_results
            if result.facts
        ),
        "audit_population_matches_independent_receipt": (
            population["physical_groups_with_more_than_two_rows"] == 90
            and population["maximum_rows_in_one_physical_group"] == 6
            and population["physical_groups_with_varying_fiscal_labels"] == 78
        ),
    }
    status = (
        "s2_mu_physical_period_identity_successor_pass"
        if all(checks.values())
        else "s2_mu_physical_period_identity_successor_failed"
    )

    unsigned = {
        "schema_version": (
            "fin_ia_s2_mu_physical_period_identity_successor_result_v1_1"
        ),
        "status": status,
        "recorded_at": "2026-08-24",
        "issue_id": (
            "RC-S2-010-final-successor-pointer-is-not-period-identity-authority"
        ),
        "scope": "executor_only_no_mart_rebuild_zero_call_successor",
        "bound_inputs": {
            "sqlite": _bound_ref(sqlite_path),
            "original_failure_receipt": _bound_ref(original_failure_path),
            "predecessor_result": _bound_ref(predecessor_path),
            "independent_audit_failure_receipt": _bound_ref(audit_failure_path),
            "fact_request_id": ORIGINAL_REQUEST_ID,
        },
        "implementation_refs": [
            _bound_ref(ROOT / "src/financial_facts/executor.py"),
            _bound_ref(
                ROOT
                / "scripts/data_retrieval/materialize_s2_mu_physical_period_identity_successor.py"
            ),
        ],
        "method": {
            "period_identity_authority": (
                "same_physical_period 10-Q accepted within 45 days or 10-K "
                "accepted within 90 days; absent a timely origin, every "
                "observed fiscal label must agree"
            ),
            "numeric_vintage_policy": (
                "later values remain eligible only when their raw fiscal "
                "identity matches the admitted physical-period identity"
            ),
            "ambiguous_identity_policy": "typed_conflict_fail_closed",
            "mart_superseded_by_pointer_used_as_period_identity": False,
        },
        "audit_population": population,
        "predecessor_failure": {
            "classification": "P1_material",
            "predecessor_result_digest": predecessor.get("result_digest"),
            "status": audit_failure.get("status"),
        },
        "original_request_after": original.as_dict(),
        "multi_vintage_point_in_time_replay": audit_replay,
        "checks": checks,
        "calls": {"network": 0, "provider": 0, "model": 0},
        "authority": {
            "numeric_fact_authority_is_source_bound_executor_only": True,
            "s2_stage_qualification_authorized": False,
            "s1_or_s3_acceptance_authorized": False,
            "qualified_human_review_pass": False,
            "publication_or_release_authorized": False,
        },
        "known_boundary": (
            "This successor repairs one standardized-statement physical-period "
            "identity mechanism on the existing immutable mart. A missing "
            "timely origin with disagreeing labels remains a typed conflict. "
            "It does not rebuild the mart, close product-level S2 bridges, "
            "qualify a stage, or replace qualified-human review."
        ),
    }
    output = {**unsigned, "result_digest": canonical_digest(unsigned)}
    _write_json(_resolve(args.output), output)
    print(
        json.dumps(
            {
                "status": status,
                "checks": checks,
                "audit_population": population,
                "original_fact_count": len(original_facts),
                "audit_replay_count": len(audit_replay),
                "calls": output["calls"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status.endswith("_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
