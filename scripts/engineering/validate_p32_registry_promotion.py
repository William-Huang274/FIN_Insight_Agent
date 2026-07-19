"""Validate P32 active registry promotion decisions.

This validator is deliberately stricter than the L1/L2/L3 learning gate:
source discovery and contract translation do not imply runtime promotion.
Only contracts proven by the P32-L4 deterministic fixture may be marked
``active_registry_ready``. Newly translated gap-domain contracts must remain
deferred until a matching deterministic fixture exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


CONTRACT_LEDGER = Path("docs/project_os/p32_l3_contract_translation_ledger.jsonl")
PROMOTION_LEDGER = Path("docs/project_os/p32_active_registry_promotion_ledger.jsonl")
FIXTURE_MANIFEST = Path("data/manifests/p32_l4_ai_semis_deterministic_fixture_v0_1.json")
P33_FIXTURE_MANIFESTS = [
    Path("data/manifests/p33_enterprise_rag_data_pipeline_fixture_v0_1.json"),
    Path("data/manifests/p33_sandbox_resource_scheduler_fixture_v0_1.json"),
    Path("data/manifests/p33_capital_market_feedback_fixture_v0_1.json"),
    Path("data/manifests/p33_workbench_artifact_review_surface_fixture_v0_1.json"),
    Path("data/manifests/p33_research_to_quant_factor_handoff_fixture_v0_1.json"),
]

ALLOWED_STATUSES = {"active_registry_ready", "deferred", "rejected", "superseded"}
ACTIVE_REQUIRED_FIELDS = [
    "runtime_entry_policy",
    "localization_notes",
    "do_not_promote",
    "rollback_gate",
    "evidence_refs",
]
DEFERRED_REQUIRED_FIELDS = [
    "defer_reason",
    "runtime_entry_policy",
    "localization_notes",
    "do_not_promote",
    "rollback_gate",
]


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


def _require(row: dict, fields: Iterable[str], errors: list[str]) -> None:
    contract_id = row.get("contract_id", "<missing>")
    for field in fields:
        if row.get(field) in (None, "", []):
            errors.append(f"{row.get('_ledger_path')}:{row.get('_line_no')} {contract_id}: missing {field}")


def _fixture_contract_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    contract_ids: set[str] = set()
    for contract_id in manifest.get("absorbed_contract_ids") or []:
        contract_ids.add(str(contract_id))
    if manifest.get("contract_id") and manifest.get("status") == "pass":
        contract_ids.add(str(manifest.get("contract_id")))
    for artifact in manifest.get("artifacts", []):
        plan = artifact.get("contract_aligned_plan") or {}
        for contract_id in plan.get("absorbed_contract_ids") or []:
            contract_ids.add(str(contract_id))
        for contract_id in plan.get("used_case_contract_ids") or []:
            contract_ids.add(str(contract_id))
    return contract_ids


def validate(repo_root: Path) -> dict:
    contracts_path = repo_root / CONTRACT_LEDGER
    promotions_path = repo_root / PROMOTION_LEDGER
    fixture_path = repo_root / FIXTURE_MANIFEST
    p33_fixture_paths = [repo_root / path for path in P33_FIXTURE_MANIFESTS]

    contract_rows = read_jsonl(contracts_path)
    promotion_rows = read_jsonl(promotions_path)
    fixture_contract_ids = set()
    fixture_contract_ids.update(_fixture_contract_ids(fixture_path))
    for p33_fixture_path in p33_fixture_paths:
        fixture_contract_ids.update(_fixture_contract_ids(p33_fixture_path))
    accepted_fixture_refs = {str(FIXTURE_MANIFEST).replace("\\", "/")}
    accepted_fixture_refs.update(str(path).replace("\\", "/") for path in P33_FIXTURE_MANIFESTS)

    errors: list[str] = []
    contract_ids = {str(row.get("contract_id")) for row in contract_rows if row.get("contract_id")}
    promotion_ids: set[str] = set()
    active_count = 0
    deferred_count = 0

    for row in promotion_rows:
        _require(row, ["contract_id", "promotion_decision", "promotion_scope", "status"], errors)
        contract_id = row.get("contract_id")
        status = row.get("status")
        if contract_id:
            if contract_id in promotion_ids:
                errors.append(f"duplicate promotion contract_id: {contract_id}")
            promotion_ids.add(str(contract_id))
            if contract_id not in contract_ids:
                errors.append(f"{contract_id}: promoted contract not found in {CONTRACT_LEDGER}")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{contract_id}: invalid promotion status {status}")

        if status == "active_registry_ready":
            active_count += 1
            _require(row, ACTIVE_REQUIRED_FIELDS, errors)
            if contract_id not in fixture_contract_ids:
                errors.append(f"{contract_id}: active promotion lacks P32-L4 fixture proof")
            evidence_refs = {str(ref).replace("\\", "/") for ref in (row.get("evidence_refs") or [])}
            if not evidence_refs.intersection(accepted_fixture_refs):
                errors.append(f"{contract_id}: active promotion must cite at least one accepted L4 fixture manifest")
            runtime_policy = str(row.get("runtime_entry_policy")).lower().replace("-", " ").replace("_", " ")
            if "feature flag" not in runtime_policy and "runtime alignment" not in runtime_policy:
                errors.append(f"{contract_id}: active runtime_entry_policy must be feature-flagged or runtime-alignment scoped")

        if status == "deferred":
            deferred_count += 1
            _require(row, DEFERRED_REQUIRED_FIELDS, errors)
            if "pending_l4_fixture" not in str(row.get("promotion_decision")):
                errors.append(f"{contract_id}: deferred row must state pending_l4_fixture promotion decision")

    return {
        "status": "pass" if not errors else "fail",
        "error_count": len(errors),
        "errors": errors,
        "contract_count": len(contract_ids),
        "fixture_contract_count": len(fixture_contract_ids),
        "promotion_count": len(promotion_ids),
        "active_registry_ready_count": active_count,
        "deferred_count": deferred_count,
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
