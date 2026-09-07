from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.canonical_runtime import canonical_digest  # noqa: E402
from sec_agent.research.report_gap_crosswalk import (  # noqa: E402
    compile_report_gap_crosswalk,
    validate_program_baseline_manifest,
)


DEFAULT_BASELINE = (
    "configs/research/evals/"
    "fin_ia_0_1_3_dell_source_report_quality_program_baseline_manifest_v1_0.json"
)
DEFAULT_BASELINE_VERIFICATION = (
    "configs/research/evals/"
    "fin_ia_0_1_3_dell_source_report_quality_baseline_verification_v1_1.json"
)
DEFAULT_PROTOCOL = (
    "configs/research/evals/"
    "fin_ia_0_1_3_dell_source_report_quality_evaluation_protocol_v1_0.json"
)
DEFAULT_AUTHORITY_TEMPLATE = (
    "configs/research/evals/"
    "fin_ia_0_1_3_dell_source_report_quality_execution_authority_template_v1_0.json"
)
DEFAULT_PROGRAM = (
    "configs/research/evals/"
    "fin_ia_0_1_3_dell_report_gap_crosswalk_program_v1_0.json"
)
DEFAULT_PRIVATE_OUTPUT = (
    "data/workbench_private/fin_0_1_3_report_gap_crosswalk/dell-r3/full_result.json"
)
DEFAULT_PUBLIC_OUTPUT = (
    "configs/research/evals/"
    "fin_ia_0_1_3_dell_report_gap_crosswalk_result_v1_2.json"
)


class DellReportGapCrosswalkMaterializationError(RuntimeError):
    pass


