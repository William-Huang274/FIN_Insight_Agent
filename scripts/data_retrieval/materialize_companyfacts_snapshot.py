"""Materialize an immutable captured snapshot using existing S2 financial rules.

This is ingestion, not evaluation. It neither loads acceptance answers nor
changes the live database. An explicit new output directory is required.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from financial_facts import (build_company_fact_mart, load_company_fact_mart_policy,
                             load_sec_snapshot_result_manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--rules", type=Path, default=ROOT / "configs/financial_facts/fin_ia_0_1_3_s2_company_financial_fact_mart_policy_v1_0.json")
    args = parser.parse_args()
    root = args.snapshot.resolve().parent
    snapshot = load_sec_snapshot_result_manifest(args.snapshot)
    # Copy rule definitions only. A company's expected answers do not authorize
    # ingestion of another company and are not supplied to the runtime.
    baseline = json.loads(args.rules.read_text(encoding="utf-8"))
    policy = {key: baseline[key] for key in ("schema_version", "status", "minimum_period_end",
              "allowed_forms", "metric_definitions", "authority")}
    policy.update(recorded_at=date.today().isoformat(), research_as_of=args.as_of.isoformat(),
                  source_bindings=[], acceptance_qrels=[])
    for source in snapshot.builder_source_bindings:
        binding = source.model_dump()
        for key in ("companyfacts_ref", "companyfacts_metadata_ref", "submissions_ref", "submissions_metadata_ref"):
            path = (root / binding[key]).resolve(strict=True)
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError("snapshot_source_path_outside_root")
            binding[key] = str(path)
        policy["source_bindings"].append(binding)
    loaded = load_company_fact_mart_policy(policy, require_acceptance_qrels=False)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "policy.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")
    try:
        result = build_company_fact_mart(loaded, repository_root=ROOT,
                                        sqlite_path=args.output / "financial-facts.sqlite")
    except Exception as exc:
        (args.output / "failure.json").write_text(json.dumps({"failure_type": type(exc).__name__,
            "snapshot_digest": snapshot.manifest_digest}), encoding="utf-8")
        raise
    (args.output / "build-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "counts": result["counts"]}))


if __name__ == "__main__":
    main()
