from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import StrictModel, canonical_digest
from sec_agent.financial_research_generalization_contract import (
    compile_case_research_contract,
    load_financial_research_contract,
)
from sec_agent.financial_research_source_object_vertical import (
    POLICY_SCHEMA as VERTICAL_POLICY_SCHEMA,
    RUN_SCOPE as VERTICAL_RUN_SCOPE,
    DeclaredResidualGap,
    FinancialQueryLane,
    FinancialSourceObjectVerticalPolicy,
    HierarchyFinding,
    LocalRetrievalAsset,
    ReviewedCandidateBinding,
    execute_financial_source_object_vertical,
    normalized_sha256,
    validate_financial_source_object_vertical_policy,
)


TRANSFER_POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_mu_nvda_core_unchanged_transfer_policy_v1_0"
)
TRANSFER_RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_mu_nvda_core_unchanged_transfer_result_v1_0"
)
TRANSFER_RUN_SCOPE = "S1_MU_NVDA_CORE_UNCHANGED_TRANSFER"
EXPECTED_CASE_KEYS = ("MU", "NVDA")


class FinancialResearchTransferError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class LockedTransferArtifact(StrictModel):
    artifact_id: str
    path: str
    normalized_sha256: str
    role: str


class DellVerticalReference(StrictModel):
    result_ref: str
    result_digest: str
    compiled_core_fingerprint: str


class TransferCaseDefinition(StrictModel):
    case_key: str
    contract_ref: str
    result_ref: str
    assets: tuple[LocalRetrievalAsset, ...]
    query_lanes: tuple[FinancialQueryLane, ...]
    reviewed_candidate_bindings: tuple[ReviewedCandidateBinding, ...]
    declared_residual_gaps: tuple[DeclaredResidualGap, ...]
    hierarchy_findings: tuple[HierarchyFinding, ...]


class CoreUnchangedTransferPolicy(StrictModel):
    schema_version: str
    contract_ref: str
    run_scope: str
    recorded_at: str
    generalization_contract_ref: str
    generalization_contract_sha256: str
    expected_core_fingerprint: str
    dell_vertical_reference: DellVerticalReference
    locked_artifacts: tuple[LockedTransferArtifact, ...]
    case_policies: tuple[TransferCaseDefinition, ...]
    hard_boundaries: dict[str, Any]


def load_core_unchanged_transfer_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> CoreUnchangedTransferPolicy:
    root = Path(repo_root).resolve()
    try:
        policy = CoreUnchangedTransferPolicy.model_validate(
            json.loads(Path(path).read_text(encoding="utf-8"))
        )
    except Exception as exc:
        raise FinancialResearchTransferError("transfer_policy_shape_invalid") from exc
    if (
        policy.schema_version != TRANSFER_POLICY_SCHEMA
        or policy.run_scope != TRANSFER_RUN_SCOPE
    ):
        raise FinancialResearchTransferError("transfer_policy_identity_invalid")
    if tuple(row.case_key for row in policy.case_policies) != EXPECTED_CASE_KEYS:
        raise FinancialResearchTransferError("transfer_case_order_or_identity_invalid")
    _validate_zero_call_boundary(policy.hard_boundaries)
    _validate_locked_artifacts(policy, repo_root=root)
    _validate_dell_reference(policy, repo_root=root)

    contract_path = _resolve(root, policy.generalization_contract_ref)
    if normalized_sha256(contract_path) != policy.generalization_contract_sha256:
        raise FinancialResearchTransferError(
            "transfer_generalization_contract_digest_mismatch"
        )
    contract = load_financial_research_contract(contract_path)
    for case in policy.case_policies:
        compiled = compile_case_research_contract(contract, case.case_key)
        if compiled.core_fingerprint != policy.expected_core_fingerprint:
            raise FinancialResearchTransferError("transfer_core_fingerprint_mismatch")
        vertical = _to_vertical_policy(policy, case)
        validate_financial_source_object_vertical_policy(vertical, compiled=compiled)
    return policy


