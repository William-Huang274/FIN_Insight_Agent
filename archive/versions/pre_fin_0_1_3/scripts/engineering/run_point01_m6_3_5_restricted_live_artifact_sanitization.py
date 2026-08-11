"""Create a safe audit projection from the quarantined v4 live artifact.

The v4 result and its temporary SQLite store are immutable restricted evidence:
they are neither rewritten nor used as runtime input.  This offline utility
reads the JSON once, whitelists audit fields, replaces the colliding invocation
identifier with a new digest-bound projection identity, and writes a separate
non-citable audit projection.  It never resolves a receipt, starts a client,
or opens a network connection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_3_5_restricted_live_artifact_policy_v1_0.json"
DEFAULT_INPUT = ROOT / "data/manifests/point01_m6_3_5_v4_single_fixed_nvda_10k_live_pilot_result_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_3_5_v5_sanitized_authorized_live_audit_projection_v1_0.json"

FORBIDDEN_KEYS = frozenset(
    {
        "approval_nonce",
        "global_approval_nonce",
        "user_agent",
        "raw_document",
        "raw_html",
    }
)


class RestrictedLiveArtifactError(RuntimeError):
    """The restricted source cannot safely form a superseding projection."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _read_mapping(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RestrictedLiveArtifactError(f"restricted_artifact_unreadable:{path.name}") from exc
    if not isinstance(value, dict):
        raise RestrictedLiveArtifactError("restricted_artifact_mapping_required")
    return value


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RestrictedLiveArtifactError(f"restricted_artifact_{name}_mapping_required")
    return value


def _restricted_path_ref(path: Path) -> str:
    """Return a publish-safe source reference for repo and isolated tests."""
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return f"external_restricted_input/{path.name}"


