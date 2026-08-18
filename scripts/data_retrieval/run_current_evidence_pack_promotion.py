from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
for candidate in (ROOT, SRC_ROOT):
    value = str(candidate)
    if value not in sys.path:
        sys.path.insert(0, value)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    canonical_digest,
    file_sha256,
    validate_reviewed_evidence_pack,
)
from sec_agent.research.reviewed_evidence_anchor import (  # noqa: E402
    compile_reviewed_evidence_anchor_catalog,
    load_reviewed_evidence_anchor_catalog,
)
from retrieval.current_runtime_binding import (  # noqa: E402
    build_current_s1_runtime_binding_receipt,
)


AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_current_evidence_pack_promotion_authority_v1_0"
)
PACK_SET_AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_current_evidence_pack_set_promotion_authority_v2_0"
)
COMPOSED_RESULT_SCHEMA_VERSION = (
    "fin_ia_current_research_evidence_pack_result_v1_1"
)
COMPOSED_RESULT_STATUS = (
    "terminal_succeeded_current_pack_composition_with_declared_gaps"
)
EXECUTION_RESULT_SCHEMA_VERSION = (
    "fin_ia_current_evidence_pack_promotion_result_v1_0"
)
PACK_SET_EXECUTION_RESULT_SCHEMA_VERSION = (
    "fin_ia_current_evidence_pack_set_promotion_result_v2_0"
)


class CurrentEvidencePackPromotionError(RuntimeError):
    """A current Evidence Pack promotion was not exactly authorized."""


def validate_authority(
    payload: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    clean = value.get("clean_implementation")
    bound = value.get("bound_inputs")
    replacement = value.get("replacement_contract")
    budget = value.get("execution_budget")
    output = value.get("output_contract")
    if not (
        value.get("schema_version") == AUTHORITY_SCHEMA_VERSION
        and value.get("status")
        == "fresh_zero_call_current_pack_promotion_authorized"
        and all(
            isinstance(row, Mapping)
            for row in (clean, bound, replacement, budget, output)
        )
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_authority_shape_invalid"
        )
    assert isinstance(clean, Mapping)
    assert isinstance(bound, Mapping)
    assert isinstance(replacement, Mapping)
    assert isinstance(budget, Mapping)
    assert isinstance(output, Mapping)
    if not (
        clean.get("working_tree_required_clean_before_execution") is True
        and clean.get("pushed_head_required") is True
        and str(clean.get("branch") or "")
        and str(clean.get("git_commit") or "")
        and replacement.get("case_key") == "DELL"
        and replacement.get("retained_case_keys") == [
            "MU",
            "NVDA",
            "ORCL",
            "ASML",
            "ANET",
        ]
        and str(replacement.get("private_object_root_relative") or "")
        and budget.get("network_calls") == 0
        and budget.get("model_calls") == 0
        and budget.get("provider_calls") == 0
        and budget.get("retries") == 0
        and budget.get("current_pointer_mutation")
        == "replace_registered_result_and_workspace_once"
        and budget.get("private_object_copy") == "forbidden"
        and budget.get("raw_source_publication") == "forbidden"
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_scope_or_budget_invalid"
        )
    _safe_relative(
        str(replacement["private_object_root_relative"]),
        "current_pack_promotion_private_root_invalid",
    )
    for ref_key, digest_key in (
        ("predecessor_result_ref", "predecessor_result_sha256"),
        ("predecessor_workspace_ref", "predecessor_workspace_sha256"),
        ("successor_result_ref", "successor_result_sha256"),
        ("successor_pack_ref", "successor_pack_sha256"),
        ("zero_call_proof_ref", "zero_call_proof_sha256"),
        ("runner_ref", "runner_sha256"),
        ("runtime_registry_ref", "runtime_registry_sha256"),
    ):
        path = _safe_repository_path(
            repository_root, str(bound.get(ref_key) or "")
        )
        _assert_digest(path, str(bound.get(digest_key) or ""))
    proof = _read_json(
        repository_root / str(bound["zero_call_proof_ref"])
    )
    if not (
        proof.get("schema_version")
        == "fin_ia_current_evidence_pack_promotion_zero_call_proof_v1_0"
        and proof.get("status") == "pass"
        and proof.get("current_pointer_mutated") is False
        and proof.get("private_object_copy_performed") is False
        and proof.get("model_calls") == 0
        and proof.get("network_calls") == 0
        and set(proof.get("mutation_results") or ())
        >= {
            "successor_digest_drift_rejected",
            "budget_expansion_rejected",
            "private_root_escape_rejected",
            "retained_case_partition_drift_rejected",
        }
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_zero_call_proof_invalid"
        )
    for key in (
        "composed_result_ref",
        "composed_workspace_ref",
        "public_execution_result_ref",
    ):
        path = _safe_repository_path(
            repository_root, str(output.get(key) or "")
        )
        if path.exists():
            raise CurrentEvidencePackPromotionError(
                "current_pack_promotion_output_already_exists"
            )
    registry_ref = str(output.get("runtime_registry_ref") or "")
    if not registry_ref or registry_ref != str(
        bound.get("runtime_registry_ref") or ""
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_registry_binding_invalid"
        )
    if str(output.get("runtime_registry_id") or "") != (
        "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R11"
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_registry_id_invalid"
        )
    return value


def assert_repository_state(
    authority: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    clean = authority["clean_implementation"]
    branch = _git(repository_root, "branch", "--show-current")
    if branch != str(clean["branch"]):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_repository_branch_mismatch"
        )
    implementation = str(clean["git_commit"])
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, "HEAD"],
        cwd=repository_root,
        capture_output=True,
        check=False,
        text=True,
    )
    if ancestor.returncode != 0:
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_implementation_not_ancestor"
        )
    if _git(repository_root, "status", "--porcelain"):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_repository_not_clean"
        )
    if _git(repository_root, "rev-parse", "HEAD") != _git(
        repository_root, "rev-parse", "@{upstream}"
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_head_not_pushed"
        )


