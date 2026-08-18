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
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.integrated_pack_readiness import (  # noqa: E402
    compile_integrated_requirement_readiness,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


DEFAULT_PRODUCT_REPLAY = (
    "data/workbench_private/fin_0_1_3_s1_material_scope_product_replay/"
    "dell-r3-v2/full_result.json"
)
DEFAULT_EVIDENCE_PACK = (
    "data/workbench_private/fin_0_1_3_s1_vs4_dell_supplement_vertical/v1_0/"
    "packs/dell/c61ea7a02634ec21944ec6edc9b127c474e3474116dfe501932455664fc3dc23.json"
)
DEFAULT_REVIEW_PLAN = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_natural_requirement_evidence_review_v1_0.json"
)
DEFAULT_ANCHOR_CATALOG = (
    "configs/runtime/fin_ia_0_1_3_current_reviewed_claim_anchor_catalog_v1_2.json"
)
DEFAULT_PRIVATE_OUTPUT = (
    "data/workbench_private/fin_0_1_3_s1_integrated_pack_readiness/"
    "dell-r3-v1/full_result.json"
)
DEFAULT_PUBLIC_OUTPUT = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_integrated_pack_readiness_result_v1_0.json"
)


def _resolve(ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"integrated_readiness_json_object_required:{path.name}")
    return value


def _sha256(path: Path) -> str:
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


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"integrated_readiness_output_exists:{_relative(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _public_projection(
    *,
    full_result: Mapping[str, Any],
    private_output: Path,
    private_sha256: str,
) -> dict[str, Any]:
    result = dict(full_result["integrated_readiness"])
    requirements = []
    for row in result["requirements"]:
        numeric = row["numeric_coverage"]
        requirements.append(
            {
                "requirement_id": row["requirement_id"],
                "request_id": row["request_id"],
                "facet_id": row["facet_id"],
                "role": row["role"],
                "evidence_decision_state": row["evidence_decision_state"],
                "supported_product_ids": row["supported_product_ids"],
                "unsupported_product_ids": row["unsupported_product_ids"],
                "numeric_state": numeric["state"],
                "resolved_metric_count": numeric["resolved_metric_count"],
                "typed_gap_metric_count": numeric["typed_gap_metric_count"],
                "numeric_gap_owning_stages": sorted(
                    {
                        str(metric.get("owning_stage") or "")
                        for metric in numeric["metrics"]
                        if metric.get("state") == "typed_gap"
                    }
                    - {""}
                ),
                "integrated_state": row["integrated_state"],
                "research_consumable": row["research_consumable"],
                "fully_satisfied": row["fully_satisfied"],
                "decision_reason_zh": row["decision_reason_zh"],
                "claim_boundary_zh": row["claim_boundary_zh"],
            }
        )
    not_ready_requests = int(result["summary"]["request_count"]) - int(
        result["summary"]["research_consumable_request_count"]
    )
    status = (
        "completed_development_readiness_all_requests_consumable"
        if not_ready_requests == 0
        else "completed_development_readiness_with_residual_requests"
    )
    body = {
        "schema_version": "fin_ia_s1_s2_integrated_pack_readiness_public_v1_0",
        "status": status,
        "recorded_at": full_result["recorded_at"],
        "prepared_from_commit": full_result["prepared_from_commit"],
        "case_key": result["case_key"],
        "research_plan_digest": result["research_plan_digest"],
        "scope_compilation_digest": result["scope_compilation_digest"],
        "evidence_pack_payload_digest": result["evidence_pack_payload_digest"],
        "review_plan_digest": result["review_plan_digest"],
        "summary": result["summary"],
        "requests": result["requests"],
        "requirements": requirements,
        "authority": result["authority"],
        "source_bindings": full_result["source_bindings"],
        "full_result_ref": _relative(private_output),
        "full_result_sha256": private_sha256,
        "known_boundary": result["known_boundary"],
    }
    return {**body, "result_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-replay", default=DEFAULT_PRODUCT_REPLAY)
    parser.add_argument("--evidence-pack", default=DEFAULT_EVIDENCE_PACK)
    parser.add_argument("--review-plan", default=DEFAULT_REVIEW_PLAN)
    parser.add_argument("--anchor-catalog", default=DEFAULT_ANCHOR_CATALOG)
    parser.add_argument("--private-output", default=DEFAULT_PRIVATE_OUTPUT)
    parser.add_argument("--public-output", default=DEFAULT_PUBLIC_OUTPUT)
    args = parser.parse_args()

    dirty = _git_output("status", "--porcelain")
    if dirty:
        raise RuntimeError("integrated_readiness_clean_worktree_required")
    prepared_from_commit = _git_output("rev-parse", "HEAD")
    recorded_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    paths = {
        "product_replay": _resolve(args.product_replay),
        "evidence_pack": _resolve(args.evidence_pack),
        "review_plan": _resolve(args.review_plan),
        "anchor_catalog": _resolve(args.anchor_catalog),
    }
    inputs = {key: _load_json(path) for key, path in paths.items()}
    product_projection = inputs["product_replay"].get("product_projection")
    if not isinstance(product_projection, Mapping):
        raise ValueError("integrated_readiness_product_projection_missing")
    integrated = compile_integrated_requirement_readiness(
        product_projection=product_projection,
        evidence_pack=inputs["evidence_pack"],
        review_plan=inputs["review_plan"],
        anchor_catalog=inputs["anchor_catalog"],
        recorded_at=recorded_at,
    )
    source_bindings = {
        key: {"ref": _relative(path), "sha256": _sha256(path)}
        for key, path in paths.items()
    }
    full_body = {
        "schema_version": "fin_ia_s1_s2_integrated_pack_readiness_full_v1_0",
        "status": "completed_zero_call_integrated_readiness",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "source_bindings": source_bindings,
        "integrated_readiness": integrated,
        "execution": {
            "network_calls": 0,
            "generation_model_calls": 0,
            "embedding_calls": 0,
            "reranker_calls": 0,
            "candidate_text_promotions": 0,
            "evidence_promotions": 0,
            "numeric_fact_creations": 0,
            "public_information_gap_claims": 0,
        },
    }
    full_result = {**full_body, "result_digest": canonical_digest(full_body)}
    private_output = _resolve(args.private_output)
    public_output = _resolve(args.public_output)
    _write_new_json(private_output, full_result)
    private_sha256 = _sha256(private_output)
    public = _public_projection(
        full_result=full_result,
        private_output=private_output,
        private_sha256=private_sha256,
    )
    _write_new_json(public_output, public)
    print(
        json.dumps(
            {
                "status": public["status"],
                "prepared_from_commit": prepared_from_commit,
                "summary": public["summary"],
                "public_output": _relative(public_output),
                "private_output": _relative(private_output),
                "result_digest": public["result_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
