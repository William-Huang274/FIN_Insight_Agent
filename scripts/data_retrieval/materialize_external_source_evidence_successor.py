from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.external_source_evidence import (  # noqa: E402
    EXTERNAL_SOURCE_EVIDENCE_RESULT_SCHEMA_VERSION,
    adjudicate_external_source_evidence,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    build_reviewed_evidence_pack_correction_successor,
    build_reviewed_evidence_pack_successor,
    validate_reviewed_evidence_pack,
)


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("external_source_evidence_json_not_object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _product_successor_projection(
    *,
    plan: dict,
    evidence: dict,
    successor: dict,
    summary: dict,
    summary_path: Path,
    pack_path: Path,
) -> dict:
    coverage = dict(summary["coverage_delta"])
    accepted_rows = [
        dict(row) for row in evidence.get("accepted_evidence_items") or ()
    ]
    direct_count = sum(
        row.get("disposition") == "accepted_direct_source_evidence"
        for row in accepted_rows
    )
    bounded_count = sum(
        row.get("disposition") == "accepted_bounded_context_evidence"
        for row in accepted_rows
    )
    body = {
        "schema_version": (
            "fin_ia_s1_product_evidence_successor_public_result_v1_2"
        ),
        "status": "proposition_bound_evidence_successor_materialized",
        "recorded_at": plan.get("recorded_at"),
        "prepared_from_commit": _git("rev-parse", "HEAD"),
        "case_key": plan.get("case_key"),
        "plan_id": plan.get("plan_id"),
        "plan_digest": plan.get("plan_digest"),
        "predecessor_pack_payload_digest": plan.get(
            "predecessor_pack_payload_digest"
        ),
        "successor_pack_payload_digest": successor.get("pack_payload_digest"),
        "private_pack_ref": str(pack_path.relative_to(ROOT)).replace("\\", "/"),
        "private_pack_sha256": _sha256(pack_path),
        "full_result_ref": str(summary_path.relative_to(ROOT)).replace("\\", "/"),
        "full_result_sha256": _sha256(summary_path),
        "coverage_delta": {
            "predecessor_evidence_count": coverage[
                "predecessor_evidence_count"
            ],
            "added_or_rebound_evidence_count": (
                coverage["added_direct_evidence_count"]
                + coverage["added_bounded_context_evidence_count"]
            ),
            "retired_evidence_count": coverage["retired_evidence_count"],
            "successor_evidence_count": coverage["successor_evidence_count"],
            "candidate_text_promoted_count": 0,
            "numeric_authority_granted_count": 0,
            "numeric_rows_delegated_to_S2": 0,
        },
        "decision_counts": {
            "accept_for_requirements": direct_count,
            "accept_for_request_context": bounded_count,
            "reject_for_current_scope": len(evidence.get("rejected_items") or ()),
            "delegate_to_s2_numeric_authority": 0,
        },
        "review_scope_counts": {
            "review_items": len(evidence.get("decision_receipts") or ()),
            "actionable_review_items": len(evidence.get("decision_receipts") or ()),
            "informational_review_items_preserved": 0,
        },
        "capture_receipt_count": len(evidence.get("source_materials") or ()),
        "external_ladder_binding": {
            "compiled_result_digest": summary.get("compiled_result_digest"),
            "evidence_result_digest": evidence.get("result_digest"),
            "gap_ids_narrowed": evidence.get("gap_ids_narrowed") or [],
            "gap_ids_satisfied": evidence.get("gap_ids_satisfied") or [],
        },
        "authority": {
            "accepted_claims_capture_bound": True,
            "accepted_evidence_proposition_bound": True,
            "candidate_is_not_evidence": True,
            "generation_model_calls": 0,
            "network_calls": 0,
            "metric_row_promoted_as_narrative_evidence": False,
            "numeric_fact_authority": False,
            "qualified_human_review": False,
            "S1_qualification_claimed": False,
            "product_publication": False,
        },
        "known_boundary": (
            "This tracked projection promotes only capture-bound, source-use-gated "
            "external claims into the DELL internal Evidence successor. Industry, "
            "channel and media material remains bounded context; no candidate or "
            "secondary-source number becomes NumericFact, no residual gap is closed "
            "without a separate receipt, and this result does not qualify S1, grant "
            "qualified-human review or authorize publication."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def materialize(plan: dict) -> tuple[dict, dict, dict]:
    compiled_path = _resolve(str(plan.get("compiled_result_ref") or ""))
    predecessor_path = _resolve(str(plan.get("predecessor_pack_ref") or ""))
    if (
        _sha256(compiled_path) != str(plan.get("compiled_result_sha256") or "")
        or _sha256(predecessor_path)
        != str(plan.get("predecessor_pack_sha256") or "")
    ):
        raise ValueError("external_source_evidence_file_binding_invalid")
    compiled = _load(compiled_path)
    predecessor = _load(predecessor_path)
    validate_reviewed_evidence_pack(predecessor)
    if (
        str(compiled.get("result_digest") or "")
        != str(plan.get("compiled_result_digest") or "")
        or str(predecessor.get("pack_payload_digest") or "")
        != str(plan.get("predecessor_pack_payload_digest") or "")
    ):
        raise ValueError("external_source_evidence_content_binding_invalid")

    evidence = adjudicate_external_source_evidence(
        compiled_result=compiled,
        plan=plan,
    )
    retirements = [
        dict(row) for row in plan.get("predecessor_evidence_retirements") or ()
    ]
    builder = (
        build_reviewed_evidence_pack_correction_successor
        if retirements
        else build_reviewed_evidence_pack_successor
    )
    builder_kwargs = {
        "predecessor": predecessor,
        "evidence_result": evidence,
        "accepted_result_statuses": (
            "external_source_evidence_gate_passed_internal_engineering",
        ),
        "gap_ids_satisfied": plan.get("gap_ids_satisfied") or (),
        "successor_lineage": {
            "recorded_at": plan.get("recorded_at"),
            "source_family": "captured_external_source_ladder",
            "adjudication_plan_id": plan.get("plan_id"),
            "adjudication_plan_digest": plan.get("plan_digest"),
            "compiled_result_digest": compiled.get("result_digest"),
            "predecessor_pack_payload_digest": predecessor.get(
                "pack_payload_digest"
            ),
            "evidence_result_digest": evidence.get("result_digest"),
            "retirement_receipt_digest": (
                canonical_digest(retirements) if retirements else None
            ),
        },
        "content_gate_basis": (
            "reviewed_predecessor_plus_capture_bound_source_use_gated_external_ladder"
        ),
        "known_boundary_suffix": (
            "The added Evidence preserves issuer-direct versus bounded ecosystem "
            "roles. Industry, channel and media material cannot create Dell "
            "exact ASP, unit, allocation, yield, profit or causal authority. "
            "Any retired item is a digest-bound stale source identity replaced "
            "by corrected Evidence, not a silent deletion. This internal "
            "engineering successor does not qualify S1, grant qualified-human "
            "acceptance or authorize publication."
        ),
    }
    if retirements:
        builder_kwargs["retirements"] = retirements
    successor = builder(
        **builder_kwargs,
    )
    direct_count = sum(
        row.get("disposition") == "accepted_direct_source_evidence"
        for row in evidence.get("accepted_evidence_items") or ()
    )
    bounded_count = sum(
        row.get("disposition") == "accepted_bounded_context_evidence"
        for row in evidence.get("accepted_evidence_items") or ()
    )
    summary_body = {
        "schema_version": "fin_ia_s1_external_source_evidence_successor_public_result_v1_0",
        "status": "external_source_evidence_successor_materialized",
        "recorded_at": plan.get("recorded_at"),
        "case_key": plan.get("case_key"),
        "research_as_of": plan.get("research_as_of"),
        "plan_id": plan.get("plan_id"),
        "plan_digest": plan.get("plan_digest"),
        "compiled_result_digest": compiled.get("result_digest"),
        "evidence_result_schema": EXTERNAL_SOURCE_EVIDENCE_RESULT_SCHEMA_VERSION,
        "evidence_result_digest": evidence.get("result_digest"),
        "predecessor_pack_payload_digest": predecessor.get("pack_payload_digest"),
        "successor_pack_payload_digest": successor.get("pack_payload_digest"),
        "coverage_delta": {
            "predecessor_evidence_count": len(predecessor.get("evidence_items") or ()),
            "added_direct_evidence_count": direct_count,
            "added_bounded_context_evidence_count": bounded_count,
            "retired_evidence_count": len(retirements),
            "successor_evidence_count": len(successor.get("evidence_items") or ()),
            "residual_gap_count_before": len(predecessor.get("residual_gaps") or ()),
            "residual_gap_count_after": len(successor.get("residual_gaps") or ()),
            "gap_closed_count": len(plan.get("gap_ids_satisfied") or ()),
            "gap_narrowed_count": len(evidence.get("gap_ids_narrowed") or ()),
        },
        "affected_slot_ids": sorted(
            {
                str(binding.get("slot_id") or "")
                for row in evidence.get("accepted_evidence_items") or ()
                for binding in row.get("slot_bindings") or ()
            }
        ),
        "authority": {
            "qualified_human_review": False,
            "S1_qualification": False,
            "product_publication": False,
            "model_calls": 0,
            "network_calls": 0,
        },
        "known_boundary": (
            "The external ladder adds reviewed issuer facts and bounded industry, "
            "channel and media context. Remaining gaps stay explicit until a "
            "separate closure receipt or S2 derivation qualifies them."
        ),
    }
    return evidence, successor, {
        **summary_body,
        "result_digest": canonical_digest(summary_body),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Adjudicate reviewed external candidates and materialize one "
            "immutable Evidence Pack successor."
        )
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--public-product-result", type=Path)
    args = parser.parse_args()
    evidence, successor, summary = materialize(_load(args.plan.resolve()))
    output_dir = args.output_dir.resolve()
    evidence_path = output_dir / "evidence_gate_result.json"
    pack_path = output_dir / "pack.json"
    summary_path = output_dir / "result.json"
    _write(evidence_path, evidence)
    _write(pack_path, successor)
    summary["private_artifacts"] = {
        "evidence_result_ref": str(evidence_path.relative_to(ROOT)).replace("\\", "/"),
        "evidence_result_sha256": _sha256(evidence_path),
        "pack_ref": str(pack_path.relative_to(ROOT)).replace("\\", "/"),
        "pack_sha256": _sha256(pack_path),
    }
    unsigned = dict(summary)
    unsigned.pop("result_digest", None)
    summary["result_digest"] = canonical_digest(unsigned)
    _write(summary_path, summary)
    if args.public_product_result is not None:
        if _git("status", "--porcelain"):
            raise RuntimeError(
                "external_source_product_projection_clean_worktree_required"
            )
        projection = _product_successor_projection(
            plan=_load(args.plan.resolve()),
            evidence=evidence,
            successor=successor,
            summary=summary,
            summary_path=summary_path,
            pack_path=pack_path,
        )
        public_path = args.public_product_result.resolve()
        if public_path.exists():
            raise FileExistsError(
                "external_source_product_projection_output_exists"
            )
        _write(public_path, projection)
    print(json.dumps(summary["coverage_delta"], ensure_ascii=False, indent=2))
    print(f"result_digest={summary['result_digest']}")
    print(f"output={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