def _assert_no_raw_secret(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_string = str(key)
            if key_string in FORBIDDEN_KEYS:
                raise RestrictedLiveArtifactError(f"sanitized_projection_forbidden_key:{key_string}")
            _assert_no_raw_secret(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _assert_no_raw_secret(nested)


def _object_view(
    value: Mapping[str, Any],
    *,
    kind: str,
    execution_instance_id: str,
    superseding_receipt_version_ref: str,
    restricted_original_receipt_digest: str,
) -> dict[str, Any]:
    """Whitelist an unpromoted object without carrying old execution refs."""
    common = {
        "kind": kind,
        "execution_instance_id": execution_instance_id,
        "superseding_receipt_version_ref": superseding_receipt_version_ref,
        "restricted_original_receipt_digest": restricted_original_receipt_digest,
        "restricted_original_content_digest": str(value["content_digest"]),
        "promotion_status": str(value.get("promotion_status", "unpromoted")),
        "writer_citable": bool(value.get("writer_citable", False)),
        "domain_judgment_eligible": bool(value.get("domain_judgment_eligible", False)),
    }
    if kind == "candidate":
        return {
            **common,
            "candidate_id": str(value["candidate_id"]),
            "source_document_sha256": str(value["source_document_sha256"]),
            "source_url": str(value["source_url"]),
            "table_coordinate": str(value["table_coordinate"]),
            "table_heading_normalized": str(value["table_heading_normalized"]),
            "unit_caption_normalized": str(value["unit_caption_normalized"]),
            "row_label_normalized": str(value["row_label_normalized"]),
            "normalized_period": str(value["normalized_period"]),
            "financial_statement_role": str(value["financial_statement_role"]),
        }
    if kind == "parser":
        return {
            **common,
            "parser_candidate_id": str(value["parser_candidate_id"]),
            "parsed_table_digest": str(value["parsed_table_digest"]),
            "table_coordinate": str(value["table_coordinate"]),
            "parse_status": str(value["parse_status"]),
        }
    if kind == "fact":
        return {
            **common,
            "normalized_fact_id": str(value["normalized_fact_id"]),
            "normalized_value": str(value["normalized_value"]),
            "unit": str(value["unit"]),
            "scale_multiplier": int(value["scale_multiplier"]),
            "period": str(value["period"]),
            "source_coordinate": str(value["source_coordinate"]),
        }
    if kind == "trace":
        return {
            **common,
            "numeric_trace_id": str(value["numeric_trace_id"]),
            "input_digest": str(value["input_digest"]),
            "output_value": str(value["output_value"]),
            "program_steps": list(value["program_steps"]),
        }
    raise RestrictedLiveArtifactError(f"unsupported_lineage_kind:{kind}")


def build_projection(*, original: Mapping[str, Any], original_path: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    receipt = _require_mapping(original.get("receipt"), "receipt")
    candidate = _require_mapping(original.get("candidate"), "candidate")
    parser = _require_mapping(original.get("parser"), "parser")
    fact = _require_mapping(original.get("fact"), "fact")
    trace = _require_mapping(original.get("trace"), "trace")
    package = _require_mapping(original.get("approval_package"), "approval_package")
    source = _require_mapping(receipt.get("source_document"), "source_document")
    raw_nonce = str(receipt.get("global_approval_nonce") or "")
    if len(raw_nonce) < 16:
        raise RestrictedLiveArtifactError("restricted_original_raw_nonce_not_present_for_sanitization")
    if original.get("status") != "pass" or original.get("execution_status") != "positive_chain_persisted":
        raise RestrictedLiveArtifactError("restricted_original_not_successful_authorized_pilot")
    if original.get("external_call_count") != 1 or original.get("tool_invocation_count") != 1:
        raise RestrictedLiveArtifactError("restricted_original_single_send_contract_invalid")
    if source.get("raw_document_persisted") is not False:
        raise RestrictedLiveArtifactError("restricted_original_raw_document_persistence_invalid")

    original_sha256 = _sha256_bytes(original_path.read_bytes())
    original_invocation_id = str(receipt["invocation_id"])
    execution_instance_id = "sec_document_execution_" + _sha256_text(
        json.dumps(
            {
                "restricted_original_sha256": original_sha256,
                "global_approval_id": receipt["global_approval_id"],
                "global_approval_receipt_digest": receipt["global_approval_receipt_digest"],
                "request_digest": receipt["request_digest"],
                "plan_digest": receipt["tool_selection_plan_digest"],
                "source_document_sha256": source["document_content_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )[:24]
    superseding_receipt_version_ref = f"{execution_instance_id}:restricted_superseding_projection"
    projection = {
        "result_version": str(policy["sanitized_projection"]["result_version"]),
        "status": "pass",
        "execution_state": str(policy["sanitized_projection"]["allowed_terminal_execution_state"]),
        "artifact_classification": "sanitized_superseding_audit_projection_non_citable",
        "restricted_original": {
            "path": _restricted_path_ref(original_path),
            "sha256": original_sha256,
            "classification": "restricted_quarantined_audit_input",
            "git_publish": False,
            "downstream_consumption": False,
            "retention_policy_ref": str(policy["policy_ref"]),
            "original_invocation_id_sha256": _sha256_text(original_invocation_id),
        },
        "package_authority_boundary": {
            "package_ref": str(package["package_ref"]),
            "package_digest": str(package["package_digest"]),
            "manifest_digest": str(package["manifest_digest"]),
            "live_send_requires_separate_exact_receipt": True,
            "evidence_promotion": False,
            "writer_domain_judgment_m6_7_full_chain": False,
        },
        "execution_authorization_snapshot": {
            "authorization_kind": "fixed_store_exact_one_shot_receipt",
            "live_send_authorized_by_exact_receipt": True,
            "receipt_identity": f"{receipt['global_approval_id']}:consumed",
            "receipt_state": "consumed",
            "approval_nonce_sha256": _sha256_text(raw_nonce),
            "receipt_digest": str(receipt["global_approval_receipt_digest"]),
            "authority_store_identity": str(receipt["global_approval_store_identity"]),
            "execution_instance_id": execution_instance_id,
        },
        "execution_outcome": {
            "execution_status": "positive_chain_persisted",
            "invocation_state": str(receipt["invocation_state"]),
            "downstream_status": str(receipt["downstream_status"]),
            "external_call_count": 1,
            "tool_invocation_count": 1,
            "retry_call_count": int(receipt["retry_call_count"]),
            "fallback_call_count": int(receipt["fallback_call_count"]),
            "model_call_count": 0,
            "raw_document_persisted": False,
            "source_document_sha256": str(source["document_content_sha256"]),
            "response_status_code": int(source["response_status_code"]),
        },
        "lineage": {
            "execution_instance_id": execution_instance_id,
            "request_id": str(receipt["request_id"]),
            "request_digest": str(receipt["request_digest"]),
            "tool_selection_plan_id": str(receipt["tool_selection_plan_id"]),
            "tool_selection_plan_digest": str(receipt["tool_selection_plan_digest"]),
            "receipt_version_ref": superseding_receipt_version_ref,
        },
        "unpromoted_lineage": {
            "candidate": _object_view(candidate, kind="candidate", execution_instance_id=execution_instance_id, superseding_receipt_version_ref=superseding_receipt_version_ref, restricted_original_receipt_digest=str(receipt["content_digest"])),
            "parser": _object_view(parser, kind="parser", execution_instance_id=execution_instance_id, superseding_receipt_version_ref=superseding_receipt_version_ref, restricted_original_receipt_digest=str(receipt["content_digest"])),
            "fact": _object_view(fact, kind="fact", execution_instance_id=execution_instance_id, superseding_receipt_version_ref=superseding_receipt_version_ref, restricted_original_receipt_digest=str(receipt["content_digest"])),
            "trace": _object_view(trace, kind="trace", execution_instance_id=execution_instance_id, superseding_receipt_version_ref=superseding_receipt_version_ref, restricted_original_receipt_digest=str(receipt["content_digest"])),
        },
        "downstream_firewall": {
            "evidence_promotion_authorized": False,
            "writer_citable": False,
            "domain_judgment_eligible": False,
            "context_ingestion_authorized": False,
            "m6_4_sourcehunter_authorized": False,
            "m6_6_authoritative_gate_authorized": False,
            "m6_7_judgment_authorized": False,
        },
        "execution_counts": {
            "external_call_count": 1,
            "network_request_count": 1,
            "tool_invocation_count": 1,
            "retry_count": 0,
            "fallback_count": 0,
            "model_call_count": 0,
        },
    }
    _assert_no_raw_secret(projection)
    return projection


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a sanitized audit projection from restricted v4 M6.3/M6.5 live evidence.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    projection = build_projection(
        original=_read_mapping(input_path),
        original_path=input_path,
        policy=_read_mapping(POLICY_PATH),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": projection["status"], "output": str(output_path), "external_call_count": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
