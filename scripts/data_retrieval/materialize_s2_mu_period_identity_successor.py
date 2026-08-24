from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from financial_facts.executor import FactLookup, execute_fact_lookup  # noqa: E402
from retrieval.query_plan import canonical_digest  # noqa: E402


FAILURE_CANDIDATE_PERIODS = [
    ["2024-11-29", "2025-02-27", "quarter_discrete", 2025, "Q3", "USD"],
    ["2025-02-28", "2025-05-29", "quarter_discrete", 2025, "Q3", "USD"],
]


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


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute only the RC-S2-006 MU net-income projection."
    )
    parser.add_argument(
        "--sqlite",
        default="data/workbench_private/fin_0_1_3_s2_company_financial_fact_mart/v1/company_financial_facts.sqlite",
    )
    parser.add_argument(
        "--failure-receipt",
        default="data/workbench_private/fin_0_1_3_s1_candidate_provenance_replay/mu-r1/full_result.json",
    )
    parser.add_argument(
        "--output",
        default="configs/financial_facts/fin_ia_0_1_3_s2_mu_period_identity_successor_result_v1_0.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sqlite_path = _resolve(args.sqlite)
    failure_path = _resolve(args.failure_receipt)
    lookup = FactLookup(
        fact_request_id="TFR::916e7ab7802ba4c47059ac2f",
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
    result = execute_fact_lookup(sqlite_path, lookup)
    facts = [fact.as_dict() for fact in result.facts]
    q3_periods = {
        (
            fact["fiscal_year"],
            fact["fiscal_period"],
            fact["period_start"],
            fact["period_end"],
        )
        for fact in facts
        if fact["period_role"] == "quarter_discrete"
    }
    expected_q3_periods = {
        (2026, "Q3", "2026-02-27", "2026-05-28"),
        (2025, "Q3", "2025-02-28", "2025-05-29"),
    }
    checks = {
        "request_resolved": result.status == "resolved",
        "typed_conflict_absent": result.typed_conflict is None,
        "current_and_comparable_q3_exact": q3_periods == expected_q3_periods,
        "obsolete_fy2025_q2_range_not_labelled_q3": (
            2025,
            "Q3",
            "2024-11-29",
            "2025-02-27",
        )
        not in q3_periods,
        "failure_receipt_preserved": failure_path.is_file(),
    }
    status = (
        "s2_mu_period_identity_successor_pass"
        if all(checks.values())
        else "s2_mu_period_identity_successor_failed"
    )
    unsigned = {
        "schema_version": "fin_ia_s2_mu_period_identity_successor_result_v1_0",
        "status": status,
        "recorded_at": "2026-08-24",
        "issue_id": "RC-S2-006-MU-fiscal-quarter-discrete-period-identity-collision",
        "scope": "single_existing_typed_fact_request_recomputed_no_mart_rebuild",
        "bound_inputs": {
            "sqlite_ref": _relative(sqlite_path),
            "sqlite_sha256": _sha256(sqlite_path),
            "immutable_failure_receipt_ref": _relative(failure_path),
            "immutable_failure_receipt_sha256": _sha256(failure_path),
            "fact_request_id": lookup.fact_request_id,
        },
        "implementation_refs": [
            _bound_ref(ROOT / "src/financial_facts/executor.py"),
            _bound_ref(
                ROOT
                / "scripts/data_retrieval/materialize_s2_mu_period_identity_successor.py"
            ),
        ],
        "before": {
            "status": "typed_conflict",
            "code": "typed_fact_comparable_period_ambiguous",
            "candidate_periods": FAILURE_CANDIDATE_PERIODS,
        },
        "after": result.as_dict(),
        "checks": checks,
        "calls": {"network": 0, "provider": 0, "model": 0},
        "authority": {
            "numeric_fact_authority_is_source_bound_executor_only": True,
            "candidate_or_narrative_grants_numeric_authority": False,
            "s2_stage_qualification_authorized": False,
            "s1_or_s3_acceptance_authorized": False,
            "publication_or_release_authorized": False,
        },
        "known_boundary": "This successor closes only the false MU net-income period-label collision by honoring a later physical-period identity successor as of the request date. It does not erase the immutable failure, rebuild the mart, close other S2 product bridges, or qualify any stage.",
    }
    output = {**unsigned, "result_digest": canonical_digest(unsigned)}
    _write_json(_resolve(args.output), output)
    print(
        json.dumps(
            {
                "status": status,
                "checks": checks,
                "fact_count": len(facts),
                "quarter_discrete_periods": sorted(q3_periods),
                "calls": output["calls"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status.endswith("_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