def compose_current_pack(
    authority: Mapping[str, Any],
    *,
    authority_path: Path,
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    bound = authority["bound_inputs"]
    replacement = authority["replacement_contract"]
    output = authority["output_contract"]
    predecessor = _read_json(
        repository_root / str(bound["predecessor_result_ref"])
    )
    workspace = _read_json(
        repository_root / str(bound["predecessor_workspace_ref"])
    )
    successor_result = _read_json(
        repository_root / str(bound["successor_result_ref"])
    )
    successor_pack_path = (
        repository_root / str(bound["successor_pack_ref"])
    )
    successor_pack = _read_json(successor_pack_path)
    _validate_predecessor(predecessor, workspace)
    validate_reviewed_evidence_pack(successor_pack)

    case_key = str(replacement["case_key"])
    if successor_pack.get("case_key") != case_key:
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_successor_case_mismatch"
        )
    _validate_successor_binding(
        successor_result,
        successor_pack,
        successor_pack_path=successor_pack_path,
        repository_root=repository_root,
        private_object_root_relative=str(
            replacement["private_object_root_relative"]
        ),
    )

    result_body = deepcopy(predecessor)
    predecessor_result_digest = str(result_body.pop("result_digest"))
    result_body.update(
        {
            "schema_version": COMPOSED_RESULT_SCHEMA_VERSION,
            "run_scope": "CURRENT_RESEARCH_EVIDENCE_PACK_COMPOSITION_ZERO_CALL",
            "recorded_at": str(authority["recorded_at"]),
            "attempt_id": str(authority["authority_id"]),
            "status": COMPOSED_RESULT_STATUS,
        }
    )
    summaries = [dict(row) for row in result_body["case_summaries"]]
    replacement_summary = _case_summary(successor_pack)
    result_body["case_summaries"] = [
        replacement_summary if row.get("case_key") == case_key else row
        for row in summaries
    ]
    result_body["pack_payload_digests"][case_key] = str(
        successor_pack["pack_payload_digest"]
    )
    relative_pack_key = _relative_pack_key(
        successor_pack_path,
        repository_root=repository_root,
        private_object_root_relative=str(
            replacement["private_object_root_relative"]
        ),
    )
    result_body["pack_artifacts"][case_key] = {
        "private_object_root_relative": str(
            replacement["private_object_root_relative"]
        ),
        "object_key": relative_pack_key,
        "digest": file_sha256(successor_pack_path),
        "byte_size": successor_pack_path.stat().st_size,
        "media_type": "application/json",
        "artifact_type": "reviewed_local_evidence_pack_with_declared_gaps",
    }
    result_body["observed_counts"] = _recompute_observed_counts(
        dict(result_body["observed_counts"]),
        list(result_body["case_summaries"]),
    )
    result_body["stage_acceptance"].update(
        {
            "current_pack_composition_digest_bound": True,
            "dell_official_transcript_evidence_promoted": True,
            "core_research_ready": True,
            "s1_product_acceptance": False,
            "complete_investment_report_claimed": False,
        }
    )
    result_body["current_composition_lineage"] = {
        "schema_version": "fin_ia_current_pack_composition_lineage_v1_0",
        "predecessor_result_digest": predecessor_result_digest,
        "replacement_case_key": case_key,
        "successor_result_digest": str(successor_result["result_digest"]),
        "successor_pack_payload_digest": str(
            successor_pack["pack_payload_digest"]
        ),
        "successor_pack_artifact_sha256": file_sha256(successor_pack_path),
        "retained_case_keys": list(replacement["retained_case_keys"]),
        "private_object_copy_performed": False,
    }
    result_body["known_boundary"] = (
        "Current composition promotes the reviewed DELL official-transcript "
        "successor while retaining the prior MU, NVDA and holdout packs by "
        "digest. It establishes a current, S3-consumable Evidence Pack input, "
        "not S1 product acceptance, complete external-source coverage, model "
        "research quality, a complete report or release."
    )
    composed_result = {
        **result_body,
        "result_digest": canonical_digest(result_body),
    }

    composed_workspace = deepcopy(workspace)
    composed_workspace["evidence_pack_result_digest"] = composed_result[
        "result_digest"
    ]
    for row in composed_workspace["cases"]:
        if row.get("case_key") != case_key:
            continue
        row["evidence_pack_binding"] = {
            "pack_case_key": case_key,
            "pack_artifact_digest": file_sha256(successor_pack_path),
            "pack_payload_digest": successor_pack["pack_payload_digest"],
        }
    composed_workspace["known_boundary"] = (
        "FIN 0.1.3 exposes three identity-bound reviewed Evidence Packs; the "
        "DELL binding includes the approved official transcript successor. "
        "Dynamic case creation, model research, complete-report claims and "
        "release remain unavailable until their own gates pass."
    )

    execution_body = {
        "schema_version": EXECUTION_RESULT_SCHEMA_VERSION,
        "result_id": str(output["result_id"]),
        "authority_ref": authority_path.resolve().relative_to(
            repository_root.resolve()
        ).as_posix(),
        "recorded_at": str(authority["recorded_at"]),
        "status": "current_dell_pack_promoted_mu_nvda_retained",
        "replacement_case_key": case_key,
        "before_after": {
            "evidence_items": [
                _summary_by_case(summaries, case_key)[
                    "accepted_evidence_items"
                ],
                replacement_summary["accepted_evidence_items"],
            ],
            "residual_gaps": [
                _summary_by_case(summaries, case_key)["residual_gaps"],
                replacement_summary["residual_gaps"],
            ],
        },
        "retained_case_keys": list(replacement["retained_case_keys"]),
        "composed_result_digest": composed_result["result_digest"],
        "composed_workspace_payload_digest": canonical_digest(
            composed_workspace
        ),
        "successor_pack_artifact_sha256": file_sha256(successor_pack_path),
        "successor_pack_payload_digest": successor_pack[
            "pack_payload_digest"
        ],
        "execution": {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "retries": 0,
            "private_object_copy_performed": False,
            "raw_source_published": False,
        },
        "remaining_boundaries": {
            "core_research_ready": True,
            "S1_product_acceptance": False,
            "S3_execution_authorized": False,
            "complete_research_or_release_claimed": False,
        },
    }
    execution_result = {
        **execution_body,
        "result_digest": canonical_digest(execution_body),
    }
    return composed_result, composed_workspace, execution_result


