from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC_ROOT)]

from financial_facts import (  # noqa: E402
    CompanyFactMartPolicy,
    CompanyFactObservation,
    FactLookup,
    MetricDefinition,
    execute_fact_lookup,
    write_company_fact_mart,
)
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
from scripts.data_retrieval.materialize_s2_mu_physical_period_identity_successor_v3 import (  # noqa: E402
    EXPECTED_POPULATION,
)


PREDECESSOR_RESULT = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_mu_physical_period_identity_successor_result_v1_3.json"
)
INDEPENDENT_AUDIT_FAILURE = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_derived_conflict_boundary_independent_audit_failure_v1_0.json"
)
OUTPUT = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_mu_physical_period_identity_successor_result_v1_4.json"
)
SQLITE = (
    "data/workbench_private/fin_0_1_3_s2_company_financial_fact_mart/v1/"
    "company_financial_facts.sqlite"
)
PREDECESSOR_SHA256 = (
    "c2d87be31c0a74eb2d19e1b72120771691282232636d52453071ef319a29092c"
)


def _metric(
    metric_id: str,
    *,
    unit_family: str = "currency",
    formula: str | None = None,
) -> MetricDefinition:
    return MetricDefinition(
        metric_id=metric_id,
        unit_family=unit_family,
        concepts=() if formula else (("us-gaap", metric_id),),
        allowed_units=() if formula else ("USD",),
        formula=formula,
    )


def _observation(
    observation_id: str,
    metric_id: str,
    value: str,
    *,
    accepted_at: str,
    period_start: str,
    period_end: str,
    fiscal_year: int,
    fiscal_period: str,
    period_role: str = "quarter_discrete",
) -> CompanyFactObservation:
    return CompanyFactObservation(
        observation_id=observation_id,
        ticker="DELL",
        cik="0001571996",
        legal_name="Dell Technologies Inc.",
        metric_id=metric_id,
        unit_family="currency",
        taxonomy="us-gaap",
        concept=metric_id,
        concept_priority=0,
        value_decimal=value,
        unit="USD",
        period_start=period_start,
        period_end=period_end,
        duration_days=91 if period_role == "quarter_discrete" else 365,
        period_role=period_role,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        reported_fiscal_year=fiscal_year,
        reported_fiscal_period=fiscal_period,
        form="10-Q" if period_role != "fiscal_year" else "10-K",
        accession_number="SYNTHETIC-" + observation_id,
        filed_at=accepted_at[:10],
        accepted_at=accepted_at,
        frame=None,
        primary_document="synthetic-boundary-probe.htm",
        citation_url="https://www.sec.gov/Archives/synthetic-boundary-probe",
        companyfacts_ref="synthetic/companyfacts.json",
        companyfacts_sha256="a" * 64,
        submissions_ref="synthetic/submissions.json",
        submissions_sha256="b" * 64,
        captured_at="2026-08-24T00:00:00+00:00",
    )


