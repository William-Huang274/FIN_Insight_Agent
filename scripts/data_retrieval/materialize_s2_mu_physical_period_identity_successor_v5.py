from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC_ROOT)]

from financial_facts import (  # noqa: E402
    CompanyFactMartPolicy,
    FactLookup,
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
from scripts.data_retrieval.materialize_s2_mu_physical_period_identity_successor_v4 import (  # noqa: E402
    _metric,
    _observation,
    _synthetic_boundary_probes,
)


PREDECESSOR_RESULT = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_mu_physical_period_identity_successor_result_v1_4.json"
)
CLEAN_AUDIT_FAILURE = (
    "configs/audits/"
    "fin_ia_0_1_3_commit_1243b3cc_clean_independent_audit_failure_v1_0.json"
)
OUTPUT = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_mu_physical_period_identity_successor_result_v1_5.json"
)
SQLITE = (
    "data/workbench_private/fin_0_1_3_s2_company_financial_fact_mart/v1/"
    "company_financial_facts.sqlite"
)
PREDECESSOR_SHA256 = (
    "5a28c662538312467c75b070e3b89e7b98130dd241ffb61b56645250ec9f012a"
)
CLEAN_AUDIT_FAILURE_SHA256 = (
    "ffdf44e100da7ab259dcbc7669dfed720172e6f9cea218c8b1a27d588d70cbc4"
)


