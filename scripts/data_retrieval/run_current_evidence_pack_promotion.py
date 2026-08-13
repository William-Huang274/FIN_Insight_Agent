from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path, PurePosixPath
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


AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_current_evidence_pack_promotion_authority_v1_0"
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
    return execution_result


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
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            handle.write("\n")
    except FileExistsError as exc:
        raise CurrentEvidencePackPromotionError(
            "current_pack_promotion_output_already_exists"
        ) from exc


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
    authority = validate_authority(
        _read_json(authority_path), repository_root=ROOT
    )
    assert_repository_state(authority, repository_root=ROOT)
    result = execute(
        authority,
        authority_path=authority_path,
        repository_root=ROOT,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
