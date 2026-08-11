"""Validate P32 learning gate ledgers.

The validator checks reference integrity across:

- L1 learning source ledgers
- L2 extraction ledgers
- L1 coverage matrix
- L3 contract translation ledger

It is intentionally deterministic and does not call any model or network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


DEFAULT_FILES = {
    "financial_learning": Path("docs/project_os/financial_research_method_learning_ledger.jsonl"),
    "agent_learning": Path("docs/project_os/agent_engineering_pattern_learning_ledger.jsonl"),
    "financial_extraction": Path("docs/project_os/financial_research_method_extraction_ledger.jsonl"),
    "agent_extraction": Path("docs/project_os/agent_engineering_pattern_extraction_ledger.jsonl"),
    "coverage": Path("docs/project_os/p32_l1_coverage_matrix.jsonl"),
    "contracts": Path("docs/project_os/p32_l3_contract_translation_ledger.jsonl"),
}

ALLOWED_COVERAGE_STATUSES = {
    "sufficient_for_initial_l3",
    "partial_needs_more_l1",
    "gap_needs_l1",
}
ALLOWED_CONTRACT_STATUSES = {"candidate_l3_translated", "active", "rejected", "superseded"}
ALLOWED_EXTRACTION_STATUSES = {"candidate_l2_extracted", "active", "rejected", "superseded"}


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSONL: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{lineno}: expected JSON object")
        row["_ledger_path"] = str(path)
        row["_line_no"] = lineno
        rows.append(row)
    return rows


def require_fields(row: dict, fields: Iterable[str], errors: list[str]) -> None:
    ident = row.get("coverage_domain") or row.get("contract_id") or row.get("extraction_id") or row.get("source_id") or row.get("pattern_id")
    for field in fields:
        if row.get(field) in (None, "", []):
            errors.append(f"{row.get('_ledger_path')}:{row.get('_line_no')} {ident}: missing {field}")


def validate(repo_root: Path) -> dict:
    paths = {key: repo_root / path for key, path in DEFAULT_FILES.items()}
    rows = {key: read_jsonl(path) for key, path in paths.items()}
    errors: list[str] = []

    source_ids: set[str] = set()
    for key in ("financial_learning", "agent_learning"):
        for row in rows[key]:
            source_key = row.get("source_id") or row.get("pattern_id")
            require_fields(row, ["source_type", "source_title", "source_url", "status"], errors)
            if not source_key:
                errors.append(f"{row.get('_ledger_path')}:{row.get('_line_no')}: missing source_id/pattern_id")
            elif source_key in source_ids:
                errors.append(f"duplicate source/pattern id: {source_key}")
            else:
                source_ids.add(str(source_key))

    extraction_ids: set[str] = set()
    for key in ("financial_extraction", "agent_extraction"):
        for row in rows[key]:
            require_fields(row, ["extraction_id", "source_ids", "status"], errors)
            extraction_id = row.get("extraction_id")
            if extraction_id:
                if extraction_id in extraction_ids:
                    errors.append(f"duplicate extraction_id: {extraction_id}")
                extraction_ids.add(str(extraction_id))
            if row.get("status") not in ALLOWED_EXTRACTION_STATUSES:
                errors.append(f"{extraction_id}: invalid extraction status {row.get('status')}")
            for source_id in row.get("source_ids") or []:
                if source_id not in source_ids:
                    errors.append(f"{extraction_id}: unknown source_id {source_id}")

    coverage_domains: set[str] = set()
    coverage_counts = {"sufficient_for_initial_l3": 0, "partial_needs_more_l1": 0, "gap_needs_l1": 0}
    for row in rows["coverage"]:
        require_fields(row, ["coverage_domain", "track", "coverage_status", "next_action", "pass_condition"], errors)
        domain = row.get("coverage_domain")
        if domain:
            if domain in coverage_domains:
                errors.append(f"duplicate coverage_domain: {domain}")
            coverage_domains.add(str(domain))
        status = row.get("coverage_status")
        if status not in ALLOWED_COVERAGE_STATUSES:
            errors.append(f"{domain}: invalid coverage_status {status}")
        else:
            coverage_counts[status] += 1
        for source_id in row.get("current_source_ids") or []:
            if source_id not in source_ids:
                errors.append(f"{domain}: unknown current_source_id {source_id}")
        if status == "sufficient_for_initial_l3" and not row.get("current_source_ids"):
            errors.append(f"{domain}: sufficient coverage requires at least one current_source_id")
        if status == "gap_needs_l1" and row.get("supports_next_proof") is True:
            errors.append(f"{domain}: gap_needs_l1 cannot support next proof")

    contract_ids: set[str] = set()
    for row in rows["contracts"]:
        require_fields(
            row,
            [
                "contract_id",
                "source_extraction_ids",
                "target_runtime_objects",
                "target_agent_nodes",
                "input_contract",
                "output_contract",
                "acceptance_non_llm_gate",
                "status",
            ],
            errors,
        )
        contract_id = row.get("contract_id")
        if contract_id:
            if contract_id in contract_ids:
                errors.append(f"duplicate contract_id: {contract_id}")
            contract_ids.add(str(contract_id))
        if row.get("status") not in ALLOWED_CONTRACT_STATUSES:
            errors.append(f"{contract_id}: invalid contract status {row.get('status')}")
        for extraction_id in row.get("source_extraction_ids") or []:
            if extraction_id not in extraction_ids:
                errors.append(f"{contract_id}: unknown extraction_id {extraction_id}")
        for contract_field in ("input_contract", "output_contract"):
            value = row.get(contract_field)
            if not isinstance(value, dict) or not value.get("required_fields"):
                errors.append(f"{contract_id}: {contract_field} must include required_fields")
        if not row.get("acceptance_non_llm_gate"):
            errors.append(f"{contract_id}: missing acceptance_non_llm_gate")

    return {
        "status": "pass" if not errors else "fail",
        "error_count": len(errors),
        "errors": errors,
        "source_count": len(source_ids),
        "extraction_count": len(extraction_ids),
        "coverage_domain_count": len(coverage_domains),
        "coverage_counts": coverage_counts,
        "contract_count": len(contract_ids),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    result = validate(args.repo_root.resolve())
    if args.output:
        output = args.repo_root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