def execute(
    authority: Mapping[str, Any],
    *,
    authority_path: Path,
    repository_root: Path,
) -> dict[str, Any]:
    composed_result, composed_workspace, execution_result = (
        compose_current_pack(
            authority,
            authority_path=authority_path,
            repository_root=repository_root,
        )
    )
    output = authority["output_contract"]
    _write_exclusive(
        _safe_repository_path(
            repository_root, str(output["composed_result_ref"])
        ),
        composed_result,
    )
    _write_exclusive(
        _safe_repository_path(
            repository_root, str(output["composed_workspace_ref"])
        ),
        composed_workspace,
    )
    _write_exclusive(
        _safe_repository_path(
            repository_root, str(output["public_execution_result_ref"])
        ),
        execution_result,
    )
    registry_path = _safe_repository_path(
        repository_root, str(output["runtime_registry_ref"])
    )
    registry = _compose_runtime_registry(
        _read_json(registry_path),
        repository_root=repository_root,
        result_ref=str(output["composed_result_ref"]),
        result_payload=composed_result,
        workspace_ref=str(output["composed_workspace_ref"]),
        workspace_payload=composed_workspace,
        registry_id=str(output["runtime_registry_id"]),
    )
    _write_atomic_replace(registry_path, registry)
    return execution_result


