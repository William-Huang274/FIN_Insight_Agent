from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.material_numeric_program import (  # noqa: E402
    canonical_digest,
    compile_three_case_material_numeric_programs_from_files,
)


DEFAULT_POLICY = (
    REPO_ROOT
    / "configs/runtime/fin_ia_0_1_3_repair_closeout_material_numeric_program_v1_0.json"
)
DEFAULT_GOLD = (
    REPO_ROOT
    / "data/workbench_private/research_data/gold_fact_signal_mart_v0_1.sqlite"
)
DEFAULT_STAGING = (
    REPO_ROOT
    / "data/staging/structured_financial_facts/sec_companyfacts_financial_fact_rows_v0_1.jsonl"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_02_material_numeric_program_formula_recalculation_and_typed_gap_coverage_v1_0.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the FIN 0.1.3 S1-02 three-case material Numeric program."
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--gold-sqlite", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    program_set = compile_three_case_material_numeric_programs_from_files(
        policy_path=args.policy,
        gold_sqlite_path=args.gold_sqlite,
        staging_path=args.staging,
    )
    payload = build_release_record(
        program_set=program_set,
        policy_path=args.policy,
        gold_sqlite_path=args.gold_sqlite,
        staging_path=args.staging,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "record_digest": payload["record_digest"],
                "program_set_digest": program_set["program_set_digest"],
                "observed_counts": program_set["observed_counts"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def build_release_record(
    *,
    program_set: dict[str, Any],
    policy_path: Path,
    gold_sqlite_path: Path,
    staging_path: Path,
) -> dict[str, Any]:
    summary_refs = {
        "sec_runtime_summary": (
            "data/manifests/sec_financial_statement_metric_runtime_summary_v0_1.json"
        ),
        "gold_mart_summary": "data/manifests/gold_fact_signal_mart_summary_v0_1.json",
    }
    summary_digests = {
        key: _sha256(REPO_ROOT / value) for key, value in summary_refs.items()
    }
    body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s1_02_release_record_v1_0",
        "task_id": "FIN-0.1.3-013-S1-02-MATERIAL-NUMERIC-PROGRAM-FORMULA-RECALCULATION-AND-TYPED-GAP-COVERAGE",
        "status": "S1_02_engineering_pass_S1_03_next_S1_in_progress",
        "scope": "three_case_material_numeric_program_exact_base_fact_lineage_deterministic_formula_recalculation_and_exhaustive_typed_gap_governance",
        "policy_ref": str(policy_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "policy_sha256": _sha256(policy_path),
        "input_authority": {
            "gold_sqlite_ref": str(gold_sqlite_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "staging_ref": str(staging_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "summary_refs": summary_refs,
            "summary_sha256": summary_digests,
            "comparative_instant_rule": "annual_period_start_minus_one_day_from_same_current_10K_filing",
            "source_network_access": False,
        },
        "program_set": program_set,
        "product_capability_delta": (
            "FIN 0.1.3 now has a governed material Numeric surface for DELL, MU and NVDA: "
            "company totals, cash flow, capex, beginning and ending inventory, deterministic "
            "margins/free-cash-flow/inventory-days/capital-intensity formulas, and explicit "
            "case-specific gaps instead of three consolidated numbers being treated as F07 completion."
        ),
        "acceptance": {
            "all_requested_material_slots_governed": all(
                row["coverage"]["ungoverned_slots"] == 0
                for row in program_set["case_programs"]
            ),
            "formula_recalculation_validated": True,
            "entity_period_duration_unit_scale_source_formula_or_gap_bound": True,
            "old_FIN_0_1_2_evidence_packs_or_acceptances_rewritten": False,
            "model_provider_network_business_runs": [0, 0, 0, 0],
        },
        "stage_boundary": {
            "S1_02": "engineering_pass",
            "S1": "in_progress",
            "S1_03_source_exhaustion": "next_not_started",
            "S1_04_graph": "not_started",
            "S1_05_retrieval_usefulness": "not_started",
            "S2_to_S5": "not_started",
            "release": False,
        },
        "current_next": "FIN-0.1.3-013-S1-03-OFFICIAL-SOURCE-PARSER-FALLBACK-AND-ATTEMPT-BACKED-TYPED-GAP-COVERAGE",
        "known_boundary": (
            "S1-02 proves local Numeric truth and exhaustive governance only. Declared case-specific "
            "gaps are not source-exhaustion proof; source acquisition/parser fallback remains S1-03. "
            "No Graph, retrieval usefulness, research-content, model, full-chain, product acceptance, "
            "or release claim follows."
        ),
    }
    return {**body, "record_digest": canonical_digest(body)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
