from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from financial_facts import (  # noqa: E402
    FactLookup,
    build_company_fact_mart,
    execute_fact_lookup,
    load_company_fact_mart_policy,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


CURRENT_BOUND_RESULT = (
    ROOT
    / "configs/financial_facts/"
    "fin_ia_0_1_3_s2_company_financial_fact_mart_result_v1_1.json"
).resolve()
HISTORICAL_RESULT_V1_0 = (
    ROOT
    / "configs/financial_facts/"
    "fin_ia_0_1_3_s2_company_financial_fact_mart_result_v1_0.json"
).resolve()
PROTECTED_RESULT_OUTPUTS = frozenset(
    {CURRENT_BOUND_RESULT, HISTORICAL_RESULT_V1_0}
)
DEFAULT_RESULT_OUTPUT = (
    "data/workbench_private/fin_0_1_3_s2_company_financial_fact_mart/"
    "v1/company_financial_fact_mart_result.json"
)


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _validated_unsigned_build_result(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the materialization receipt before composing the outer result."""

    claimed = payload.get("result_digest")
    unsigned = {key: value for key, value in payload.items() if key != "result_digest"}
    if not isinstance(claimed, str) or claimed != canonical_digest(unsigned):
        raise ValueError("company_fact_mart_build_result_digest_invalid")
    return unsigned


def _validated_result_output(value: str | Path) -> Path:
    output = _resolve(value)
    if output in PROTECTED_RESULT_OUTPUTS:
        raise ValueError("protected_s2_result_output_forbidden")
    return output


def _compose_outer_result(
    build_result: Mapping[str, Any],
    outer_fields: Mapping[str, Any],
) -> dict[str, Any]:
    if "result_digest" in outer_fields:
        raise ValueError("outer_result_digest_field_forbidden")
    build_unsigned = _validated_unsigned_build_result(build_result)
    forbidden_overrides = (set(build_unsigned) & set(outer_fields)) - {"status"}
    if forbidden_overrides:
        raise ValueError("outer_result_reserved_field_override_forbidden")
    unsigned = {
        **build_unsigned,
        **outer_fields,
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def _evaluate_qrels(
    sqlite_path: Path,
    qrels: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for qrel in qrels:
        lookup = FactLookup(
            fact_request_id="QREL::" + str(qrel["qrel_id"]),
            ticker=str(qrel["ticker"]),
            metric_id=str(qrel["metric_id"]),
            research_as_of=str(qrel["research_as_of"]),
            period={
                "start_date": qrel.get("period_start"),
                "end_date": qrel["period_end"],
                "fiscal_years": [int(qrel["fiscal_year"])],
            },
            granularity=str(qrel["period_role"]),
            requested_unit="reported_source_unit",
        )
        result = execute_fact_lookup(sqlite_path, lookup)
        facts = list(result.facts)
        exact = [
            fact
            for fact in facts
            if fact.period_start == qrel.get("period_start")
            and fact.period_end == qrel["period_end"]
            and fact.period_role == qrel["period_role"]
            and fact.fiscal_year == int(qrel["fiscal_year"])
            and fact.fiscal_period == qrel["fiscal_period"]
            and fact.value_decimal == qrel["expected_value"]
            and fact.unit == qrel["expected_unit"]
            and qrel["expected_accession"] in fact.accession_numbers
            and fact.numeric_fact_authority is True
        ]
        rows.append(
            {
                "qrel_id": qrel["qrel_id"],
                "stratum": qrel["stratum"],
                "status": result.status,
                "fact_count": len(facts),
                "exact_match": len(exact) == 1,
                "numeric_fact_id": exact[0].numeric_fact_id if len(exact) == 1 else None,
            }
        )
    strata = {
        stratum: {
            "qrel_count": sum(row["stratum"] == stratum for row in rows),
            "exact_match_count": sum(
                row["stratum"] == stratum and row["exact_match"] for row in rows
            ),
        }
        for stratum in sorted({str(row["stratum"]) for row in rows})
    }
    return {
        "qrel_count": len(rows),
        "exact_match_count": sum(row["exact_match"] for row in rows),
        "strata": strata,
        "rows": rows,
    }


def _evaluate_mutations(sqlite_path: Path) -> dict[str, Any]:
    dell_before_filing = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="MUTATION::DELL_BEFORE_Q1_ACCEPTED",
            ticker="DELL",
            metric_id="revenue",
            research_as_of="2026-06-08",
            period={
                "start_date": "2026-01-31",
                "end_date": "2026-05-01",
                "fiscal_years": [2027],
            },
            granularity="quarter_discrete",
            requested_unit="reported_source_unit",
        ),
    )
    mu_discrete_ocf = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="MUTATION::MU_Q3_DISCRETE_OCF",
            ticker="MU",
            metric_id="operating_cash_flow",
            research_as_of="2026-08-06",
            period={
                "start_date": "2026-02-27",
                "end_date": "2026-05-28",
                "fiscal_years": [2026],
            },
            granularity="quarter_discrete",
            requested_unit="reported_source_unit",
        ),
    )
    unknown_entity = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="MUTATION::UNKNOWN_ENTITY",
            ticker="ORCL",
            metric_id="revenue",
            research_as_of="2026-08-06",
            period={"start_date": None, "end_date": "2026-08-06", "fiscal_years": []},
            granularity="quarter_and_fiscal_year",
            requested_unit="reported_source_unit",
        ),
    )
    dell_margin = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="DERIVED::DELL_Q1_GROSS_MARGIN",
            ticker="DELL",
            metric_id="gross_margin",
            research_as_of="2026-08-06",
            period={
                "start_date": "2026-01-31",
                "end_date": "2026-05-01",
                "fiscal_years": [2027],
            },
            granularity="quarter_discrete",
            requested_unit="reported_source_unit",
        ),
    )
    dell_fcf = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="DERIVED::DELL_Q1_FREE_CASH_FLOW",
            ticker="DELL",
            metric_id="free_cash_flow",
            research_as_of="2026-08-06",
            period={
                "start_date": "2026-01-31",
                "end_date": "2026-05-01",
                "fiscal_years": [2027],
            },
            granularity="quarter_discrete",
            requested_unit="reported_source_unit",
        ),
    )
    dell_current_series = execute_fact_lookup(
        sqlite_path,
        FactLookup(
            fact_request_id="MUTATION::DELL_CURRENT_DISCLOSURE_COHORT",
            ticker="DELL",
            metric_id="revenue",
            research_as_of="2026-08-06",
            period={
                "start_date": None,
                "end_date": "2026-08-06",
                "fiscal_years": [2025, 2026, 2027],
            },
            granularity="quarter_and_fiscal_year",
            requested_unit="reported_source_unit",
        ),
    )
    checks = {
        "future_filing_excluded": dell_before_filing.status == "typed_gap",
        "mu_ytd_ocf_not_mislabeled_as_discrete_quarter": (
            mu_discrete_ocf.status == "typed_gap"
        ),
        "cross_case_unknown_entity_rejected": unknown_entity.status == "typed_gap",
        "same_period_margin_trace_resolved": (
            dell_margin.status == "resolved"
            and len(dell_margin.facts) == 1
            and dell_margin.facts[0].formula_trace is not None
        ),
        "same_period_free_cash_flow_trace_resolved": (
            dell_fcf.status == "resolved"
            and len(dell_fcf.facts) == 1
            and dell_fcf.facts[0].value_decimal == "3118000000"
        ),
        "open_period_keeps_same_cadence_comparable_without_stale_ytd": (
            dell_current_series.status == "resolved"
            and {fact.period_role for fact in dell_current_series.facts}
            == {"quarter_discrete", "fiscal_year"}
            and {
                (
                    fact.fiscal_year,
                    fact.fiscal_period,
                    fact.period_role,
                    fact.period_end,
                )
                for fact in dell_current_series.facts
            }
            == {
                (2027, "Q1", "quarter_discrete", "2026-05-01"),
                (2026, "Q1", "quarter_discrete", "2025-05-02"),
                (2026, "FY", "fiscal_year", "2026-01-30"),
            }
        ),
    }
    return {
        "checks": checks,
        "all_pass": all(checks.values()),
        "derived_examples": {
            "dell_q1_gross_margin": (
                dell_margin.facts[0].as_dict() if dell_margin.facts else None
            ),
            "dell_q1_free_cash_flow": (
                dell_fcf.facts[0].as_dict() if dell_fcf.facts else None
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        default="configs/financial_facts/fin_ia_0_1_3_s2_company_financial_fact_mart_policy_v1_0.json",
    )
    parser.add_argument(
        "--sqlite",
        default="data/workbench_private/fin_0_1_3_s2_company_financial_fact_mart/v1/company_financial_facts.sqlite",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_RESULT_OUTPUT,
    )
    args = parser.parse_args()
    policy_path = _resolve(args.policy)
    sqlite_path = _resolve(args.sqlite)
    output = _validated_result_output(args.output)
    policy_payload = _read_json(policy_path)
    policy = load_company_fact_mart_policy(policy_payload)
    build_result = build_company_fact_mart(
        policy,
        repository_root=ROOT,
        sqlite_path=sqlite_path,
    )
    qrels = _evaluate_qrels(sqlite_path, policy.acceptance_qrels)
    mutations = _evaluate_mutations(sqlite_path)
    acceptance = {
        "latest_fiscal_year_9_of_9": (
            qrels["strata"]["latest_fiscal_year"]["exact_match_count"] == 9
        ),
        "current_interim_15_of_15": (
            qrels["strata"]["current_interim"]["exact_match_count"] == 15
        ),
        "all_qrels_exact": qrels["exact_match_count"] == qrels["qrel_count"],
        "mutations_pass": mutations["all_pass"],
        "network_calls": 0,
        "model_calls": 0,
        "candidate_or_metric_row_grants_numeric_authority": False,
    }
    status = (
        "s2_company_financial_fact_mart_engineering_pass"
        if all(
            acceptance[key]
            for key in (
                "latest_fiscal_year_9_of_9",
                "current_interim_15_of_15",
                "all_qrels_exact",
                "mutations_pass",
            )
        )
        else "s2_company_financial_fact_mart_failed"
    )
    result = _compose_outer_result(
        build_result,
        {
            "status": status,
            "policy_ref": _relative(policy_path),
            "policy_digest": canonical_digest(policy_payload),
            "qrel_evaluation": qrels,
            "mutation_evaluation": mutations,
            "acceptance": acceptance,
            "known_boundary": (
                "This engineering gate authorizes source-bound company NumericFact "
                "lookup for the three current cases. It does not promote narrative "
                "candidates to Evidence, provide PIT market valuation, close S1 source "
                "gaps, or prove S3 research quality."
            ),
        },
    )
    _write_json(output, result)
    print(
        json.dumps(
            {
                "status": status,
                "sqlite": _relative(sqlite_path),
                "output": _relative(output),
                "counts": result["counts"],
                "qrels": {
                    "exact": qrels["exact_match_count"],
                    "total": qrels["qrel_count"],
                    "strata": qrels["strata"],
                },
                "mutations": mutations["checks"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status.endswith("engineering_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
