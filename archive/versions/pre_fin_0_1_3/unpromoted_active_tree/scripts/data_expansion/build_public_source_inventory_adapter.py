from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "fin_agent_public_source_inventory_adapter_v0.1"
SUMMARY_SCHEMA_VERSION = "fin_agent_public_source_inventory_adapter_summary_v0.1"
GATE_SCHEMA_VERSION = "fin_agent_public_source_inventory_adapter_gate_v0.1"
GAP_SCHEMA_VERSION = "fin_agent_public_source_inventory_gap_v0.1"
REJECT_SCHEMA_VERSION = "fin_agent_public_source_inventory_rejected_candidate_v0.1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote approved public-source gate rows into source inventory rows.")
    parser.add_argument("--policy", default="configs/data_sources/public_source_promotion_policy_v0_1.yaml")
    parser.add_argument(
        "--mapping-candidates",
        default="data/processed_private/public_sources/public_source_mapping_endpoint_gate_v0_1/mapping_candidates.jsonl",
    )
    parser.add_argument(
        "--endpoint-records",
        default="data/processed_private/public_sources/public_source_mapping_endpoint_gate_v0_1/endpoint_records.jsonl",
    )
    parser.add_argument(
        "--source-gaps",
        default="data/processed_private/public_sources/public_source_mapping_endpoint_gate_v0_1/source_gaps.jsonl",
    )
    parser.add_argument("--gate-rows", default="data/manifests/public_source_mapping_endpoint_gate_v0_1.jsonl")
    parser.add_argument(
        "--gate-summary",
        default="data/manifests/public_source_mapping_endpoint_gate_summary_v0_1.json",
    )
    parser.add_argument("--run-id", default="public_source_inventory_adapter_v0_1")
    parser.add_argument("--output-root", default="data/processed_private/public_sources")
    parser.add_argument(
        "--manifest-output",
        default="data/manifests/public_source_inventory_adapter_summary_v0_1.json",
    )
    parser.add_argument("--gate-output", default="data/manifests/public_source_inventory_adapter_v0_1.jsonl")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy_path = _resolve(args.policy)
    mapping_path = _resolve(args.mapping_candidates)
    endpoint_path = _resolve(args.endpoint_records)
    gaps_path = _resolve(args.source_gaps)
    source_gate_path = _resolve(args.gate_rows)
    gate_summary_path = _resolve(args.gate_summary)
    output_dir = _resolve(args.output_root) / args.run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    policy = load_policy(policy_path)
    mapping_rows = _read_jsonl(mapping_path)
    endpoint_rows = _read_jsonl(endpoint_path)
    source_gap_rows = _read_jsonl(gaps_path)
    source_gate_rows = _read_jsonl(source_gate_path)
    source_gate_summary = _read_json(gate_summary_path)
    input_paths = {
        "policy": policy_path,
        "mapping_candidates": mapping_path,
        "endpoint_records": endpoint_path,
        "source_gaps": gaps_path,
        "mapping_endpoint_gate_rows": source_gate_path,
        "mapping_endpoint_gate_summary": gate_summary_path,
    }
    output_paths = {
        "processed_private_output_dir": output_dir,
        "public_source_inventory_rows": output_dir / "public_source_inventory_rows.jsonl",
        "public_source_gap_rows": output_dir / "public_source_gap_rows.jsonl",
        "rejected_public_source_candidates": output_dir / "rejected_public_source_candidates.jsonl",
        "metadata": output_dir / "metadata.json",
        "adapter_gate_rows": _resolve(args.gate_output),
        "summary": _resolve(args.manifest_output),
    }
    result = build_inventory_adapter(
        policy=policy,
        mapping_rows=mapping_rows,
        endpoint_rows=endpoint_rows,
        source_gap_rows=source_gap_rows,
        source_gate_rows=source_gate_rows,
        source_gate_summary=source_gate_summary,
        run_id=args.run_id,
        input_paths=input_paths,
        output_paths=output_paths,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    _write_jsonl(output_paths["public_source_inventory_rows"], result["inventory_rows"])
    _write_jsonl(output_paths["public_source_gap_rows"], result["gap_rows"])
    _write_jsonl(output_paths["rejected_public_source_candidates"], result["rejected_rows"])
    _write_jsonl(output_paths["adapter_gate_rows"], result["adapter_gate_rows"])
    _write_json(output_paths["metadata"], result["summary"])
    _write_json(output_paths["summary"], result["summary"])
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def load_policy(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        policy = yaml.safe_load(handle) or {}
    validate_policy(policy)
    return policy


def validate_policy(policy: dict[str, Any]) -> None:
    if not isinstance(policy, dict):
        raise ValueError("Promotion policy must be a mapping.")
    if policy.get("schema_version") != "fin_agent_public_source_promotion_policy_v0_1":
        raise ValueError("Unsupported public source promotion policy schema_version.")
    source_policies = policy.get("source_policies")
    if not isinstance(source_policies, dict) or not source_policies:
        raise ValueError("Promotion policy must define source_policies.")
    for source_id, source_policy in source_policies.items():
        if not isinstance(source_policy, dict):
            raise ValueError(f"source_policies.{source_id} must be a mapping.")
        for rule_group in ("mapping_candidate_rules", "endpoint_record_rules"):
            for rule in source_policy.get(rule_group) or []:
                if not isinstance(rule, dict) or not rule.get("rule_id"):
                    raise ValueError(f"{source_id}.{rule_group} entries must have rule_id.")
                promotion = rule.get("promotion")
                if not isinstance(promotion, dict):
                    raise ValueError(f"{source_id}.{rule.get('rule_id')} must define promotion.")
                for key in ("promotion_status", "inventory_surface", "source_family", "claim_scope"):
                    if key not in promotion:
                        raise ValueError(f"{source_id}.{rule.get('rule_id')}.promotion missing {key}.")


def build_inventory_adapter(
    *,
    policy: dict[str, Any],
    mapping_rows: list[dict[str, Any]],
    endpoint_rows: list[dict[str, Any]],
    source_gap_rows: list[dict[str, Any]],
    source_gate_rows: list[dict[str, Any]],
    source_gate_summary: dict[str, Any],
    run_id: str,
    input_paths: dict[str, Path],
    output_paths: dict[str, Path],
    generated_at: str,
) -> dict[str, Any]:
    source_gate_by_id = {str(row.get("source_id") or ""): row for row in source_gate_rows}
    inventory_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []

    for row in mapping_rows:
        promoted = _promote_or_reject(
            row,
            source_row_kind="mapping_candidate",
            rule_group="mapping_candidate_rules",
            policy=policy,
            source_gate_by_id=source_gate_by_id,
            run_id=run_id,
        )
        if promoted["promoted"]:
            inventory_rows.append(promoted["row"])
        else:
            rejected_rows.append(promoted["row"])

    for row in endpoint_rows:
        promoted = _promote_or_reject(
            row,
            source_row_kind="endpoint_record",
            rule_group="endpoint_record_rules",
            policy=policy,
            source_gate_by_id=source_gate_by_id,
            run_id=run_id,
        )
        if promoted["promoted"]:
            inventory_rows.append(promoted["row"])
        else:
            rejected_rows.append(promoted["row"])

    for row in source_gap_rows:
        gap_rows.append(_source_gap_row(row, policy=policy, run_id=run_id))
    gap_rows.extend(_source_level_gap_rows(policy=policy, source_gate_by_id=source_gate_by_id, run_id=run_id))

    adapter_gate_rows = _build_adapter_gate_rows(
        policy=policy,
        source_gate_by_id=source_gate_by_id,
        inventory_rows=inventory_rows,
        rejected_rows=rejected_rows,
        gap_rows=gap_rows,
        generated_at=generated_at,
    )
    summary = _build_summary(
        policy=policy,
        source_gate_summary=source_gate_summary,
        inventory_rows=inventory_rows,
        rejected_rows=rejected_rows,
        gap_rows=gap_rows,
        adapter_gate_rows=adapter_gate_rows,
        run_id=run_id,
        input_paths=input_paths,
        output_paths=output_paths,
        generated_at=generated_at,
    )
    return {
        "inventory_rows": inventory_rows,
        "rejected_rows": rejected_rows,
        "gap_rows": gap_rows,
        "adapter_gate_rows": adapter_gate_rows,
        "summary": summary,
    }


def _promote_or_reject(
    row: dict[str, Any],
    *,
    source_row_kind: str,
    rule_group: str,
    policy: dict[str, Any],
    source_gate_by_id: dict[str, dict[str, Any]],
    run_id: str,
) -> dict[str, Any]:
    source_id = str(row.get("source_id") or "")
    source_policy = (policy.get("source_policies") or {}).get(source_id) or {}
    for rule in source_policy.get(rule_group) or []:
        if _matches_rule(row, rule.get("match") or {}):
            return {
                "promoted": True,
                "row": _inventory_row(
                    row,
                    source_row_kind=source_row_kind,
                    policy=policy,
                    source_policy=source_policy,
                    rule=rule,
                    source_gate=source_gate_by_id.get(source_id) or {},
                    run_id=run_id,
                ),
            }
    return {
        "promoted": False,
        "row": _rejected_row(
            row,
            source_row_kind=source_row_kind,
            policy=policy,
            source_policy=source_policy,
            source_gate=source_gate_by_id.get(source_id) or {},
            run_id=run_id,
        ),
    }


def _matches_rule(row: dict[str, Any], match: dict[str, Any]) -> bool:
    field_map = {
        "mapping_types": "mapping_type",
        "statuses": "status",
        "confidence": "confidence",
        "record_types": "record_type",
    }
    for match_key, row_key in field_map.items():
        allowed = match.get(match_key)
        if not allowed:
            continue
        allowed_values = {str(item) for item in _list_value(allowed)}
        if str(row.get(row_key) or "") not in allowed_values:
            return False
    return True


def _inventory_row(
    row: dict[str, Any],
    *,
    source_row_kind: str,
    policy: dict[str, Any],
    source_policy: dict[str, Any],
    rule: dict[str, Any],
    source_gate: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    promotion = dict(rule.get("promotion") or {})
    digest = _digest(row)
    runtime_source_family = str(promotion.get("runtime_source_family") or "").strip()
    return {
        "schema_version": SCHEMA_VERSION,
        "inventory_run_id": run_id,
        "row_id": f"{run_id}:{row.get('source_id')}:{source_row_kind}:{digest}",
        "promotion_policy_version": policy.get("schema_version"),
        "policy_rule_id": rule.get("rule_id"),
        "source_row_kind": source_row_kind,
        "source_id": row.get("source_id", ""),
        "source_gate_status": source_gate.get("status", ""),
        "source_gate_decision": source_gate.get("decision", ""),
        "source_status": source_policy.get("source_status", ""),
        "promotion_status": promotion.get("promotion_status", ""),
        "inventory_surface": promotion.get("inventory_surface", ""),
        "source_family": promotion.get("source_family", ""),
        "runtime_source_family": runtime_source_family,
        "source_tier": promotion.get("source_tier", ""),
        "claim_scope": promotion.get("claim_scope", ""),
        "allowed_claims": _list_value(promotion.get("allowed_claims")),
        "forbidden_claims": _list_value(promotion.get("forbidden_claims")),
        "required_next_gates": _list_value(promotion.get("required_next_gates")),
        "runtime_eligible": bool(promotion.get("runtime_eligible")),
        "resolver_eligible": bool(promotion.get("resolver_eligible")),
        "bounded_evidence_eligible": bool(promotion.get("bounded_evidence_eligible")),
        "context_only": bool(promotion.get("context_only")),
        "exact_value_authority": bool(promotion.get("exact_value_authority")),
        "ticker": str(row.get("ticker") or "").upper(),
        "company_name": str(row.get("company_name") or ""),
        "sector": str(row.get("sector") or ""),
        "category": str(row.get("category") or ""),
        "country": str(row.get("country") or ""),
        "mapping_type": str(row.get("mapping_type") or ""),
        "record_type": str(row.get("record_type") or ""),
        "source_row_status": str(row.get("status") or ""),
        "confidence": str(row.get("confidence") or ""),
        "external_id": str(row.get("external_id") or ""),
        "external_name": str(row.get("external_name") or ""),
        "source_url": str(row.get("source_url_logged") or row.get("source_url") or ""),
        "attributes": _dict_value(row.get("attributes")),
        "evidence": _dict_value(row.get("evidence")),
        "source_record_digest": digest,
    }


def _rejected_row(
    row: dict[str, Any],
    *,
    source_row_kind: str,
    policy: dict[str, Any],
    source_policy: dict[str, Any],
    source_gate: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    source_id = str(row.get("source_id") or "")
    digest = _digest(row)
    return {
        "schema_version": REJECT_SCHEMA_VERSION,
        "inventory_run_id": run_id,
        "row_id": f"{run_id}:{source_id}:{source_row_kind}:rejected:{digest}",
        "promotion_policy_version": policy.get("schema_version"),
        "source_row_kind": source_row_kind,
        "source_id": source_id,
        "source_gate_status": source_gate.get("status", ""),
        "source_gate_decision": source_gate.get("decision", ""),
        "source_status": source_policy.get("source_status", "not_in_policy"),
        "rejection_reason": source_policy.get("default_reject_reason", "no_promotion_rule_match"),
        "next_action": source_policy.get("default_next_action", "add_source_specific_promotion_policy"),
        "runtime_eligible": False,
        "resolver_eligible": False,
        "bounded_evidence_eligible": False,
        "exact_value_authority": False,
        "ticker": str(row.get("ticker") or "").upper(),
        "company_name": str(row.get("company_name") or ""),
        "sector": str(row.get("sector") or ""),
        "category": str(row.get("category") or ""),
        "country": str(row.get("country") or ""),
        "mapping_type": str(row.get("mapping_type") or ""),
        "record_type": str(row.get("record_type") or ""),
        "source_row_status": str(row.get("status") or ""),
        "confidence": str(row.get("confidence") or ""),
        "external_id": str(row.get("external_id") or ""),
        "external_name": str(row.get("external_name") or ""),
        "source_url": str(row.get("source_url_logged") or row.get("source_url") or ""),
        "source_record_digest": digest,
    }


def _source_gap_row(row: dict[str, Any], *, policy: dict[str, Any], run_id: str) -> dict[str, Any]:
    source_id = str(row.get("source_id") or "")
    source_policy = (policy.get("source_policies") or {}).get(source_id) or {}
    return {
        "schema_version": GAP_SCHEMA_VERSION,
        "inventory_run_id": run_id,
        "gap_kind": "source_mapping_or_endpoint_gap",
        "source_id": source_id,
        "source_status": source_policy.get("source_status", "not_in_policy"),
        "gap_type": str(row.get("gap_type") or "unknown"),
        "detail": str(row.get("detail") or ""),
        "next_action": source_policy.get("default_next_action", "inspect_source_gap"),
        "ticker": str(row.get("ticker") or "").upper(),
        "company_name": str(row.get("company_name") or ""),
        "sector": str(row.get("sector") or ""),
        "category": str(row.get("category") or ""),
        "country": str(row.get("country") or ""),
        "source_url": str(row.get("source_url") or ""),
        "runtime_eligible": False,
        "bounded_evidence_eligible": False,
        "source_record_digest": _digest(row),
    }


def _source_level_gap_rows(
    *,
    policy: dict[str, Any],
    source_gate_by_id: dict[str, dict[str, Any]],
    run_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_id, source_policy in sorted((policy.get("source_policies") or {}).items()):
        if source_id not in source_gate_by_id:
            continue
        for gap in source_policy.get("source_level_gaps") or []:
            if not isinstance(gap, dict):
                continue
            base = {
                "source_id": source_id,
                "gap_type": str(gap.get("gap_type") or "source_policy_blocker"),
                "detail": str(gap.get("detail") or ""),
                "next_action": str(gap.get("next_action") or source_policy.get("default_next_action") or ""),
            }
            rows.append(
                {
                    "schema_version": GAP_SCHEMA_VERSION,
                    "inventory_run_id": run_id,
                    "gap_kind": "source_policy_blocker",
                    "source_id": source_id,
                    "source_status": source_policy.get("source_status", ""),
                    "source_gate_status": source_gate_by_id[source_id].get("status", ""),
                    "source_gate_decision": source_gate_by_id[source_id].get("decision", ""),
                    "gap_type": base["gap_type"],
                    "detail": base["detail"],
                    "next_action": base["next_action"],
                    "ticker": "",
                    "company_name": "",
                    "sector": "",
                    "category": "",
                    "country": "",
                    "source_url": "",
                    "runtime_eligible": False,
                    "bounded_evidence_eligible": False,
                    "source_record_digest": _digest(base),
                }
            )
    return rows


def _build_adapter_gate_rows(
    *,
    policy: dict[str, Any],
    source_gate_by_id: dict[str, dict[str, Any]],
    inventory_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    source_ids = sorted(set(source_gate_by_id) | set((policy.get("source_policies") or {}).keys()))
    inventory_by_source = _count_by(inventory_rows, "source_id")
    rejected_by_source = _count_by(rejected_rows, "source_id")
    gap_by_source = _count_by(gap_rows, "source_id")
    runtime_by_source = _count_by([row for row in inventory_rows if row.get("runtime_eligible")], "source_id")
    evidence_by_source = _count_by([row for row in inventory_rows if row.get("bounded_evidence_eligible")], "source_id")
    rows = []
    for source_id in source_ids:
        source_policy = (policy.get("source_policies") or {}).get(source_id) or {}
        source_gate = source_gate_by_id.get(source_id) or {}
        promoted_count = inventory_by_source.get(source_id, 0)
        runtime_count = runtime_by_source.get(source_id, 0)
        evidence_count = evidence_by_source.get(source_id, 0)
        status = "promoted" if runtime_count else "held"
        if evidence_count:
            status = "promoted_context_only"
        if gap_by_source.get(source_id, 0) and runtime_count:
            status = "partial_promoted_with_gaps"
        rows.append(
            {
                "schema_version": GATE_SCHEMA_VERSION,
                "generated_at": generated_at,
                "source_id": source_id,
                "source_status": source_policy.get("source_status", "not_in_policy"),
                "source_gate_status": source_gate.get("status", ""),
                "source_gate_decision": source_gate.get("decision", ""),
                "adapter_status": status,
                "promoted_inventory_row_count": promoted_count,
                "runtime_eligible_row_count": runtime_count,
                "resolver_eligible_row_count": sum(
                    1 for row in inventory_rows if row.get("source_id") == source_id and row.get("resolver_eligible")
                ),
                "bounded_evidence_eligible_row_count": evidence_count,
                "rejected_candidate_count": rejected_by_source.get(source_id, 0),
                "gap_row_count": gap_by_source.get(source_id, 0),
            }
        )
    return rows


def _build_summary(
    *,
    policy: dict[str, Any],
    source_gate_summary: dict[str, Any],
    inventory_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
    adapter_gate_rows: list[dict[str, Any]],
    run_id: str,
    input_paths: dict[str, Path],
    output_paths: dict[str, Path],
    generated_at: str,
) -> dict[str, Any]:
    runtime_rows = [row for row in inventory_rows if row.get("runtime_eligible")]
    resolver_rows = [row for row in inventory_rows if row.get("resolver_eligible")]
    bounded_rows = [row for row in inventory_rows if row.get("bounded_evidence_eligible")]
    exact_rows = [row for row in inventory_rows if row.get("exact_value_authority")]
    gate_status_counts = Counter(str(row.get("adapter_status") or "") for row in adapter_gate_rows)
    next_gates = sorted(
        {
            str(item)
            for row in inventory_rows
            for item in _list_value(row.get("required_next_gates"))
            if str(item).strip()
        }
    )
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "policy_schema_version": policy.get("schema_version"),
        "policy_as_of_date": policy.get("as_of_date"),
        "status": "pass_with_runtime_inventory_candidates",
        "source_gate_status": source_gate_summary.get("status"),
        "source_gate_universe_company_count": source_gate_summary.get("universe_company_count"),
        "input_counts": {
            "mapping_candidate_rows": sum(1 for row in inventory_rows + rejected_rows if row.get("source_row_kind") == "mapping_candidate"),
            "endpoint_record_rows": sum(1 for row in inventory_rows + rejected_rows if row.get("source_row_kind") == "endpoint_record"),
            "source_gap_rows": sum(1 for row in gap_rows if row.get("gap_kind") == "source_mapping_or_endpoint_gap"),
        },
        "promoted_inventory_row_count": len(inventory_rows),
        "runtime_eligible_row_count": len(runtime_rows),
        "resolver_eligible_row_count": len(resolver_rows),
        "bounded_evidence_eligible_row_count": len(bounded_rows),
        "exact_value_authority_row_count": len(exact_rows),
        "rejected_candidate_count": len(rejected_rows),
        "gap_row_count": len(gap_rows),
        "source_policy_blocker_count": sum(1 for row in gap_rows if row.get("gap_kind") == "source_policy_blocker"),
        "promoted_sources": sorted(_count_by(runtime_rows, "source_id")),
        "bounded_evidence_sources": sorted(_count_by(bounded_rows, "source_id")),
        "promoted_counts_by_source": dict(sorted(_count_by(inventory_rows, "source_id").items())),
        "runtime_counts_by_source": dict(sorted(_count_by(runtime_rows, "source_id").items())),
        "resolver_counts_by_source": dict(sorted(_count_by(resolver_rows, "source_id").items())),
        "bounded_evidence_counts_by_source": dict(sorted(_count_by(bounded_rows, "source_id").items())),
        "rejected_counts_by_source": dict(sorted(_count_by(rejected_rows, "source_id").items())),
        "gap_counts_by_source": dict(sorted(_count_by(gap_rows, "source_id").items())),
        "promotion_counts_by_surface": dict(sorted(_count_by(inventory_rows, "inventory_surface").items())),
        "promotion_counts_by_claim_scope": dict(sorted(_count_by(inventory_rows, "claim_scope").items())),
        "promotion_counts_by_source_family": dict(sorted(_count_by(inventory_rows, "source_family").items())),
        "adapter_status_counts": dict(sorted(gate_status_counts.items())),
        "required_next_gates": next_gates,
        "runtime_policy": policy.get("runtime_policy") or {},
        "agent_promotion_allowed": True,
        "agent_promotion_scope": "feature_flagged_source_inventory_and_context_only",
        "primary_disclosure_evidence_promotion_allowed": False,
        "company_product_sales_promotion_allowed": False,
        "outputs": {key: _repo_path(path) for key, path in output_paths.items()},
        "inputs": {key: _repo_path(path) for key, path in input_paths.items()},
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        value = str(row.get(key) or "")
        if value:
            counts[value] += 1
    return dict(counts)


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _digest(row: dict[str, Any]) -> str:
    data = json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(data).hexdigest()[:16]


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