def _requested_comparable_conflict_probes() -> dict[str, object]:
    metrics = (
        _metric("revenue"),
        _metric("gross_profit"),
        _metric(
            "gross_margin",
            unit_family="percentage",
            formula="gross_profit / revenue * 100",
        ),
    )
    current_revenue = _observation(
        "CURRENT-REV-Q1-ORIGIN",
        "revenue",
        "200",
        accepted_at="2026-06-09T00:00:00+00:00",
        period_start="2026-01-31",
        period_end="2026-05-01",
        fiscal_year=2027,
        fiscal_period="Q1",
    )
    current_gross_profit = replace(
        _observation(
            "CURRENT-GP-Q1-ORIGIN",
            "gross_profit",
            "50",
            accepted_at="2026-06-09T00:00:00+00:00",
            period_start="2026-01-31",
            period_end="2026-05-01",
            fiscal_year=2027,
            fiscal_period="Q1",
        ),
        accession_number=current_revenue.accession_number,
    )
    late_comparable = replace(
        _observation(
            "COMPARABLE-REV-Q1-LATE-COPY",
            "revenue",
            "100",
            accepted_at="2026-06-09T00:00:00+00:00",
            period_start="2025-02-01",
            period_end="2025-05-02",
            fiscal_year=2026,
            fiscal_period="Q1",
        ),
        accession_number=current_revenue.accession_number,
    )
    policy = CompanyFactMartPolicy(
        recorded_at="2026-08-24",
        research_as_of="2026-08-06",
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

    def lookup(metric_id: str, fiscal_years: list[int]) -> FactLookup:
        return FactLookup(
            fact_request_id=(
                f"AUDIT::REQUESTED-COMPARABLE::{metric_id}::"
                f"{','.join(str(value) for value in fiscal_years) or 'AUTO'}"
            ),
            ticker="DELL",
            metric_id=metric_id,
            research_as_of="2026-08-06",
            period={
                "start_date": None,
                "end_date": "2026-08-06",
                "fiscal_years": fiscal_years,
            },
            granularity="quarter_discrete",
            requested_unit="reported_source_unit",
        )

    with TemporaryDirectory(prefix="fin_ia_s2_requested_comparable_") as temp_dir:
        sqlite_path = Path(temp_dir) / "facts.sqlite"
        write_company_fact_mart(
            sqlite_path,
            observations=(
                current_revenue,
                current_gross_profit,
                late_comparable,
            ),
            metrics=metrics,
            policy=policy,
        )
        explicit_direct = execute_fact_lookup(
            sqlite_path,
            lookup("revenue", [2026, 2027]),
        )
        automatic_direct = execute_fact_lookup(
            sqlite_path,
            lookup("revenue", []),
        )
        explicit_derived = execute_fact_lookup(
            sqlite_path,
            lookup("gross_margin", [2026, 2027]),
        )
    return {
        "explicit_requested_direct": explicit_direct.as_dict(),
        "automatic_comparable_direct": automatic_direct.as_dict(),
        "explicit_requested_derived": explicit_derived.as_dict(),
    }


def _direct_probe_passes(probe: dict[str, object]) -> bool:
    typed_conflict = probe.get("typed_conflict") or {}
    conflicts = typed_conflict.get("conflicts") or []
    return bool(
        probe.get("status") == "typed_conflict"
        and probe.get("typed_gap") is None
        and len(conflicts) == 1
        and conflicts[0].get("code")
        == "typed_fact_physical_period_identity_source_unavailable"
        and conflicts[0].get("period_end") == "2025-05-02"
        and conflicts[0].get("candidate_fiscal_identities")
        == [{"fiscal_year": 2026, "fiscal_period": "Q1"}]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the S2 successor that cannot drop requested or "
            "automatic comparable physical-identity conflicts."
        )
    )
    parser.add_argument("--sqlite", default=SQLITE)
    parser.add_argument("--predecessor-result", default=PREDECESSOR_RESULT)
    parser.add_argument("--clean-audit-failure", default=CLEAN_AUDIT_FAILURE)
    parser.add_argument("--output", default=OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sqlite_path = _resolve(args.sqlite)
    predecessor_path = _resolve(args.predecessor_result)
    audit_failure_path = _resolve(args.clean_audit_failure)
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
    prior_probes = _synthetic_boundary_probes()
    comparable_probes = _requested_comparable_conflict_probes()
    prior_derived = prior_probes["derived_conflict_propagation"]
    prior_role = prior_probes["unrelated_role_isolation"]
    prior_derived_conflicts = (
        (prior_derived.get("typed_conflict") or {}).get("conflicts") or []
    )
    no_origin_conflicts = (
        no_origin.typed_conflict.get("conflicts")
        if no_origin.typed_conflict
        else []
    )
    derived_comparable = comparable_probes["explicit_requested_derived"]
    derived_comparable_conflicts = (
        (derived_comparable.get("typed_conflict") or {}).get("conflicts") or []
    )
    nested_comparable_conflicts = (
        derived_comparable_conflicts[0].get("input_conflicts")
        if derived_comparable_conflicts
        else []
    )
    unsigned_audit = {
        key: value
        for key, value in audit_failure.items()
        if key != "receipt_digest"
    }
    checks = {
        "v1_4_predecessor_preserved_and_bound": (
            _sha256(predecessor_path) == PREDECESSOR_SHA256
            and predecessor.get("status")
            == "s2_mu_strict_identity_and_conflict_boundary_successor_pass"
            and all(predecessor.get("checks", {}).values())
        ),
        "commit_1243_clean_audit_failure_preserved_and_bound": (
            _sha256(audit_failure_path) == CLEAN_AUDIT_FAILURE_SHA256
            and audit_failure.get("status") == "failed_successor_required"
            and audit_failure.get("audited_commit")
            == "1243b3cc2e1e1c17a46437195c24ab076d3b4365"
            and audit_failure.get("receipt_digest")
            == canonical_digest(unsigned_audit)
            and any(
                finding.get("finding_id")
                == "S2_REQUESTED_COMPARABLE_IDENTITY_CONFLICT_DROPPED"
                for finding in audit_failure.get("findings") or []
            )
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
        "prior_derived_input_conflict_still_propagates": (
            prior_derived.get("status") == "typed_conflict"
            and prior_derived.get("typed_gap") is None
            and len(prior_derived_conflicts) == 1
            and prior_derived_conflicts[0].get("code")
            == "derived_formula_input_conflict"
        ),
        "prior_unrelated_role_isolation_preserved": (
            prior_role.get("status") == "typed_gap"
            and prior_role.get("typed_conflict") is None
        ),
        "explicit_requested_comparable_identity_conflict_propagates": (
            _direct_probe_passes(
                comparable_probes["explicit_requested_direct"]
            )
        ),
        "automatic_comparable_identity_conflict_propagates": (
            _direct_probe_passes(
                comparable_probes["automatic_comparable_direct"]
            )
        ),
        "derived_requested_comparable_conflict_propagates": (
            derived_comparable.get("status") == "typed_conflict"
            and derived_comparable.get("typed_gap") is None
            and len(derived_comparable_conflicts) == 1
            and derived_comparable_conflicts[0].get("code")
            == "derived_formula_input_conflict"
            and derived_comparable_conflicts[0].get("input_metric") == "revenue"
            and len(nested_comparable_conflicts) == 1
            and nested_comparable_conflicts[0].get("period_end") == "2025-05-02"
            and nested_comparable_conflicts[0].get("code")
            == "typed_fact_physical_period_identity_source_unavailable"
        ),
    }
    status = (
        "s2_mu_requested_comparable_conflict_successor_pass"
        if all(checks.values())
        else "s2_mu_requested_comparable_conflict_successor_failed"
    )
    unsigned = {
        "schema_version": (
            "fin_ia_s2_mu_physical_period_identity_successor_result_v1_5"
        ),
        "status": status,
        "recorded_at": "2026-08-24",
        "issue_ids": [
            "RC-S2-017-requested-comparable-period-identity-conflict-was-dropped"
        ],
        "scope": (
            "executor_only_requested_and_automatic_comparable_identity_"
            "conflict_zero_call_successor"
        ),
        "bound_inputs": {
            "sqlite": _bound_ref(sqlite_path),
            "v1_4_predecessor_result": _bound_ref(predecessor_path),
            "clean_independent_audit_failure": _bound_ref(audit_failure_path),
            "fact_request_id": ORIGINAL_REQUEST_ID,
        },
        "implementation_refs": [
            _bound_ref(ROOT / "src/financial_facts/executor.py"),
            _bound_ref(
                ROOT
                / "scripts/data_retrieval/"
                "materialize_s2_mu_physical_period_identity_successor_v5.py"
            ),
        ],
        "method": {
            "explicit_requested_year_conflict_policy": (
                "all identity conflicts whose nested candidate years can "
                "match an explicit request are propagated before latest-role selection"
            ),
            "automatic_comparable_conflict_policy": (
                "the current fiscal identity selects prior-year same-period "
                "conflicts from nested candidate identities and fails closed"
            ),
            "filing_cohort_conflict_policy": (
                "an identity conflict is relevant when the current filing "
                "accession is among its copies rather than requiring every vintage "
                "to share that accession"
            ),
            "derived_input_policy": (
                "a surfaced direct comparable identity conflict remains a derived conflict"
            ),
        },
        "full_mart_origin_population": population,
        "original_request_after": current.as_dict(),
        "timely_origin_six_asof_replay": audit_replay,
        "no_origin_counterexample_after": no_origin.as_dict(),
        "prior_synthetic_boundary_probes": prior_probes,
        "requested_comparable_conflict_probes": comparable_probes,
        "checks": checks,
        "calls": {"network": 0, "provider": 0, "model": 0},
        "authority": {
            "numeric_fact_authority_is_source_bound_executor_only": True,
            "partial_resolved_response_with_requested_identity_conflict_allowed": False,
            "public_information_gap_requires_conflict_free_inputs": True,
            "s2_stage_qualification_authorized": False,
            "qualified_human_review_pass": False,
            "publication_or_release_authorized": False,
        },
        "known_boundary": (
            "This closes the audited current/comparable conflict-routing bug "
            "for the bound executor and regressions. It does not rebuild the "
            "mart, provide product-level ASP/units/PVM/profit bridges, or qualify S2."
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
