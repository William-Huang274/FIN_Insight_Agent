from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.public_context_evidence import (  # noqa: E402
    PUBLIC_CONTEXT_EVIDENCE_RESULT_SCHEMA_VERSION,
    adjudicate_public_context_evidence,
)
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    build_reviewed_evidence_pack_successor,
    canonical_digest,
    validate_reviewed_evidence_pack,
)


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def materialize(plan: dict) -> tuple[dict, dict, dict]:
    compiled_path = _resolve(str(plan.get("compiled_result_ref") or ""))
    predecessor_path = _resolve(str(plan.get("predecessor_pack_ref") or ""))
    compiled = _load(compiled_path)
    predecessor = _load(predecessor_path)
    validate_reviewed_evidence_pack(predecessor)
    if (
        str(compiled.get("result_digest") or "")
        != str(plan.get("compiled_result_digest") or "")
        or str(predecessor.get("pack_payload_digest") or "")
        != str(plan.get("predecessor_pack_payload_digest") or "")
    ):
        raise ValueError("public_context_evidence_materialization_binding_invalid")

    evidence_result = adjudicate_public_context_evidence(
        compiled_result=compiled,
        plan=plan,
    )
    successor = build_reviewed_evidence_pack_successor(
        predecessor=predecessor,
        evidence_result=evidence_result,
        accepted_result_statuses=(
            "public_context_evidence_gate_passed_internal_engineering",
        ),
        gap_ids_satisfied=[],
        successor_lineage={
            "recorded_at": plan.get("recorded_at"),
            "source_family": "captured_free_public_context",
            "adjudication_plan_id": plan.get("plan_id"),
            "adjudication_plan_digest": plan.get("plan_digest"),
            "compiled_result_digest": compiled.get("result_digest"),
            "predecessor_pack_payload_digest": predecessor.get(
                "pack_payload_digest"
            ),
            "evidence_result_digest": evidence_result.get("result_digest"),
        },
        content_gate_basis=(
            "reviewed_predecessor_plus_capture_bound_source_use_gated_public_context"
        ),
        known_boundary_suffix=(
            "The added sources remain speaker-, industry- or competitor-bound; "
            "they do not establish Dell-specific allocation, ASP, unit volume, "
            "profit, cash conversion or causal attribution. This internal "
            "engineering successor does not qualify S1, grant qualified-human "
            "acceptance or authorize publication."
        ),
    )
    summary_body = {
        "schema_version": "fin_ia_s1_public_context_evidence_successor_public_result_v1_0",
        "status": "public_context_evidence_successor_materialized",
        "recorded_at": plan.get("recorded_at"),
        "case_key": plan.get("case_key"),
        "research_as_of": plan.get("research_as_of"),
        "plan_id": plan.get("plan_id"),
        "plan_digest": plan.get("plan_digest"),
        "compiled_result_digest": compiled.get("result_digest"),
        "evidence_result_schema": PUBLIC_CONTEXT_EVIDENCE_RESULT_SCHEMA_VERSION,
        "evidence_result_digest": evidence_result.get("result_digest"),
        "predecessor_pack_payload_digest": predecessor.get("pack_payload_digest"),
        "successor_pack_payload_digest": successor.get("pack_payload_digest"),
        "coverage_delta": {
            "predecessor_evidence_count": len(predecessor.get("evidence_items") or ()),
            "added_bounded_context_evidence_count": len(
                evidence_result.get("accepted_evidence_items") or ()
            ),
            "successor_evidence_count": len(successor.get("evidence_items") or ()),
            "residual_gap_count_before": len(predecessor.get("residual_gaps") or ()),
            "residual_gap_count_after": len(successor.get("residual_gaps") or ()),
            "gap_closed_count": 0,
        },
        "source_count": len(
            {
                row.get("source_record_id")
                for row in evidence_result.get("source_materials") or ()
            }
        ),
        "affected_slot_ids": sorted(
            {
                str(binding.get("slot_id") or "")
                for row in evidence_result.get("accepted_evidence_items") or ()
                for binding in row.get("slot_bindings") or ()
            }
        ),
        "authority": {
            "target_company_exact_numeric_authority_granted": False,
            "causal_attribution_authorized": False,
            "qualified_human_review": False,
            "S1_qualification": False,
            "product_publication": False,
            "model_calls": 0,
            "network_calls": 0,
        },
        "known_boundary": (
            "Seven free-public-source propositions are now usable as bounded "
            "research context. No Dell-specific residual gap was closed."
        ),
    }
    return (
        evidence_result,
        successor,
        {**summary_body, "result_digest": canonical_digest(summary_body)},
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Adjudicate public context and materialize one reviewed-Pack successor."
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    plan = _load(args.plan.resolve())
    evidence_result, successor, summary = materialize(plan)
    output_dir = args.output_dir.resolve()
    evidence_path = output_dir / "evidence_result.json"
    pack_path = output_dir / "pack.json"
    summary_path = output_dir / "result.json"
    _write(evidence_path, evidence_result)
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
    print(json.dumps(summary["coverage_delta"], ensure_ascii=False, indent=2))
    print(f"result_digest={summary['result_digest']}")
    print(f"output={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