def _resolve(ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise DellReportGapCrosswalkMaterializationError(
            "report_gap_crosswalk_path_outside_repository"
        ) from exc


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DellReportGapCrosswalkMaterializationError(
            f"report_gap_crosswalk_json_object_required:{path.name}"
        )
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _require_clean_worktree(status_porcelain: str) -> None:
    if status_porcelain.strip():
        raise DellReportGapCrosswalkMaterializationError(
            "report_gap_crosswalk_clean_worktree_required"
        )


def _git_blob_at_commit(commit: str, ref: str) -> str:
    try:
        blob = _git_output("rev-parse", "--verify", f"{commit}:{ref}")
        object_type = _git_output("cat-file", "-t", blob)
    except subprocess.CalledProcessError as exc:
        raise DellReportGapCrosswalkMaterializationError(
            f"report_gap_crosswalk_git_commit_path_invalid:{commit}:{ref}"
        ) from exc
    if object_type != "blob":
        raise DellReportGapCrosswalkMaterializationError(
            f"report_gap_crosswalk_git_object_not_blob:{commit}:{ref}"
        )
    return blob


def _git_blob_for_source_bytes(ref: str, payload: bytes) -> str:
    try:
        completed = subprocess.run(
            ["git", "hash-object", "--stdin", "--path", ref],
            cwd=ROOT,
            check=True,
            input=payload,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise DellReportGapCrosswalkMaterializationError(
            f"report_gap_crosswalk_git_source_blob_invalid:{ref}"
        ) from exc
    return completed.stdout.decode("ascii").strip()


def _render_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def _write_new(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(
            f"report_gap_crosswalk_output_exists:{_relative(path)}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(_render_json(payload))


def _governance_binding(
    path: Path, payload: Mapping[str, Any], digest_field: str
) -> dict[str, str]:
    return {
        "ref": _relative(path),
        "sha256": _sha256_file(path),
        digest_field: str(payload[digest_field]),
    }


def compile_materialization(
    *,
    baseline_path: Path,
    baseline_verification_path: Path,
    protocol_path: Path,
    authority_template_path: Path,
    program_path: Path,
    private_output_path: Path,
    recorded_at: str,
    prepared_from_commit: str,
) -> dict[str, dict[str, Any]]:
    baseline = _read_json(baseline_path)
    baseline_verification = _read_json(baseline_verification_path)
    protocol = _read_json(protocol_path)
    authority_template = _read_json(authority_template_path)
    program = _read_json(program_path)

    source_bytes_by_ref: dict[str, bytes] = {}
    git_blob_by_source_ref: dict[str, str] = {}
    git_blob_by_commit_ref: dict[str, str] = {}
    all_bindings = [
        *dict(baseline.get("input_bindings") or {}).values(),
        *dict(baseline_verification.get("input_bindings") or {}).values(),
    ]
    for raw_binding in all_bindings:
        ref = str(dict(raw_binding).get("ref") or "")
        payload = _resolve(ref).read_bytes()
        source_bytes_by_ref[ref] = payload
        binding = dict(raw_binding)
        if binding.get("git_tracking") == "tracked":
            commit = str(binding.get("git_commit") or "")
            git_blob_by_source_ref[ref] = _git_blob_for_source_bytes(ref, payload)
            git_blob_by_commit_ref[f"{commit}:{ref}"] = _git_blob_at_commit(
                commit, ref
            )
    parsed = validate_program_baseline_manifest(
        baseline,
        verification=baseline_verification,
        source_bytes_by_ref=source_bytes_by_ref,
        git_blob_by_source_ref=git_blob_by_source_ref,
        git_blob_by_commit_ref=git_blob_by_commit_ref,
    )
    compiled = compile_report_gap_crosswalk(
        baseline_manifest=baseline,
        evaluation_protocol=protocol,
        authority_template=authority_template,
        program=program,
        pack=parsed["R4_current_pack"],
        R4_successor_result=parsed["R4_successor_result"],
        R4_evidence_gate_result=parsed["R4_evidence_gate_result"],
        dynamic_full_result=parsed["R38_private_full_result"],
        writer_full_result=parsed["R17_private_full_result"],
        readiness_public_result=parsed["product_readiness_public"],
        readiness_private_result=parsed["product_readiness_private"],
        bridge_public_result=parsed["S2_product_bridge_public"],
        bridge_private_result=parsed["S2_product_bridge_private"],
    )
    governance_bindings = {
        "baseline_manifest": _governance_binding(
            baseline_path, baseline, "manifest_digest"
        ),
        "baseline_verification": _governance_binding(
            baseline_verification_path,
            baseline_verification,
            "verification_digest",
        ),
        "evaluation_protocol": _governance_binding(
            protocol_path, protocol, "protocol_digest"
        ),
        "execution_authority_template": _governance_binding(
            authority_template_path, authority_template, "template_digest"
        ),
        "crosswalk_program": _governance_binding(
            program_path, program, "program_digest"
        ),
    }
    full_body: dict[str, Any] = {
        "schema_version": "fin_ia_dell_report_gap_crosswalk_full_result_v1_2",
        "status": "materialized_zero_call_R2_audit_correction_reaudit_pending",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "governance_bindings": governance_bindings,
        "baseline_input_bindings": baseline["input_bindings"],
        "baseline_verification_input_bindings": baseline_verification[
            "input_bindings"
        ],
        "R1_independent_audit_failure": baseline_verification[
            "R1_independent_audit_failure"
        ],
        "R2_independent_audit_failure": baseline_verification[
            "R2_independent_audit_failure"
        ],
        "crosswalk_content_digest": compiled["crosswalk_content_digest"],
        "audit_projection": compiled["audit_projection"],
        "model_visible_projection": compiled["model_visible_projection"],
        "reader_visible_projection": compiled["reader_visible_projection"],
        "execution": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "embedding_calls": 0,
            "reranker_calls": 0,
            "candidate_promotions": 0,
            "evidence_promotions": 0,
            "gap_closures": 0,
        },
        "acceptance": {
            "R1_independent_audit_failed": True,
            "R2_independent_audit_failed": True,
            "baseline_manifest_valid": True,
            "baseline_actual_counts_recomputed": True,
            "candidate_packet_actual_counts_recomputed": True,
            "tracked_git_commit_path_blobs_verified": True,
            "quality_protocol_valid": True,
            "execution_authority_template_valid": True,
            "crosswalk_deterministic_contract_pass": True,
            "independent_review_pass": False,
            "G1_pass": False,
            "S1_pass": False,
            "S2_pass": False,
            "S3_pass": False,
            "product_acceptance": False,
            "publication": False,
            "release_ready": False,
        },
        "known_boundary": (
            "R1 and R2 failed author-separated review and remain immutable. This R3 zero-call "
            "correction recomputes candidate packet counts from nested request items, verifies "
            "per-request and top-level counts, unique refs and digests, and deterministically "
            "rebuilds the unchanged crosswalk content. It closes no research gap, admits no "
            "candidate, authorizes no source, embedding, reranker, Agent or Writer call, and "
            "does not pass G1 until a new author-separated review passes."
        ),
    }
    full = {
        **full_body,
        "full_result_digest": canonical_digest(full_body),
    }
    private_bytes = _render_json(full)
    public_body: dict[str, Any] = {
        "schema_version": "fin_ia_dell_report_gap_crosswalk_public_result_v1_2",
        "status": "materialized_zero_call_R2_audit_correction_reaudit_pending",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "crosswalk_content_digest": compiled["crosswalk_content_digest"],
        "counts": compiled["audit_projection"]["counts"],
        "model_visible_projection": compiled["model_visible_projection"],
        "reader_visible_projection": compiled["reader_visible_projection"],
        "governance_bindings": governance_bindings,
        "private_full_result_ref": _relative(private_output_path),
        "private_full_result_sha256": _sha256_bytes(private_bytes),
        "private_full_result_digest": full["full_result_digest"],
        "execution": full["execution"],
        "acceptance": full["acceptance"],
        "known_boundary": full["known_boundary"],
    }
    public = {
        **public_body,
        "result_digest": canonical_digest(public_body),
    }
    return {"private": full, "public": public}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    parser.add_argument(
        "--baseline-verification", default=DEFAULT_BASELINE_VERIFICATION
    )
    parser.add_argument("--protocol", default=DEFAULT_PROTOCOL)
    parser.add_argument("--authority-template", default=DEFAULT_AUTHORITY_TEMPLATE)
    parser.add_argument("--program", default=DEFAULT_PROGRAM)
    parser.add_argument("--private-output", default=DEFAULT_PRIVATE_OUTPUT)
    parser.add_argument("--public-output", default=DEFAULT_PUBLIC_OUTPUT)
    args = parser.parse_args()

    _require_clean_worktree(_git_output("status", "--porcelain"))
    private_output = _resolve(args.private_output)
    public_output = _resolve(args.public_output)
    if private_output.exists() or public_output.exists():
        existing = private_output if private_output.exists() else public_output
        raise FileExistsError(
            f"report_gap_crosswalk_output_exists:{_relative(existing)}"
        )
    prepared_from_commit = _git_output("rev-parse", "HEAD")
    recorded_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    compiled = compile_materialization(
        baseline_path=_resolve(args.baseline),
        baseline_verification_path=_resolve(args.baseline_verification),
        protocol_path=_resolve(args.protocol),
        authority_template_path=_resolve(args.authority_template),
        program_path=_resolve(args.program),
        private_output_path=private_output,
        recorded_at=recorded_at,
        prepared_from_commit=prepared_from_commit,
    )
    _write_new(private_output, compiled["private"])
    _write_new(public_output, compiled["public"])
    print(
        json.dumps(
            {
                "status": compiled["public"]["status"],
                "crosswalk_content_digest": compiled["public"][
                    "crosswalk_content_digest"
                ],
                "counts": compiled["public"]["counts"],
                "private_output": _relative(private_output),
                "public_output": _relative(public_output),
                "result_digest": compiled["public"]["result_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