def execute_core_unchanged_transfer(
    *,
    policy: CoreUnchangedTransferPolicy,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    before = _locked_digest_map(policy, repo_root=root)
    contract = load_financial_research_contract(
        _resolve(root, policy.generalization_contract_ref)
    )
    case_results: dict[str, dict[str, Any]] = {}
    case_summaries: list[dict[str, Any]] = []
    for case in policy.case_policies:
        compiled = compile_case_research_contract(contract, case.case_key)
        if compiled.core_fingerprint != policy.expected_core_fingerprint:
            raise FinancialResearchTransferError("transfer_core_fingerprint_mismatch")
        vertical = _to_vertical_policy(policy, case)
        result = execute_financial_source_object_vertical(
            policy=vertical,
            compiled=compiled,
            repo_root=root,
        )
        case_results[case.case_key] = result
        case_summaries.append(_summarise_case(case, result=result))
    after = _locked_digest_map(policy, repo_root=root)
    locked_unchanged = before == after
    cases_pass = all(row["transfer_acceptance"] == "pass" for row in case_summaries)
    observed_calls = {
        key: sum(int(result["observed_calls"][key]) for result in case_results.values())
        for key in (
            "network",
            "provider",
            "model",
            "embedding",
            "rerank",
            "evidence_promotion",
        )
    }
    zero_calls = all(value == 0 for value in observed_calls.values())
    status = (
        "engineering_pass_core_unchanged_transfer"
        if locked_unchanged and cases_pass and zero_calls
        else "engineering_blocked_core_transfer_or_candidate_terminalization_failure"
    )
    body = {
        "schema_version": TRANSFER_RESULT_SCHEMA,
        "contract_ref": policy.contract_ref,
        "run_scope": policy.run_scope,
        "recorded_at": policy.recorded_at,
        "status": status,
        "dell_reference": policy.dell_vertical_reference.model_dump(mode="json"),
        "expected_core_fingerprint": policy.expected_core_fingerprint,
        "locked_artifacts_before": before,
        "locked_artifacts_after": after,
        "case_summaries": case_summaries,
        "observed_calls": observed_calls,
        "stage_acceptance": {
            "locked_core_unchanged": locked_unchanged,
            "mu_transfer_pass": _case_pass(case_summaries, "MU"),
            "nvda_transfer_pass": _case_pass(case_summaries, "NVDA"),
            "ticker_specific_core_branch_added": False,
            "held_out_generalization_admitted": status
            == "engineering_pass_core_unchanged_transfer",
            "sparse_dense_rebuild_admitted": False,
            "external_supplement_admitted": False,
            "model_synthesis_admitted": False,
        },
        "compatibility_finding": {
            "code": "legacy_dell_vertical_executor_namespace",
            "blocking": False,
            "meaning": (
                "The frozen executor retains a DELL-named internal run scope and raw result "
                "schema. Transfer acceptance is case-neutral and is computed by this wrapper; "
                "the legacy labels must be renamed only in a later versioned contract change."
            ),
        },
        "known_boundary": (
            "This is a real-local, zero-network, zero-model transfer proof. Qualified rows remain "
            "candidates rather than Evidence. Passing transfer admits held-out identity tests only; "
            "it does not admit index rebuild, external supplement, Evidence promotion, or model synthesis."
        ),
    }
    return {
        "case_results": case_results,
        "transfer_result": {**body, "result_digest": canonical_digest(body)},
    }


def _to_vertical_policy(
    policy: CoreUnchangedTransferPolicy,
    case: TransferCaseDefinition,
) -> FinancialSourceObjectVerticalPolicy:
    return FinancialSourceObjectVerticalPolicy(
        schema_version=VERTICAL_POLICY_SCHEMA,
        contract_ref=case.contract_ref,
        run_scope=VERTICAL_RUN_SCOPE,
        recorded_at=policy.recorded_at,
        case_key=case.case_key,
        generalization_contract_ref=policy.generalization_contract_ref,
        generalization_contract_sha256=policy.generalization_contract_sha256,
        assets=case.assets,
        query_lanes=case.query_lanes,
        reviewed_candidate_bindings=case.reviewed_candidate_bindings,
        declared_residual_gaps=case.declared_residual_gaps,
        hierarchy_findings=case.hierarchy_findings,
        hard_boundaries=dict(policy.hard_boundaries),
    )


def _summarise_case(
    case: TransferCaseDefinition,
    *,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    evaluation = dict(result["candidate_pack_evaluation"])
    missing_pairs = {
        (str(row["slot_id"]), str(facet))
        for row in evaluation["slot_evaluations"]
        for facet in row["missing_facets"]
    }
    declared_pairs = {
        (row.slot_id, row.facet_id) for row in case.declared_residual_gaps
    }
    undeclared = sorted(missing_pairs - declared_pairs)
    redundant = sorted(declared_pairs - missing_pairs)
    qualification_failures = [
        row
        for row in result["candidate_qualifications"]
        if row["qualification_status"] != "qualified"
    ]
    rejected = list(evaluation["rejected_candidates"])
    zero_calls = all(int(value) == 0 for value in result["observed_calls"].values())
    passed = not qualification_failures and not rejected and not undeclared and not redundant
    passed = passed and zero_calls
    return {
        "case_key": case.case_key,
        "result_ref": case.result_ref,
        "raw_executor_schema": result["schema_version"],
        "raw_executor_status": result["status"],
        "result_digest": result["result_digest"],
        "compiled_case_digest": result["compiled_case_digest"],
        "compiled_core_fingerprint": result["compiled_core_fingerprint"],
        "observed_counts": result["observed_counts"],
        "slot_statuses": {
            str(row["slot_id"]): str(row["status"])
            for row in evaluation["slot_evaluations"]
        },
        "undeclared_missing_facets": [f"{slot}:{facet}" for slot, facet in undeclared],
        "redundant_declared_gaps": [f"{slot}:{facet}" for slot, facet in redundant],
        "qualification_failure_count": len(qualification_failures),
        "candidate_contract_rejection_count": len(rejected),
        "observed_calls": dict(result["observed_calls"]),
        "transfer_acceptance": "pass" if passed else "fail",
    }


def _case_pass(rows: list[dict[str, Any]], case_key: str) -> bool:
    return any(
        row["case_key"] == case_key and row["transfer_acceptance"] == "pass"
        for row in rows
    )


def _validate_zero_call_boundary(boundary: Mapping[str, Any]) -> None:
    required_zero = {
        "network",
        "provider",
        "model",
        "embedding",
        "rerank",
        "evidence_promotion",
    }
    if any(int(boundary.get(key, -1)) != 0 for key in required_zero):
        raise FinancialResearchTransferError("transfer_zero_call_boundary_invalid")
    if boundary.get("qrels_loaded_after_candidate_generation") is not True:
        raise FinancialResearchTransferError("transfer_candidate_order_invalid")
    if boundary.get("core_modification_allowed") is not False:
        raise FinancialResearchTransferError("transfer_core_modification_boundary_invalid")


def _validate_locked_artifacts(
    policy: CoreUnchangedTransferPolicy,
    *,
    repo_root: Path,
) -> None:
    identities = {row.artifact_id for row in policy.locked_artifacts}
    if len(identities) != len(policy.locked_artifacts) or len(identities) < 3:
        raise FinancialResearchTransferError("transfer_locked_artifact_identity_invalid")
    actual = _locked_digest_map(policy, repo_root=repo_root)
    expected = {
        row.artifact_id: row.normalized_sha256 for row in policy.locked_artifacts
    }
    if actual != expected:
        raise FinancialResearchTransferError("transfer_locked_artifact_digest_mismatch")


def _validate_dell_reference(
    policy: CoreUnchangedTransferPolicy,
    *,
    repo_root: Path,
) -> None:
    path = _resolve(repo_root, policy.dell_vertical_reference.result_ref)
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FinancialResearchTransferError("transfer_dell_reference_missing") from exc
    if (
        result.get("result_digest") != policy.dell_vertical_reference.result_digest
        or result.get("compiled_core_fingerprint")
        != policy.dell_vertical_reference.compiled_core_fingerprint
        or result.get("compiled_core_fingerprint") != policy.expected_core_fingerprint
    ):
        raise FinancialResearchTransferError("transfer_dell_reference_mismatch")
    body = {key: value for key, value in result.items() if key != "result_digest"}
    if canonical_digest(body) != result.get("result_digest"):
        raise FinancialResearchTransferError("transfer_dell_reference_integrity_invalid")


def _locked_digest_map(
    policy: CoreUnchangedTransferPolicy,
    *,
    repo_root: Path,
) -> dict[str, str]:
    return {
        row.artifact_id: normalized_sha256(_resolve(repo_root, row.path))
        for row in policy.locked_artifacts
    }


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


__all__ = [
    "CoreUnchangedTransferPolicy",
    "FinancialResearchTransferError",
    "TRANSFER_POLICY_SCHEMA",
    "TRANSFER_RESULT_SCHEMA",
    "TRANSFER_RUN_SCOPE",
    "execute_core_unchanged_transfer",
    "load_core_unchanged_transfer_policy",
]