def validate_pack_set_authority(
    payload: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Validate an atomic, multi-case current-product Pack promotion.

    V2 is deliberately a successor to the historical DELL-only authority.  It
    walks every proposition-bound Pack successor from the currently registered
    Pack digest, and binds the matching ProductReadiness result.  This prevents
    a later retry Pack from being promoted without its immutable predecessors.
    """

    value = deepcopy(dict(payload))
    clean = value.get("clean_implementation")
    predecessor = value.get("predecessor_contract")
    replacements = value.get("replacement_chains")
    budget = value.get("execution_budget")
    output = value.get("output_contract")
    if not (
        value.get("schema_version") == PACK_SET_AUTHORITY_SCHEMA_VERSION
        and value.get("status")
        == "fresh_zero_call_current_pack_set_promotion_authorized"
        and isinstance(clean, Mapping)
        and isinstance(predecessor, Mapping)
        and isinstance(replacements, list)
        and bool(replacements)
        and isinstance(budget, Mapping)
        and isinstance(output, Mapping)
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_set_promotion_authority_shape_invalid"
        )
    assert isinstance(clean, Mapping)
    assert isinstance(predecessor, Mapping)
    assert isinstance(budget, Mapping)
    assert isinstance(output, Mapping)
    if not (
        clean.get("working_tree_required_clean_before_execution") is True
        and clean.get("pushed_head_required") is True
        and str(clean.get("branch") or "")
        and str(clean.get("git_commit") or "")
        and budget.get("network_calls") == 0
        and budget.get("model_calls") == 0
        and budget.get("provider_calls") == 0
        and budget.get("retries") == 0
        and budget.get("current_pointer_mutation")
        == "replace_registered_pack_anchor_workspace_readiness_and_binding_once"
        and budget.get("private_object_copy") == "forbidden"
        and budget.get("raw_source_publication") == "forbidden"
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_set_promotion_scope_or_budget_invalid"
        )

    predecessor_refs = (
        "current_result",
        "current_workspace",
        "current_anchor_catalog",
        "current_binding_policy",
        "runtime_registry",
        "zero_call_proof",
        "runner",
    )
    for key in predecessor_refs:
        _bound_file(
            repository_root,
            predecessor,
            ref_key=f"{key}_ref",
            digest_key=f"{key}_sha256",
        )

    current_result = _read_json(
        repository_root / str(predecessor["current_result_ref"])
    )
    workspace = _read_json(
        repository_root / str(predecessor["current_workspace_ref"])
    )
    _validate_predecessor(current_result, workspace)
    load_reviewed_evidence_anchor_catalog(
        _read_json(
            repository_root / str(predecessor["current_anchor_catalog_ref"])
        )
    )

    replacement_keys: list[str] = []
    for raw in replacements:
        if not isinstance(raw, Mapping):
            raise CurrentEvidencePackPromotionError(
                "current_pack_set_replacement_invalid"
            )
        case_key = str(raw.get("case_key") or "").strip().upper()
        chain = raw.get("successor_result_chain")
        if not (
            case_key in {"DELL", "MU", "NVDA"}
            and case_key not in replacement_keys
            and isinstance(chain, list)
            and bool(chain)
        ):
            raise CurrentEvidencePackPromotionError(
                "current_pack_set_replacement_invalid"
            )
        replacement_keys.append(case_key)
        current_payload_digest = str(
            current_result["pack_payload_digests"][case_key]
        )
        for chain_row in chain:
            if not isinstance(chain_row, Mapping):
                raise CurrentEvidencePackPromotionError(
                    "current_pack_set_successor_chain_invalid"
                )
            result_path = _bound_file(
                repository_root,
                chain_row,
                ref_key="result_ref",
                digest_key="result_sha256",
            )
            successor = _read_json(result_path)
            current_payload_digest = _validate_product_successor_link(
                successor,
                case_key=case_key,
                predecessor_payload_digest=current_payload_digest,
                repository_root=repository_root,
            )
        readiness_path = _bound_file(
            repository_root,
            raw,
            ref_key="readiness_result_ref",
            digest_key="readiness_result_sha256",
        )
        _validate_readiness_result(
            _read_json(readiness_path),
            case_key=case_key,
            repository_root=repository_root,
        )

    all_case_keys = [
        str(row.get("case_key") or "")
        for row in current_result.get("case_summaries") or ()
    ]
    retained = [str(value) for value in value.get("retained_case_keys") or ()]
    if (
        replacement_keys != ["DELL", "MU", "NVDA"]
        or retained != [key for key in all_case_keys if key not in replacement_keys]
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_set_retained_partition_invalid"
        )

    proof = _read_json(
        repository_root / str(predecessor["zero_call_proof_ref"])
    )
    if not (
        proof.get("schema_version")
        == "fin_ia_current_evidence_pack_set_promotion_zero_call_proof_v2_0"
        and proof.get("status") == "pass"
        and proof.get("current_pointer_mutated") is False
        and proof.get("private_object_copy_performed") is False
        and proof.get("model_calls") == 0
        and proof.get("network_calls") == 0
        and set(proof.get("mutation_results") or ())
        >= {
            "successor_chain_drift_rejected",
            "readiness_digest_drift_rejected",
            "retained_case_partition_drift_rejected",
            "long_claim_without_reviewed_anchor_rejected",
            "budget_expansion_rejected",
        }
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_set_zero_call_proof_invalid"
        )

    for key in (
        "composed_result_ref",
        "composed_workspace_ref",
        "composed_anchor_catalog_ref",
        "binding_policy_ref",
        "binding_receipt_ref",
        "public_execution_result_ref",
    ):
        path = _safe_repository_path_or_future(
            repository_root, str(output.get(key) or "")
        )
        if path.exists():
            raise CurrentEvidencePackPromotionError(
                "current_pack_set_output_already_exists"
            )
    predecessor_registry = _read_json(
        repository_root / str(predecessor["runtime_registry_ref"])
    )
    if (
        str(output.get("runtime_registry_ref") or "")
        != str(predecessor.get("runtime_registry_ref") or "")
        or _registry_revision(str(output.get("runtime_registry_id") or ""))
        != _registry_revision(str(predecessor_registry.get("registry_id") or ""))
        + 1
        or not str(output.get("binding_policy_id") or "")
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_set_output_contract_invalid"
        )
    return value


def compose_current_pack_set(
    authority: Mapping[str, Any],
    *,
    authority_path: Path,
    repository_root: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    predecessor = authority["predecessor_contract"]
    output = authority["output_contract"]
    current_result = _read_json(
        repository_root / str(predecessor["current_result_ref"])
    )
    workspace = _read_json(
        repository_root / str(predecessor["current_workspace_ref"])
    )
    anchor_payload = _read_json(
        repository_root / str(predecessor["current_anchor_catalog_ref"])
    )
    binding_policy = _read_json(
        repository_root / str(predecessor["current_binding_policy_ref"])
    )
    _validate_predecessor(current_result, workspace)
    predecessor_anchor = load_reviewed_evidence_anchor_catalog(anchor_payload)

    replacements: dict[
        str, tuple[dict[str, Any], Path, dict[str, Any], dict[str, Any]]
    ] = {}
    for raw in authority["replacement_chains"]:
        case_key = str(raw["case_key"])
        final_chain_row = raw["successor_result_chain"][-1]
        final_result_path = _bound_file(
            repository_root,
            final_chain_row,
            ref_key="result_ref",
            digest_key="result_sha256",
        )
        final_result = _read_json(final_result_path)
        _validate_product_successor_link(
            final_result,
            case_key=case_key,
            predecessor_payload_digest=str(
                final_result["predecessor_pack_payload_digest"]
            ),
            repository_root=repository_root,
        )
        pack_path = _safe_repository_path(
            repository_root, str(final_result["private_pack_ref"])
        )
        pack = _read_json(pack_path)
        readiness_path = _bound_file(
            repository_root,
            raw,
            ref_key="readiness_result_ref",
            digest_key="readiness_result_sha256",
        )
        readiness = _read_json(readiness_path)
        _validate_readiness_result(
            readiness,
            case_key=case_key,
            repository_root=repository_root,
        )
        replacements[case_key] = (pack, pack_path, final_result, readiness)

    body = deepcopy(dict(current_result))
    predecessor_result_digest = str(body.pop("result_digest", ""))
    body["attempt_id"] = str(authority["authority_id"])
    body["recorded_at"] = str(authority["recorded_at"])
    summaries = [dict(row) for row in body["case_summaries"]]
    body["case_summaries"] = [
        _case_summary(replacements[str(row["case_key"])][0])
        if str(row.get("case_key") or "") in replacements
        else row
        for row in summaries
    ]
    body["pack_artifacts"] = deepcopy(dict(body["pack_artifacts"]))
    body["pack_payload_digests"] = deepcopy(
        dict(body["pack_payload_digests"])
    )
    for case_key, (pack, pack_path, _result, _readiness) in replacements.items():
        private_root, object_key = _private_pack_location(
            pack_path, repository_root=repository_root
        )
        body["pack_artifacts"][case_key] = {
            "artifact_type": "reviewed_local_evidence_pack_with_declared_gaps",
            "byte_size": pack_path.stat().st_size,
            "digest": file_sha256(pack_path),
            "media_type": "application/json",
            "object_key": object_key,
            "private_object_root_relative": private_root,
        }
        body["pack_payload_digests"][case_key] = str(
            pack["pack_payload_digest"]
        )
    body["observed_counts"] = _recompute_observed_counts(
        dict(body["observed_counts"]), list(body["case_summaries"])
    )
    body["current_composition_lineage"] = {
        "schema_version": "fin_ia_current_pack_composition_lineage_v1_3",
        "predecessor_result_digest": predecessor_result_digest,
        "replacement_case_keys": list(replacements),
        "replacement_result_digests": {
            key: str(value[2]["result_digest"])
            for key, value in replacements.items()
        },
        "retained_case_keys": list(authority["retained_case_keys"]),
        "private_object_copy_performed": False,
        "promotion_kind": "three_case_proposition_bound_evidence_successor",
    }
    stage = deepcopy(dict(body.get("stage_acceptance") or {}))
    stage.update(
        {
            "three_case_proposition_bound_evidence_successors_promoted": True,
            "s1_product_acceptance": False,
            "complete_investment_report_claimed": False,
        }
    )
    body["stage_acceptance"] = stage
    body["known_boundary"] = (
        "Current composition exposes the latest internally adjudicated, "
        "capture-bound DELL, MU and NVDA Evidence successors while retaining "
        "development holdout packs by digest. It does not make internal "
        "adjudication qualified-human review, prove external-source completeness, "
        "grant NumericFact authority, qualify S1 or authorize research publication."
    )
    composed_result = {**body, "result_digest": canonical_digest(body)}

    composed_workspace = deepcopy(dict(workspace))
    composed_workspace["evidence_pack_result_digest"] = composed_result[
        "result_digest"
    ]
    for row in composed_workspace["cases"]:
        case_key = str(row.get("case_key") or "")
        if case_key not in replacements:
            continue
        pack, pack_path, _result, _readiness = replacements[case_key]
        row["evidence_pack_binding"] = {
            "pack_artifact_digest": file_sha256(pack_path),
            "pack_case_key": case_key,
            "pack_payload_digest": str(pack["pack_payload_digest"]),
        }
    composed_workspace["known_boundary"] = (
        "FIN 0.1.3 exposes three identity-bound, capture-verified current "
        "Evidence Pack successors. Dynamic case creation, S1 qualification, "
        "S2 NumericFact completion, model research and release remain separately gated."
    )

    composed_anchor = _compose_anchor_catalog(
        predecessor_anchor=predecessor_anchor,
        replacements=replacements,
    )

    composed_policy = deepcopy(dict(binding_policy))
    composed_policy["policy_id"] = str(output["binding_policy_id"])
    composed_policy["binding_receipt_projection"] = {
        "workbench_per_object_lineage_drilldown_complete": True,
    }
    composed_policy["assets"]["current_evidence_pack_result"]["ref"] = str(
        output["composed_result_ref"]
    )
    composed_policy["assets"]["current_reviewed_anchor_catalog"]["ref"] = str(
        output["composed_anchor_catalog_ref"]
    )
    for case_key, raw in zip(
        replacements, authority["replacement_chains"], strict=True
    ):
        composed_policy["assets"][
            f"{case_key.lower()}_product_readiness"
        ]["ref"] = str(raw["readiness_result_ref"])

    execution_body = {
        "schema_version": PACK_SET_EXECUTION_RESULT_SCHEMA_VERSION,
        "result_id": str(output["result_id"]),
        "authority_ref": authority_path.resolve().relative_to(
            repository_root.resolve()
        ).as_posix(),
        "recorded_at": str(authority["recorded_at"]),
        "status": "three_case_current_pack_set_promoted",
        "replacement_case_keys": list(replacements),
        "before_after": {
            case_key: {
                "evidence_items": [
                    _summary_by_case(summaries, case_key)[
                        "accepted_evidence_items"
                    ],
                    _case_summary(value[0])["accepted_evidence_items"],
                ],
                "residual_gaps": [
                    _summary_by_case(summaries, case_key)["residual_gaps"],
                    _case_summary(value[0])["residual_gaps"],
                ],
                "readiness_state": str(value[3]["readiness_state"]),
            }
            for case_key, value in replacements.items()
        },
        "retained_case_keys": list(authority["retained_case_keys"]),
        "composed_result_digest": str(composed_result["result_digest"]),
        "composed_workspace_payload_digest": canonical_digest(
            composed_workspace
        ),
        "composed_anchor_catalog_digest": str(
            composed_anchor["catalog_digest"]
        ),
        "execution": {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "retries": 0,
            "private_object_copy_performed": False,
            "raw_source_published": False,
        },
        "remaining_boundaries": {
            "S1_product_acceptance": False,
            "external_blind_qualification_complete": False,
            "qualified_human_review_complete": False,
            "S3_execution_authorized": False,
            "complete_research_or_release_claimed": False,
        },
    }
    execution_result = {
        **execution_body,
        "result_digest": canonical_digest(execution_body),
    }
    return (
        composed_result,
        composed_workspace,
        composed_anchor,
        composed_policy,
        execution_result,
    )


def execute_pack_set(
    authority: Mapping[str, Any],
    *,
    authority_path: Path,
    repository_root: Path,
) -> dict[str, Any]:
    (
        composed_result,
        composed_workspace,
        composed_anchor,
        composed_policy,
        execution_result,
    ) = compose_current_pack_set(
        authority,
        authority_path=authority_path,
        repository_root=repository_root,
    )
    output = authority["output_contract"]
    new_payloads = {
        str(output["composed_result_ref"]): composed_result,
        str(output["composed_workspace_ref"]): composed_workspace,
        str(output["composed_anchor_catalog_ref"]): composed_anchor,
        str(output["binding_policy_ref"]): composed_policy,
        str(output["public_execution_result_ref"]): execution_result,
    }
    for ref, payload in new_payloads.items():
        _write_exclusive(
            _safe_repository_path_or_future(repository_root, ref), payload
        )

    registry_path = _safe_repository_path(
        repository_root, str(output["runtime_registry_ref"])
    )
    registry = _compose_pack_set_registry(
        _read_json(registry_path),
        repository_root=repository_root,
        output=output,
        authority=authority,
        payloads=new_payloads,
        receipt_payload=None,
    )
    receipt = build_current_s1_runtime_binding_receipt(
        repository_root,
        composed_policy,
        payload_overrides={"runtime_registry": registry},
    )
    receipt_ref = str(output["binding_receipt_ref"])
    _write_exclusive(
        _safe_repository_path_or_future(repository_root, receipt_ref), receipt
    )
    registry = _compose_pack_set_registry(
        _read_json(registry_path),
        repository_root=repository_root,
        output=output,
        authority=authority,
        payloads=new_payloads,
        receipt_payload=receipt,
    )
    _write_atomic_replace(registry_path, registry)
    return execution_result


def _bound_file(
    repository_root: Path,
    payload: Mapping[str, Any],
    *,
    ref_key: str,
    digest_key: str,
) -> Path:
    path = _safe_repository_path(
        repository_root, str(payload.get(ref_key) or "")
    )
    _assert_digest(path, str(payload.get(digest_key) or ""))
    return path


def _validate_product_successor_link(
    successor: Mapping[str, Any],
    *,
    case_key: str,
    predecessor_payload_digest: str,
    repository_root: Path,
) -> str:
    body = deepcopy(dict(successor))
    result_digest = str(body.pop("result_digest", ""))
    authority = successor.get("authority") or {}
    if not (
        successor.get("schema_version")
        == "fin_ia_s1_product_evidence_successor_public_result_v1_2"
        and successor.get("status")
        == "proposition_bound_evidence_successor_materialized"
        and successor.get("case_key") == case_key
        and successor.get("predecessor_pack_payload_digest")
        == predecessor_payload_digest
        and result_digest == canonical_digest(body)
        and authority.get("accepted_claims_capture_bound") is True
        and authority.get("accepted_evidence_proposition_bound") is True
        and authority.get("candidate_is_not_evidence") is True
        and authority.get("generation_model_calls") == 0
        and authority.get("network_calls") == 0
        and authority.get("metric_row_promoted_as_narrative_evidence") is False
        and authority.get("numeric_fact_authority") is False
        and authority.get("qualified_human_review") is False
        and authority.get("S1_qualification_claimed") is False
        and authority.get("product_publication") is False
    ):
        raise CurrentEvidencePackPromotionError(
            f"current_pack_set_successor_link_invalid:{case_key}"
        )
    pack_ref = str(successor.get("private_pack_ref") or "")
    if not pack_ref.startswith("data/workbench_private/"):
        raise CurrentEvidencePackPromotionError(
            f"current_pack_set_private_pack_ref_invalid:{case_key}"
        )
    pack_path = _safe_repository_path(repository_root, pack_ref)
    _assert_digest(pack_path, str(successor.get("private_pack_sha256") or ""))
    pack = _read_json(pack_path)
    validate_reviewed_evidence_pack(pack)
    if not (
        pack.get("case_key") == case_key
        and pack.get("pack_payload_digest")
        == successor.get("successor_pack_payload_digest")
    ):
        raise CurrentEvidencePackPromotionError(
            f"current_pack_set_successor_pack_binding_invalid:{case_key}"
        )
    return str(successor["successor_pack_payload_digest"])


def _validate_readiness_result(
    payload: Mapping[str, Any],
    *,
    case_key: str,
    repository_root: Path | None = None,
) -> None:
    body = deepcopy(dict(payload))
    result_digest = str(body.pop("result_digest", ""))
    authority = payload.get("authority") or {}
    if not (
        payload.get("schema_version")
        == "fin_ia_s1_current_product_readiness_result_v1_1"
        and payload.get("status")
        == "current_product_pack_readiness_materialized"
        and payload.get("case_key") == case_key
        and result_digest == canonical_digest(body)
        and authority.get("candidate_is_not_evidence") is True
        and authority.get("public_information_gap_authority") is False
        and authority.get("S1_qualification_claimed") is False
        and str(payload.get("full_result_ref") or "").startswith(
            "data/workbench_private/"
        )
        and len(str(payload.get("full_result_sha256") or "")) == 64
    ):
        raise CurrentEvidencePackPromotionError(
            f"current_pack_set_readiness_invalid:{case_key}"
        )
    if repository_root is not None:
        full_result = _safe_repository_path(
            repository_root, str(payload["full_result_ref"])
        )
        _assert_digest(full_result, str(payload["full_result_sha256"]))


def _registry_revision(value: str) -> int:
    matched = re.fullmatch(r".+-R([0-9]+)", str(value))
    if matched is None:
        raise CurrentEvidencePackPromotionError(
            "current_pack_set_registry_revision_invalid"
        )
    return int(matched.group(1))


def _private_pack_location(
    pack_path: Path, *, repository_root: Path
) -> tuple[str, str]:
    private_base = (repository_root / "data" / "workbench_private").resolve()
    resolved = pack_path.resolve()
    try:
        relative = resolved.relative_to(private_base)
    except ValueError as exc:
        raise CurrentEvidencePackPromotionError(
            "current_pack_set_private_pack_outside_root"
        ) from exc
    if len(relative.parts) < 2:
        raise CurrentEvidencePackPromotionError(
            "current_pack_set_private_pack_location_invalid"
        )
    return PurePosixPath(*relative.parts[:-1]).as_posix(), relative.name


def _compose_anchor_catalog(
    *,
    predecessor_anchor: Any,
    replacements: Mapping[
        str,
        tuple[dict[str, Any], Path, dict[str, Any], dict[str, Any]],
    ],
) -> dict[str, Any]:
    old_entries = {
        (str(row["case_key"]), str(row["target_id"])): dict(row)
        for row in predecessor_anchor.entries
    }
    entries: list[dict[str, Any]] = [
        dict(row)
        for row in predecessor_anchor.entries
        if str(row["case_key"]) not in replacements
    ]
    bindings = {
        key: dict(value)
        for key, value in predecessor_anchor.case_pack_bindings.items()
    }
    for case_key, (pack, pack_path, _result, _readiness) in replacements.items():
        sources = {
            str(row["material_ref"]): dict(row)
            for row in pack.get("source_materials") or ()
        }
        for item in pack.get("evidence_items") or ():
            if str(item.get("object_type") or "") != "claim":
                continue
            material = sources.get(str(item.get("source_material_ref") or ""))
            if material is None:
                raise CurrentEvidencePackPromotionError(
                    f"current_pack_set_anchor_source_missing:{case_key}"
                )
            source_text = str(material.get("source_text") or "")
            old = old_entries.get((case_key, str(item["target_id"])))
            if old is not None and _old_anchor_still_binds(
                old, item=item, material=material
            ):
                entries.append(old)
                continue
            if not 24 <= len(source_text) <= 1600:
                raise CurrentEvidencePackPromotionError(
                    f"current_pack_set_explicit_anchor_required:{case_key}:"
                    f"{item.get('target_id')}"
                )
            entries.append(
                {
                    "case_key": case_key,
                    "target_id": str(item["target_id"]),
                    "source_record_id": str(item["source_record_id"]),
                    "evidence_item_digest": str(item["evidence_item_digest"]),
                    "source_text_digest": str(material["source_text_digest"]),
                    "anchor_kind": "structured_claim_text",
                    "anchor_text": source_text,
                    "anchor_start": 0,
                    "anchor_end": len(source_text),
                    "anchor_digest": hashlib.sha256(
                        source_text.encode("utf-8")
                    ).hexdigest(),
                    "review_status": "reviewed_exact_source_surface",
                }
            )
        bindings[case_key] = {
            "artifact_digest": file_sha256(pack_path),
            "pack_payload_digest": str(pack["pack_payload_digest"]),
        }
    entries.sort(key=lambda row: (str(row["case_key"]), str(row["target_id"])))
    return compile_reviewed_evidence_anchor_catalog(
        case_pack_bindings=bindings,
        entries=entries,
        known_boundary=(
            "Anchors are exact reviewed source surfaces for the current DELL, "
            "MU and NVDA claim Evidence. They grant no new Evidence, numeric, "
            "causal, qualified-human, S1 or publication authority."
        ),
    )


def _old_anchor_still_binds(
    row: Mapping[str, Any],
    *,
    item: Mapping[str, Any],
    material: Mapping[str, Any],
) -> bool:
    source_text = str(material.get("source_text") or "")
    start = int(row.get("anchor_start") or 0)
    end = int(row.get("anchor_end") or 0)
    return (
        row.get("source_record_id") == item.get("source_record_id")
        and row.get("evidence_item_digest") == item.get("evidence_item_digest")
        and row.get("source_text_digest") == material.get("source_text_digest")
        and 0 <= start < end <= len(source_text)
        and source_text[start:end] == row.get("anchor_text")
    )


def _compose_pack_set_registry(
    predecessor: Mapping[str, Any],
    *,
    repository_root: Path,
    output: Mapping[str, Any],
    authority: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    receipt_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    rows = value.get("resources")
    if not (
        value.get("schema_version")
        == "fin_ia_0_1_3_runtime_resource_registry_v1_0"
        and value.get("status") == "tracked_typed_runtime_resource_authority"
        and isinstance(rows, list)
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_set_runtime_registry_invalid"
        )
    replacements: dict[str, tuple[str, Mapping[str, Any]]] = {
        "application.result.current_research_local_evidence_packs": (
            str(output["composed_result_ref"]),
            payloads[str(output["composed_result_ref"])],
        ),
        "application.config.current_research_workspace_catalog": (
            str(output["composed_workspace_ref"]),
            payloads[str(output["composed_workspace_ref"])],
        ),
        "application.result.current_reviewed_claim_anchors": (
            str(output["composed_anchor_catalog_ref"]),
            payloads[str(output["composed_anchor_catalog_ref"])],
        ),
        "application.config.current_s1_runtime_binding_policy": (
            str(output["binding_policy_ref"]),
            payloads[str(output["binding_policy_ref"])],
        ),
    }
    for raw in authority["replacement_chains"]:
        case_key = str(raw["case_key"])
        ref = str(raw["readiness_result_ref"])
        replacements[
            f"application.result.current_s1_{case_key.lower()}_product_readiness"
        ] = (ref, _read_json(repository_root / ref))
    if receipt_payload is not None:
        replacements["application.result.current_s1_runtime_binding_receipt"] = (
            str(output["binding_receipt_ref"]),
            receipt_payload,
        )

    observed: set[str] = set()
    for row in rows:
        resource_id = str(row.get("resource_id") or "")
        replacement = replacements.get(resource_id)
        if replacement is None:
            continue
        ref, payload = replacement
        _safe_repository_path_or_future(repository_root, ref)
        rendered = _render_json(payload)
        row["repo_relative_path"] = ref
        row["sha256"] = hashlib.sha256(rendered).hexdigest()
        row["bytes"] = len(rendered)
        observed.add(resource_id)
    if observed != set(replacements):
        raise CurrentEvidencePackPromotionError(
            "current_pack_set_registry_resource_missing"
        )
    if [str(row.get("resource_id") or "") for row in rows] != sorted(
        str(row.get("resource_id") or "") for row in rows
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_set_registry_order_invalid"
        )
    value["registry_id"] = str(output["runtime_registry_id"])
    value["resource_count"] = len(rows)
    value["resource_bytes"] = sum(int(row["bytes"]) for row in rows)
    value["resource_canonical_digest"] = canonical_digest(rows)
    return value


def _compose_runtime_registry(
    predecessor: Mapping[str, Any],
    *,
    repository_root: Path,
    result_ref: str,
    result_payload: Mapping[str, Any],
    workspace_ref: str,
    workspace_payload: Mapping[str, Any],
    registry_id: str,
) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    expected_top_level = {
        "schema_version",
        "registry_id",
        "status",
        "policy",
        "detector_python_refs",
        "resource_count",
        "resource_bytes",
        "resource_canonical_digest",
        "resources",
    }
    rows = value.get("resources")
    if not (
        set(value) == expected_top_level
        and value.get("schema_version")
        == "fin_ia_0_1_3_runtime_resource_registry_v1_0"
        and value.get("status") == "tracked_typed_runtime_resource_authority"
        and isinstance(rows, list)
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_runtime_registry_invalid"
        )
    replacements = {
        "application.result.current_research_local_evidence_packs": (
            result_ref,
            result_payload,
        ),
        "application.config.current_research_workspace_catalog": (
            workspace_ref,
            workspace_payload,
        ),
    }
    observed: set[str] = set()
    for row in rows:
        resource_id = str(row.get("resource_id") or "")
        if resource_id not in replacements:
            continue
        ref, payload = replacements[resource_id]
        _safe_repository_path_or_future(repository_root, ref)
        rendered = _render_json(payload)
        row["repo_relative_path"] = ref
        row["sha256"] = hashlib.sha256(rendered).hexdigest()
        row["bytes"] = len(rendered)
        observed.add(resource_id)
    if observed != set(replacements):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_registry_resource_missing"
        )
    if [str(row.get("resource_id") or "") for row in rows] != sorted(
        str(row.get("resource_id") or "") for row in rows
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_registry_order_invalid"
        )
    value["registry_id"] = registry_id
    value["resource_count"] = len(rows)
    value["resource_bytes"] = sum(int(row["bytes"]) for row in rows)
    value["resource_canonical_digest"] = canonical_digest(rows)
    return value


def _validate_predecessor(
    predecessor: Mapping[str, Any],
    workspace: Mapping[str, Any],
) -> None:
    body = deepcopy(dict(predecessor))
    digest = str(body.pop("result_digest", ""))
    case_keys = [
        str(row.get("case_key") or "")
        for row in predecessor.get("case_summaries") or ()
    ]
    workspace_keys = [
        str(row.get("case_key") or "")
        for row in workspace.get("cases") or ()
    ]
    if not (
        digest == canonical_digest(body)
        and case_keys == ["DELL", "MU", "NVDA", "ORCL", "ASML", "ANET"]
        and workspace.get("schema_version")
        == "fin_ia_research_workspace_catalog_v1_0"
        and workspace.get("evidence_pack_result_digest") == digest
        and workspace_keys == ["DELL", "MU", "NVDA"]
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_predecessor_invalid"
        )


def _validate_successor_binding(
    successor_result: Mapping[str, Any],
    successor_pack: Mapping[str, Any],
    *,
    successor_pack_path: Path,
    repository_root: Path,
    private_object_root_relative: str,
) -> None:
    body = deepcopy(dict(successor_result))
    digest = str(body.pop("result_digest", ""))
    declared = dict(successor_result.get("successor_pack") or {})
    expected_key = _relative_pack_key(
        successor_pack_path,
        repository_root=repository_root,
        private_object_root_relative=private_object_root_relative,
    )
    if not (
        successor_result.get("schema_version")
        == "fin_ia_s1d_official_pdf_successor_result_v1_0"
        and successor_result.get("status")
        == "dell_official_pdf_successor_candidate_ready_current_pointer_unchanged"
        and digest == canonical_digest(body)
        and declared.get("artifact_sha256") == file_sha256(successor_pack_path)
        and declared.get("pack_payload_digest")
        == successor_pack.get("pack_payload_digest")
        and str(declared.get("private_object_key") or "")
        == expected_key
        and successor_result.get("remaining_boundaries", {}).get(
            "core_research_ready"
        )
        is True
        and successor_result.get("remaining_boundaries", {}).get(
            "S1_product_acceptance"
        )
        is False
    ):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_successor_binding_invalid"
        )


def _relative_pack_key(
    pack_path: Path,
    *,
    repository_root: Path,
    private_object_root_relative: str,
) -> str:
    root = (
        repository_root
        / "data"
        / "workbench_private"
        / private_object_root_relative
    ).resolve()
    try:
        return pack_path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_successor_pack_root_mismatch"
        ) from exc


def _case_summary(pack: Mapping[str, Any]) -> dict[str, Any]:
    counts = dict(pack.get("observed_counts") or {})
    summary = {
        "case_key": str(pack["case_key"]),
        "status": "local_evidence_pack_ready_with_declared_residual_gaps",
        "accepted_evidence_items": len(pack.get("evidence_items") or ()),
        "direct_evidence_items": sum(
            row.get("disposition") == "accepted_direct_source_evidence"
            for row in pack.get("evidence_items") or ()
        ),
        "bounded_context_items": sum(
            row.get("disposition") == "accepted_bounded_context_evidence"
            for row in pack.get("evidence_items") or ()
        ),
        "rejected_items": len(pack.get("rejected_items") or ()),
        "residual_gaps": len(pack.get("residual_gaps") or ()),
        "source_materials": len(pack.get("source_materials") or ()),
    }
    for key in (
        "accepted_evidence_items",
        "direct_evidence_items",
        "bounded_context_items",
        "rejected_items",
        "residual_gaps",
        "source_materials",
    ):
        if counts.get(key) != summary[key]:
            raise CurrentEvidencePackPromotionError(
                "current_pack_promotion_successor_count_drift"
            )
    return summary


def _summary_by_case(
    rows: list[dict[str, Any]], case_key: str
) -> dict[str, Any]:
    return next(row for row in rows if row.get("case_key") == case_key)


def _recompute_observed_counts(
    predecessor: dict[str, Any],
    summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    predecessor.update(
        {
            "evidence_items": sum(
                int(row["accepted_evidence_items"]) for row in summaries
            ),
            "rejected_items": sum(
                int(row["rejected_items"]) for row in summaries
            ),
            "residual_gaps": sum(
                int(row["residual_gaps"]) for row in summaries
            ),
        }
    )
    return predecessor


def _safe_relative(value: str, code: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if (
        not value
        or relative.is_absolute()
        or "\\" in value
        or ".." in relative.parts
    ):
        raise CurrentEvidencePackPromotionError(code)
    return relative


def _safe_repository_path(root: Path, ref: str) -> Path:
    relative = _safe_relative(ref, "current_pack_promotion_path_invalid")
    path = root.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_path_invalid"
        ) from exc
    return path


def _safe_repository_path_or_future(root: Path, ref: str) -> Path:
    relative = _safe_relative(ref, "current_pack_promotion_path_invalid")
    path = root.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_path_invalid"
        ) from exc
    return path


def _assert_digest(path: Path, expected: str) -> None:
    if not path.is_file() or file_sha256(path) != expected:
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_input_digest_mismatch"
        )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_json_invalid"
        ) from exc
    if not isinstance(value, dict):
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_json_mapping_required"
        )
    return value


def _write_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(_render_json(payload))
    except FileExistsError as exc:
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_output_already_exists"
        ) from exc


def _write_atomic_replace(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(path.name + ".promotion-tmp")
    if temporary.exists():
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_temporary_output_exists"
        )
    try:
        with temporary.open("xb") as handle:
            handle.write(_render_json(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _render_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_repository_state_unavailable"
        )
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote one reviewed successor into the current Pack set."
    )
    parser.add_argument("--authority", type=Path, required=True)
    args = parser.parse_args()
    authority_path = args.authority.resolve()
    raw_authority = _read_json(authority_path)
    if raw_authority.get("schema_version") == PACK_SET_AUTHORITY_SCHEMA_VERSION:
        authority = validate_pack_set_authority(
            raw_authority, repository_root=ROOT
        )
        executor = execute_pack_set
    else:
        authority = validate_authority(
            raw_authority, repository_root=ROOT
        )
        executor = execute
    assert_repository_state(authority, repository_root=ROOT)
    result = executor(
        authority,
        authority_path=authority_path,
        repository_root=ROOT,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