def _synthetic_boundary_probes() -> dict[str, object]:
    metrics = (
        _metric("revenue"),
        _metric("gross_profit"),
        _metric("net_income"),
        _metric(
            "gross_margin",
            unit_family="percentage",
            formula="gross_profit / revenue * 100",
        ),
    )
    observations = (
        _observation(
            "GP-ORIGIN",
            "gross_profit",
            "50",
            accepted_at="2026-06-09T00:00:00+00:00",
            period_start="2026-01-31",
            period_end="2026-05-01",
            fiscal_year=2027,
            fiscal_period="Q1",
        ),
        _observation(
            "REV-LATE-Q1",
            "revenue",
            "200",
            accepted_at="2026-09-01T00:00:00+00:00",
            period_start="2026-01-31",
            period_end="2026-05-01",
            fiscal_year=2027,
            fiscal_period="Q1",
        ),
        _observation(
            "REV-LATE-Q2",
            "revenue",
            "200",
            accepted_at="2026-10-01T00:00:00+00:00",
            period_start="2026-01-31",
            period_end="2026-05-01",
            fiscal_year=2027,
            fiscal_period="Q2",
        ),
        _observation(
            "NI-LATE-ANNUAL",
            "net_income",
            "100",
            accepted_at="2027-06-01T00:00:00+00:00",
            period_start="2026-01-01",
            period_end="2026-12-31",
            fiscal_year=2027,
            fiscal_period="FY",
            period_role="fiscal_year",
        ),
    )
    policy = CompanyFactMartPolicy(
        recorded_at="2026-08-24",
        research_as_of="2027-12-31",
        minimum_period_end="2022-01-01",
        allowed_forms=("10-K", "10-Q"),
        sources=(),
        metrics=metrics,
        acceptance_qrels=(),
        authority={
            "raw_capture_digest_required": True,
            "accepted_at_required": True,
            "preserve_all_vintages": True,
            "fact_signal_context_mixed_table_forbidden": True,
            "typed_conflict_fails_closed": True,
        },
    )
    with TemporaryDirectory(prefix="fin_ia_s2_boundary_probe_") as temp_dir:
        sqlite_path = Path(temp_dir) / "facts.sqlite"
        write_company_fact_mart(
            sqlite_path,
            observations=observations,
            metrics=metrics,
            policy=policy,
        )
        derived = execute_fact_lookup(
            sqlite_path,
            FactLookup(
                fact_request_id="AUDIT::DERIVED-CONFLICT-PROPAGATION",
                ticker="DELL",
                metric_id="gross_margin",
                research_as_of="2026-12-31",
                period={
                    "start_date": "2026-01-31",
                    "end_date": "2026-05-01",
                    "fiscal_years": [2027],
                },
                granularity="quarter_discrete",
                requested_unit="reported_source_unit",
                unit_family="percentage",
            ),
        )
        unrelated_role = execute_fact_lookup(
            sqlite_path,
            FactLookup(
                fact_request_id="AUDIT::UNRELATED-ROLE-ISOLATION",
                ticker="DELL",
                metric_id="net_income",
                research_as_of="2027-12-31",
                period={
                    "start_date": "2026-01-01",
                    "end_date": "2026-12-31",
                    "fiscal_years": [2027],
                },
                granularity="quarter_discrete",
                requested_unit="reported_source_unit",
                unit_family="currency",
            ),
        )
    return {
        "derived_conflict_propagation": derived.as_dict(),
        "unrelated_role_isolation": unrelated_role.as_dict(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the S2 successor that preserves direct identity, "
            "propagates derived conflicts, and isolates unrelated roles."
        )
    )
    parser.add_argument("--sqlite", default=SQLITE)
    parser.add_argument("--predecessor-result", default=PREDECESSOR_RESULT)
    parser.add_argument(
        "--independent-audit-failure", default=INDEPENDENT_AUDIT_FAILURE
    )
    parser.add_argument("--output", default=OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sqlite_path = _resolve(args.sqlite)
    predecessor_path = _resolve(args.predecessor_result)
    audit_failure_path = _resolve(args.independent_audit_failure)
    predecessor = _read_json(predecessor_path)
    audit_failure = _read_json(audit_failure_path)

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
    probes = _synthetic_boundary_probes()
    derived_probe = probes["derived_conflict_propagation"]
    role_probe = probes["unrelated_role_isolation"]
    derived_conflicts = (
        (derived_probe.get("typed_conflict") or {}).get("conflicts") or []
    )
    no_origin_conflicts = (
        no_origin.typed_conflict.get("conflicts")
        if no_origin.typed_conflict
        else []
    )
    checks = {
        "strict_origin_predecessor_v1_3_preserved_and_bound": (
            _sha256(predecessor_path) == PREDECESSOR_SHA256
            and predecessor.get("status")
            == "s2_mu_strict_timely_origin_identity_successor_pass"
            and all(predecessor.get("checks", {}).values())
        ),
        "clean_independent_audit_failure_preserved_and_bound": (
            audit_failure.get("status") == "failed_preserved_successor_required"
            and audit_failure.get("review", {}).get("independent_review") is True
            and audit_failure.get("review", {}).get("reviewed_commit")
            == "5f35b116ba8e906a7e0c73ed1972679699c6ab1c"
            and len(audit_failure.get("findings") or []) == 2
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
        "derived_input_conflict_propagates_without_gap_downgrade": (
            derived_probe.get("status") == "typed_conflict"
            and derived_probe.get("typed_gap") is None
            and len(derived_conflicts) == 1
            and derived_conflicts[0].get("code")
            == "derived_formula_input_conflict"
            and derived_conflicts[0].get("input_metric") == "revenue"
            and (derived_conflicts[0].get("input_conflicts") or [{}])[0].get(
                "code"
            )
            == "typed_fact_physical_period_identity_ambiguous"
        ),
        "unrelated_period_role_cannot_create_identity_conflict": (
            role_probe.get("status") == "typed_gap"
            and role_probe.get("typed_conflict") is None
            and (role_probe.get("typed_gap") or {}).get("gap_code")
            == "typed_fact_not_found_for_as_of_and_period"
        ),
    }
    status = (
        "s2_mu_strict_identity_and_conflict_boundary_successor_pass"
        if all(checks.values())
        else "s2_mu_strict_identity_and_conflict_boundary_successor_failed"
    )
    unsigned = {
        "schema_version": (
            "fin_ia_s2_mu_physical_period_identity_successor_result_v1_4"
        ),
        "status": status,
        "recorded_at": "2026-08-24",
        "issue_ids": [
            "RC-S2-013-unverified-origin-unanimity-is-not-period-identity-authority",
            "RC-S2-014-strict-origin-successor-receipt-shape-mismatch",
            "RC-S2-015-derived-input-conflict-was-downgraded-to-gap",
            "RC-S2-016-unrelated-period-role-could-create-false-conflict",
        ],
        "scope": (
            "executor_only_strict_identity_conflict_boundary_zero_call_successor"
        ),
        "bound_inputs": {
            "sqlite": _bound_ref(sqlite_path),
            "strict_origin_predecessor_result": _bound_ref(predecessor_path),
            "independent_audit_failure": _bound_ref(audit_failure_path),
            "fact_request_id": ORIGINAL_REQUEST_ID,
        },
        "implementation_refs": [
            _bound_ref(ROOT / "src/financial_facts/executor.py"),
            _bound_ref(
                ROOT
                / "scripts/data_retrieval/"
                "materialize_s2_mu_physical_period_identity_successor_v4.py"
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
            "derived_input_policy": (
                "typed_conflicts_propagate_with_input_provenance_and_only_"
                "conflict_free_missing_inputs_become_gaps"
            ),
            "granularity_policy": (
                "candidate_rows_are_role_scoped_before_identity_admission"
            ),
        },
        "full_mart_origin_population": population,
        "original_request_after": current.as_dict(),
        "timely_origin_six_asof_replay": audit_replay,
        "no_origin_counterexample_after": no_origin.as_dict(),
        "synthetic_boundary_probes": probes,
        "checks": checks,
        "calls": {"network": 0, "provider": 0, "model": 0},
        "authority": {
            "numeric_fact_authority_is_source_bound_executor_only": True,
            "public_information_gap_requires_conflict_free_inputs": True,
            "s2_stage_qualification_authorized": False,
            "qualified_human_review_pass": False,
            "publication_or_release_authorized": False,
        },
        "known_boundary": (
            "The current MU request, six-asof identity, strict no-origin "
            "failure, derived-conflict propagation, and unrelated-role "
            "isolation are proved. This executor-only successor does not "
            "rebuild the mart or close product-level S2 bridges."
        ),
    }
    output = {**unsigned, "result_digest": canonical_digest(unsigned)}
    _write_json(_resolve(args.output), output)
    print(
        json.dumps(
            {"status": status, "checks": checks, "calls": output["calls"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status.endswith("_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
