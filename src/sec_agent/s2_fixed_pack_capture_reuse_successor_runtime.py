from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from sec_agent.s1_six_case_local_evidence_pack import canonical_digest
from sec_agent.s2_fixed_pack_capture_reuse_successor import (
    SUCCESSOR_NODE_ORDER,
    imported_output_map,
    validate_successor_case_input,
)
from sec_agent.s2_fixed_pack_research_runtime import (
    NODE_ORDER,
    build_node_request,
    evaluate_final_output,
    perform_node_call,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


ADMISSION_SCHEMA = (
    "fin_ia_0_1_3_s2_fixed_pack_capture_reuse_successor_admission_v1_0"
)
TERMINAL_SCHEMA = (
    "fin_ia_0_1_3_s2_fixed_pack_capture_reuse_successor_terminal_v1_0"
)
SCOPE = "FIN_0_1_3_S2_FIXED_PACK_DELL_CAPTURE_REUSE_SUCCESSOR"
ProviderCall = Callable[[Mapping[str, Any]], Mapping[str, Any]]
_DIGEST = re.compile(r"[0-9a-f]{64}")
_GIT_COMMIT = re.compile(r"[0-9a-f]{40}")


class S2FixedPackSuccessorRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S2FixedPackSuccessorRuntimeError(code)


def _utc(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError as exc:
        raise S2FixedPackSuccessorRuntimeError(
            "fixed_pack_successor_timestamp_invalid"
        ) from exc


def _digest(value: str, code: str) -> str:
    candidate = str(value or "").lower()
    _require(bool(_DIGEST.fullmatch(candidate)), code)
    return candidate


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _selected_predecessor_usage(bundle: Mapping[str, Any]) -> dict[str, Any]:
    usage = dict(bundle.get("predecessor_usage") or {})
    return {
        "provider_calls": int(usage.get("provider_calls") or 0),
        "model_calls": int(usage.get("model_calls") or 0),
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "estimated_usd": float(usage.get("estimated_usd") or 0.0),
        "retries": int(usage.get("retries") or 0),
        "fallbacks": int(usage.get("fallbacks") or 0),
    }


def _capacity_contract(
    *,
    profile: Mapping[str, Any],
    predecessor_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    predecessor = _selected_predecessor_usage(predecessor_bundle)
    profile_capacity = deepcopy(dict(profile.get("capacity") or {}))
    remaining = {
        "maximum_input_tokens": int(
            profile_capacity["maximum_input_tokens_per_case"]
        )
        - predecessor["input_tokens"],
        "maximum_output_tokens": int(
            profile_capacity["maximum_output_tokens_per_case"]
        )
        - predecessor["output_tokens"],
        "maximum_total_tokens": int(
            profile_capacity["maximum_total_tokens_per_case"]
        )
        - predecessor["total_tokens"],
        "maximum_estimated_usd": round(
            float(profile_capacity["maximum_estimated_usd_per_case"])
            - predecessor["estimated_usd"],
            8,
        ),
    }
    _require(
        predecessor["provider_calls"] == 6
        and predecessor["model_calls"] == 6
        and predecessor["retries"] == 0
        and predecessor["fallbacks"] == 0
        and all(value >= 0 for value in remaining.values()),
        "fixed_pack_successor_predecessor_usage_or_remaining_budget_invalid",
    )
    return {
        "predecessor_observed": predecessor,
        "successor_provider_calls_maximum": len(SUCCESSOR_NODE_ORDER),
        "combined_provider_attempts_maximum": 14,
        "logical_node_count": len(NODE_ORDER),
        "remaining_successor_budget": remaining,
        "cumulative_profile_capacity": profile_capacity,
        "retry_count": 0,
        "fallback_count": 0,
    }


def issue_successor_admission(
    *,
    case_input: Mapping[str, Any],
    predecessor_bundle: Mapping[str, Any],
    profile: Mapping[str, Any],
    execution_git_commit: str,
    runtime_sha256: str,
    runner_sha256: str,
    successor_contract_sha256: str,
    base_contract_sha256: str,
    profile_sha256: str,
    issued_at: str,
    expires_at: str,
    run_nonce: str,
    credential_present: bool,
    execution_mode: str = "live",
) -> dict[str, Any]:
    validate_successor_case_input(case_input, profile=profile)
    _require(
        bool(_GIT_COMMIT.fullmatch(str(execution_git_commit or ""))),
        "fixed_pack_successor_admission_git_commit_invalid",
    )
    for value in (
        runtime_sha256,
        runner_sha256,
        successor_contract_sha256,
        base_contract_sha256,
        profile_sha256,
        str(predecessor_bundle.get("import_bundle_digest") or ""),
    ):
        _digest(value, "fixed_pack_successor_admission_digest_invalid")
    _require(
        execution_mode in {"live", "fixture"},
        "fixed_pack_successor_admission_execution_mode_invalid",
    )
    if execution_mode == "live":
        _require(
            credential_present is True,
            "fixed_pack_successor_admission_credential_missing",
        )
    else:
        _require(
            credential_present is False,
            "fixed_pack_successor_fixture_must_not_claim_credential",
        )
    _require(
        _utc(expires_at) > _utc(issued_at),
        "fixed_pack_successor_admission_expiry_invalid",
    )
    _require(
        predecessor_bundle.get("case_key") == case_input.get("case_key") == "DELL"
        and predecessor_bundle.get("source_pack_digest")
        == case_input.get("source_pack_digest")
        and predecessor_bundle.get("case_input_digest")
        == case_input.get("base_model_visible_digest")
        and predecessor_bundle.get("semantic_retry") is False,
        "fixed_pack_successor_admission_predecessor_binding_invalid",
    )
    run_id = "fin013_s2_fixed_pack_dell_successor_" + canonical_digest(
        {
            "git": execution_git_commit,
            "nonce": run_nonce,
            "successor_input": case_input["model_visible_digest"],
            "predecessor_terminal": predecessor_bundle[
                "predecessor_terminal_digest"
            ],
        }
    )[:20]
    capacity = _capacity_contract(
        profile=profile, predecessor_bundle=predecessor_bundle
    )
    imported = [
        {
            "node_key": row["node_key"],
            "output_digest": row["output_digest"],
            "predecessor_call_id": row["predecessor_call_id"],
            "capture_digest": row["capture_digest"],
            "capture_file_sha256": row["capture_file_sha256"],
        }
        for row in predecessor_bundle.get("imported_outputs") or ()
    ]
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "scope": SCOPE,
        "admission_id": "admission::" + run_id,
        "run_id": run_id,
        "attempt_id": run_id + "::attempt_1",
        "runtime_identity": run_id + "::runtime_1",
        "case_key": "DELL",
        "base_case_input_digest": case_input["base_model_visible_digest"],
        "successor_case_input_digest": case_input["model_visible_digest"],
        "numeric_authority_digest": case_input["numeric_authority"][
            "numeric_authority_digest"
        ],
        "source_pack_digest": case_input["source_pack_digest"],
        "predecessor": {
            "run_id": predecessor_bundle["predecessor_run_id"],
            "attempt_id": predecessor_bundle["predecessor_attempt_id"],
            "terminal_digest": predecessor_bundle[
                "predecessor_terminal_digest"
            ],
            "import_bundle_digest": predecessor_bundle["import_bundle_digest"],
            "imported_outputs": imported,
            "failed_attempt_evidence": deepcopy(
                dict(predecessor_bundle["failed_attempt_evidence"])
            ),
        },
        "successor_node_order": list(SUCCESSOR_NODE_ORDER),
        "execution_git_commit": execution_git_commit,
        "runtime_sha256": runtime_sha256,
        "runner_sha256": runner_sha256,
        "successor_contract_sha256": successor_contract_sha256,
        "base_contract_sha256": base_contract_sha256,
        "profile_sha256": profile_sha256,
        "provider": {
            "name": str(profile.get("provider") or ""),
            "model": str(profile.get("model") or ""),
            "model_tier": str(profile.get("model_tier") or ""),
            "base_url": str(profile.get("base_url") or ""),
            "chat_completions_path": str(
                profile.get("chat_completions_path") or ""
            ),
        },
        "capacity": capacity,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "run_nonce_digest": canonical_digest(run_nonce),
        "credential_present": credential_present,
        "execution_mode": execution_mode,
        "state": "issued_unconsumed",
        "semantic_retry": False,
        "promotion_authority": False,
        "paired_baseline_same_input_proven": False,
    }
    return {**body, "admission_digest": canonical_digest(body)}


def validate_successor_admission(
    admission: Mapping[str, Any],
    *,
    case_input: Mapping[str, Any],
    predecessor_bundle: Mapping[str, Any],
    profile: Mapping[str, Any],
    execution_git_commit: str,
    runtime_sha256: str,
    runner_sha256: str,
    successor_contract_sha256: str,
    base_contract_sha256: str,
    profile_sha256: str,
    observed_at: str,
) -> None:
    validate_successor_case_input(case_input, profile=profile)
    body = deepcopy(dict(admission))
    digest = str(body.pop("admission_digest", ""))
    _require(
        admission.get("schema_version") == ADMISSION_SCHEMA
        and admission.get("scope") == SCOPE
        and admission.get("state") == "issued_unconsumed"
        and admission.get("semantic_retry") is False
        and admission.get("promotion_authority") is False
        and admission.get("paired_baseline_same_input_proven") is False
        and digest == canonical_digest(body),
        "fixed_pack_successor_admission_digest_or_state_invalid",
    )
    _require(
        admission.get("case_key") == "DELL"
        and admission.get("base_case_input_digest")
        == case_input.get("base_model_visible_digest")
        and admission.get("successor_case_input_digest")
        == case_input.get("model_visible_digest")
        and admission.get("numeric_authority_digest")
        == case_input.get("numeric_authority", {}).get(
            "numeric_authority_digest"
        )
        and admission.get("source_pack_digest")
        == case_input.get("source_pack_digest")
        and admission.get("successor_node_order") == list(SUCCESSOR_NODE_ORDER),
        "fixed_pack_successor_admission_input_binding_invalid",
    )
    predecessor = dict(admission.get("predecessor") or {})
    expected_imports = [
        {
            "node_key": row["node_key"],
            "output_digest": row["output_digest"],
            "predecessor_call_id": row["predecessor_call_id"],
            "capture_digest": row["capture_digest"],
            "capture_file_sha256": row["capture_file_sha256"],
        }
        for row in predecessor_bundle.get("imported_outputs") or ()
    ]
    _require(
        predecessor.get("run_id") == predecessor_bundle.get("predecessor_run_id")
        and predecessor.get("attempt_id")
        == predecessor_bundle.get("predecessor_attempt_id")
        and predecessor.get("terminal_digest")
        == predecessor_bundle.get("predecessor_terminal_digest")
        and predecessor.get("import_bundle_digest")
        == predecessor_bundle.get("import_bundle_digest")
        and predecessor.get("imported_outputs") == expected_imports
        and predecessor.get("failed_attempt_evidence")
        == predecessor_bundle.get("failed_attempt_evidence"),
        "fixed_pack_successor_admission_import_binding_invalid",
    )
    _require(
        admission.get("execution_git_commit") == execution_git_commit
        and admission.get("runtime_sha256") == runtime_sha256
        and admission.get("runner_sha256") == runner_sha256
        and admission.get("successor_contract_sha256")
        == successor_contract_sha256
        and admission.get("base_contract_sha256") == base_contract_sha256
        and admission.get("profile_sha256") == profile_sha256
        and admission.get("capacity")
        == _capacity_contract(
            profile=profile, predecessor_bundle=predecessor_bundle
        ),
        "fixed_pack_successor_admission_runtime_or_capacity_invalid",
    )
    mode = str(admission.get("execution_mode") or "")
    _require(
        mode in {"live", "fixture"},
        "fixed_pack_successor_admission_execution_mode_invalid",
    )
    if mode == "live":
        _require(
            admission.get("credential_present") is True,
            "fixed_pack_successor_admission_credential_missing",
        )
    else:
        _require(
            admission.get("credential_present") is False,
            "fixed_pack_successor_fixture_must_not_claim_credential",
        )
    _require(
        _utc(observed_at) <= _utc(str(admission.get("expires_at") or "")),
        "fixed_pack_successor_admission_expired",
    )


def _usage_from_receipts(
    receipts: list[dict[str, Any]], profile: Mapping[str, Any]
) -> dict[str, Any]:
    input_tokens = sum(int(row.get("input_tokens") or 0) for row in receipts)
    output_tokens = sum(int(row.get("output_tokens") or 0) for row in receipts)
    total_tokens = sum(int(row.get("total_tokens") or 0) for row in receipts)
    estimated_usd = (
        input_tokens * float(profile["capacity"]["input_usd_per_million_tokens"])
        + output_tokens
        * float(profile["capacity"]["output_usd_per_million_tokens"])
    ) / 1_000_000
    return {
        "provider_calls": len(receipts),
        "model_calls": len(receipts),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_usd": round(estimated_usd, 8),
    }


def _assert_cumulative_budget(
    *,
    predecessor_usage: Mapping[str, Any],
    successor_usage: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> None:
    capacity = dict(profile["capacity"])
    cumulative_input = int(predecessor_usage["input_tokens"]) + int(
        successor_usage["input_tokens"]
    )
    cumulative_output = int(predecessor_usage["output_tokens"]) + int(
        successor_usage["output_tokens"]
    )
    cumulative_total = int(predecessor_usage["total_tokens"]) + int(
        successor_usage["total_tokens"]
    )
    cumulative_cost = float(predecessor_usage["estimated_usd"]) + float(
        successor_usage["estimated_usd"]
    )
    _require(
        cumulative_input <= int(capacity["maximum_input_tokens_per_case"])
        and cumulative_output <= int(capacity["maximum_output_tokens_per_case"])
        and cumulative_total <= int(capacity["maximum_total_tokens_per_case"])
        and cumulative_cost <= float(capacity["maximum_estimated_usd_per_case"]),
        "fixed_pack_successor_cumulative_budget_exceeded_after_capture",
    )


def execute_successor_case(
    *,
    admission: Mapping[str, Any],
    case_input: Mapping[str, Any],
    predecessor_bundle: Mapping[str, Any],
    profile: Mapping[str, Any],
    execution_git_commit: str,
    runtime_sha256: str,
    runner_sha256: str,
    successor_contract_sha256: str,
    base_contract_sha256: str,
    profile_sha256: str,
    runtime_root: str | Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    provider_call: ProviderCall,
    observed_at: str,
) -> dict[str, Any]:
    validate_successor_admission(
        admission,
        case_input=case_input,
        predecessor_bundle=predecessor_bundle,
        profile=profile,
        execution_git_commit=execution_git_commit,
        runtime_sha256=runtime_sha256,
        runner_sha256=runner_sha256,
        successor_contract_sha256=successor_contract_sha256,
        base_contract_sha256=base_contract_sha256,
        profile_sha256=profile_sha256,
        observed_at=observed_at,
    )
    root = Path(runtime_root).resolve()
    _require(
        not root.exists(), "fixed_pack_successor_runtime_root_already_exists"
    )
    ledger_path = shared_ledger.path.resolve()
    _require(
        ledger_path != root and root not in ledger_path.parents,
        "fixed_pack_successor_ledger_inside_attempt_root",
    )
    root.mkdir(parents=True)
    captures_root = root / "raw_model_only" / "calls"
    shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=str(admission["scope"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=str(admission["runtime_identity"]),
        reserved_at=observed_at,
    )
    outputs = imported_output_map(predecessor_bundle)
    imported_lineage = [
        {key: deepcopy(row[key]) for key in row if key != "output"}
        for row in predecessor_bundle.get("imported_outputs") or ()
    ]
    calls: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    terminal_status = "completed"
    terminal_phase = "verifier"
    terminal_code = "fixed_pack_capture_reuse_successor_completed"
    active_node = "initialization"
    predecessor_usage = _selected_predecessor_usage(predecessor_bundle)
    try:
        for successor_call_index, node_key in enumerate(
            SUCCESSOR_NODE_ORDER, start=1
        ):
            active_node = node_key
            if successor_call_index > len(SUCCESSOR_NODE_ORDER):
                raise S2FixedPackSuccessorRuntimeError(
                    "fixed_pack_successor_provider_call_ceiling_exceeded"
                )
            logical_node_index = NODE_ORDER.index(node_key) + 1
            request = build_node_request(
                node_key=node_key,
                case_input=case_input,
                prior_outputs=outputs,
                profile=profile,
            )
            receipt, output, node_findings, fatal_code = perform_node_call(
                call_index=successor_call_index,
                logical_node_index=logical_node_index,
                node_key=node_key,
                request=request,
                provider_call=provider_call,
                captures_root=captures_root,
                observed_at=observed_at,
            )
            calls.append(receipt)
            outputs[node_key] = output
            findings.extend(node_findings)
            successor_usage = _usage_from_receipts(calls, profile)
            _assert_cumulative_budget(
                predecessor_usage=predecessor_usage,
                successor_usage=successor_usage,
                profile=profile,
            )
            if fatal_code:
                raise S2FixedPackSuccessorRuntimeError(fatal_code)
        findings.extend(
            evaluate_final_output(
                final_output=outputs.get("final_writer"), case_input=case_input
            )
        )
        if findings:
            terminal_status = "completed_with_findings"
            terminal_code = (
                "fixed_pack_capture_reuse_successor_completed_raw_candidate_not_promoted"
            )
    except S2FixedPackSuccessorRuntimeError as exc:
        terminal_status = "failed"
        terminal_phase = active_node
        terminal_code = exc.code
        findings.append(
            {
                "level": "L1",
                "code": exc.code,
                "disposition": "terminal_failure_no_retry_no_promotion",
            }
        )
    successor_usage = _usage_from_receipts(calls, profile)
    cumulative_usage = {
        "provider_attempts": predecessor_usage["provider_calls"]
        + successor_usage["provider_calls"],
        "model_calls": predecessor_usage["model_calls"]
        + successor_usage["model_calls"],
        "input_tokens": predecessor_usage["input_tokens"]
        + successor_usage["input_tokens"],
        "output_tokens": predecessor_usage["output_tokens"]
        + successor_usage["output_tokens"],
        "total_tokens": predecessor_usage["total_tokens"]
        + successor_usage["total_tokens"],
        "estimated_usd": round(
            predecessor_usage["estimated_usd"]
            + successor_usage["estimated_usd"],
            8,
        ),
    }
    terminal_body = {
        "schema_version": TERMINAL_SCHEMA,
        "scope": SCOPE,
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "case_key": "DELL",
        "base_case_input_digest": case_input["base_model_visible_digest"],
        "successor_case_input_digest": case_input["model_visible_digest"],
        "numeric_authority_digest": case_input["numeric_authority"][
            "numeric_authority_digest"
        ],
        "source_pack_digest": case_input["source_pack_digest"],
        "predecessor": {
            "run_id": predecessor_bundle["predecessor_run_id"],
            "attempt_id": predecessor_bundle["predecessor_attempt_id"],
            "terminal_digest": predecessor_bundle[
                "predecessor_terminal_digest"
            ],
            "import_bundle_digest": predecessor_bundle["import_bundle_digest"],
            "imported_node_lineage": imported_lineage,
            "failed_attempt_evidence": deepcopy(
                dict(predecessor_bundle["failed_attempt_evidence"])
            ),
            "usage": predecessor_usage,
        },
        "status": terminal_status,
        "terminal_phase": terminal_phase,
        "terminal_code": terminal_code,
        "successor_call_receipts": calls,
        "observed_counts": {
            "imported_usable_nodes": len(imported_lineage),
            "successor_provider_calls": len(calls),
            "successor_model_calls": len(calls),
            "combined_provider_attempts": cumulative_usage[
                "provider_attempts"
            ],
            "logical_outputs_present": len(outputs),
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "findings": len(findings),
        },
        "successor_usage": successor_usage,
        "cumulative_usage": cumulative_usage,
        "findings": findings,
        "raw_outputs": outputs,
        "direct_baseline_input_digest": case_input["base_model_visible_digest"],
        "agent_chain_input_digest": case_input["model_visible_digest"],
        "same_evidence_pack_proven": True,
        "same_input_pair_proven": False,
        "paired_assessment_eligible": False,
        "paired_baseline_required_later": True,
        "semantic_retry": False,
        "business_artifact_promoted": False,
        "qualified_human_acceptance_required": True,
        "observed_at": observed_at,
        "known_boundary": (
            "Five predecessor outputs are reused byte/digest-bound and eight new nodes "
            "are executed. The predecessor direct baseline did not see the augmented "
            "numeric authority, so strict same-input paired acceptance remains pending."
        ),
    }
    terminal = {**terminal_body, "terminal_digest": canonical_digest(terminal_body)}
    _atomic_json(root / "terminal.json", terminal)
    receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=terminal_status,
        terminal_phase=terminal_phase,
        terminal_code=terminal_code,
        terminal_result_digest=terminal["terminal_digest"],
        finalized_at=observed_at,
    )
    terminal["shared_admission_receipt"] = receipt.as_dict()
    _atomic_json(root / "terminal_with_receipt.json", terminal)
    return terminal


__all__ = [
    "ADMISSION_SCHEMA",
    "SCOPE",
    "TERMINAL_SCHEMA",
    "S2FixedPackSuccessorRuntimeError",
    "execute_successor_case",
    "issue_successor_admission",
    "validate_successor_admission",
]
