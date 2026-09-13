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


PROTECTED_OUTPUT_ROOTS = tuple((ROOT / name).resolve() for name in ("configs", "src", "scripts"))
DEFAULT_RESULT_OUTPUT = "data/financial-facts/result.json"


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
    if any(output.is_relative_to(root) for root in PROTECTED_OUTPUT_ROOTS):
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
                "selection_mode": "exact_period_end",
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




def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        required=True, help="A generated dataset policy with source bindings; use materialize_companyfacts_snapshot for a new capture",
    )
    parser.add_argument(
        "--sqlite",
        default="data/financial-facts/financial-facts.sqlite",
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
    policy = load_company_fact_mart_policy(policy_payload, require_acceptance_qrels=False)
    build_result = build_company_fact_mart(
        policy,
        repository_root=ROOT,
        sqlite_path=sqlite_path,
    )
    qrels = _evaluate_qrels(sqlite_path, policy.acceptance_qrels)
    supplied_checks = qrels["qrel_count"] > 0
    checks_pass = qrels["exact_match_count"] == qrels["qrel_count"]
    acceptance = {
        "all_qrels_exact": checks_pass if supplied_checks else None,
        "checks_status": "passed" if supplied_checks and checks_pass else "failed" if supplied_checks else "not_requested",
        "network_calls": 0,
        "model_calls": 0,
        "candidate_or_metric_row_grants_numeric_authority": False,
    }
    status = (
        "company_financial_fact_mart_checks_passed" if supplied_checks and checks_pass
        else "company_financial_fact_mart_checks_failed" if supplied_checks
        else "company_financial_fact_mart_materialized_acceptance_pending"
    )
    result = _compose_outer_result(
        build_result,
        {
            "status": status,
            "policy_ref": _relative(policy_path),
            "policy_digest": canonical_digest(policy_payload),
            "qrel_evaluation": qrels,
            "acceptance": acceptance,
            "known_boundary": (
                "Builds the explicitly supplied sources and evaluates only supplied checks. "
                "Materialization does not certify financial research quality or authorize a "
                "dataset for an existing reference-case deployment."
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
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if checks_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
