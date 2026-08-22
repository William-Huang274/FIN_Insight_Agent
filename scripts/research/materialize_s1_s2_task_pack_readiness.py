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

from retrieval.integrated_pack_readiness import (  # noqa: E402
    compile_integrated_requirement_readiness,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.task_pack_readiness import (  # noqa: E402
    compile_requirement_review_successor,
    compile_task_pack_readiness,
)


DEFAULT_PROGRAM = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_s2_dell_value_capture_task_readiness_program_v1_0.json"
)
DEFAULT_PRIVATE_OUTPUT = (
    "data/workbench_private/fin_0_1_3_s1_s2_task_pack_readiness/"
    "dell-value-capture-r1/full_result.json"
)
DEFAULT_PUBLIC_OUTPUT = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_s2_dell_value_capture_task_readiness_result_v1_0.json"
)


def _resolve(ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"task_pack_readiness_json_object_required:{path.name}")
    return payload


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


def _write_new(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"task_pack_readiness_output_exists:{_relative(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--program", default=DEFAULT_PROGRAM)
    parser.add_argument("--private-output", default=DEFAULT_PRIVATE_OUTPUT)
    parser.add_argument("--public-output", default=DEFAULT_PUBLIC_OUTPUT)
    args = parser.parse_args()

    if _git_output("status", "--porcelain"):
        raise RuntimeError("task_pack_readiness_clean_worktree_required")
    prepared_from_commit = _git_output("rev-parse", "HEAD")
    recorded_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    program_path = _resolve(args.program)
    program = _json(program_path)
    if (
        program.get("schema_version")
        != "fin_ia_s1_s2_task_pack_readiness_materialization_program_v1_0"
        or program.get("status")
        != "approved_zero_call_task_pack_readiness_materialization"
    ):
        raise ValueError("task_pack_readiness_materialization_program_invalid")

    source_paths: dict[str, Path] = {}
    inputs: dict[str, dict[str, Any]] = {}
    for key, raw_binding in dict(program.get("input_bindings") or {}).items():
        binding = dict(raw_binding)
        path = _resolve(str(binding.get("ref") or ""))
        if _relative(path) != binding.get("ref") or _sha256(path) != binding.get(
            "sha256"
        ):
            raise ValueError(f"task_pack_readiness_input_binding_invalid:{key}")
        source_paths[key] = path
        inputs[key] = _json(path)

    quantitative_public = inputs["task_quantitative_public_result"]
    quantitative_binding = program["input_bindings"][
        "task_quantitative_public_result"
    ]
    if quantitative_public.get("result_digest") != quantitative_binding.get(
        "result_digest"
    ):
        raise ValueError("task_pack_readiness_quantitative_result_digest_mismatch")
    quantitative_private_path = _resolve(
        str(quantitative_public.get("full_result_ref") or "")
    )
    if _sha256(quantitative_private_path) != quantitative_public.get(
        "full_result_sha256"
    ):
        raise ValueError("task_pack_readiness_quantitative_private_sha_mismatch")
    quantitative_full = _json(quantitative_private_path)
    quantitative_projection = quantitative_full.get("task_quantitative_projection")
    if not isinstance(quantitative_projection, Mapping):
        raise ValueError("task_pack_readiness_quantitative_projection_missing")

    successor = compile_requirement_review_successor(
        program=program["review_successor_program"],
        predecessor_review_plan=inputs["predecessor_review_plan"],
        predecessor_polarity_plan=inputs["predecessor_polarity_plan"],
        evidence_pack=inputs["evidence_pack"],
        recorded_at=recorded_at,
    )
    product_projection = inputs["product_replay"].get("product_projection")
    if not isinstance(product_projection, Mapping):
        raise ValueError("task_pack_readiness_product_projection_missing")
    integrated = compile_integrated_requirement_readiness(
        product_projection=product_projection,
        evidence_pack=inputs["evidence_pack"],
        review_plan=successor["review_plan"],
        polarity_plan=successor["polarity_plan"],
        anchor_catalog=inputs["anchor_catalog"],
        recorded_at=recorded_at,
    )
    readiness = compile_task_pack_readiness(
        program=program["task_readiness_program"],
        integrated_readiness=integrated,
        quantitative_projection=quantitative_projection,
        evidence_pack=inputs["evidence_pack"],
        recorded_at=recorded_at,
    )
    source_bindings = {
        "program": {"ref": _relative(program_path), "sha256": _sha256(program_path)},
        **{
            key: {"ref": _relative(path), "sha256": _sha256(path)}
            for key, path in source_paths.items()
        },
        "task_quantitative_private_result": {
            "ref": _relative(quantitative_private_path),
            "sha256": _sha256(quantitative_private_path),
        },
    }
    full_body = {
        "schema_version": "fin_ia_s1_s2_task_pack_readiness_full_result_v1_0",
        "status": "completed_zero_call_task_pack_readiness",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "source_bindings": source_bindings,
        "review_successor": successor,
        "integrated_readiness": integrated,
        "task_pack_readiness": readiness,
        "execution": {
            "network_calls": 0,
            "provider_calls": 0,
            "generation_model_calls": 0,
            "embedding_calls": 0,
            "reranker_calls": 0,
            "evidence_promotions": 0,
            "numeric_fact_creations": 0,
            "public_information_gap_claims": 0,
        },
    }
    full_result = {**full_body, "result_digest": canonical_digest(full_body)}
    private_output = _resolve(args.private_output)
    public_output = _resolve(args.public_output)
    _write_new(private_output, full_result)
    private_sha256 = _sha256(private_output)

    requirement_states = {
        row["requirement_id"]: {
            "request_id": row["request_id"],
            "integrated_state": row["integrated_state"],
            "research_consumable": row["research_consumable"],
            "fully_satisfied": row["fully_satisfied"],
            "addressed_product_ids": row["addressed_product_ids"],
            "unaddressed_product_ids": row["unaddressed_product_ids"],
            "claim_boundary_zh": row["claim_boundary_zh"],
        }
        for row in integrated["requirements"]
    }
    public_body = {
        "schema_version": "fin_ia_s1_s2_task_pack_readiness_public_result_v1_0",
        "status": readiness["status"],
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": readiness["case_key"],
        "cell_id": readiness["cell_id"],
        "evidence_pack_payload_digest": readiness["evidence_pack_payload_digest"],
        "review_plan_digest": successor["review_plan_digest"],
        "polarity_plan_digest": successor["polarity_plan_digest"],
        "integrated_readiness_digest": integrated["result_digest"],
        "integrated_summary": integrated["summary"],
        "request_states": integrated["requests"],
        "requirement_states": requirement_states,
        "task_pack_readiness": readiness,
        "authority": {
            **readiness["authority"],
            "new_evidence_promoted_in_this_run": False,
            "model_or_network_calls": 0,
        },
        "source_bindings": source_bindings,
        "full_result_ref": _relative(private_output),
        "full_result_sha256": private_sha256,
        "known_boundary": readiness["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(public_output, public)
    print(
        json.dumps(
            {
                "status": public["status"],
                "prepared_from_commit": prepared_from_commit,
                "integrated_summary": public["integrated_summary"],
                "actionable_gap_requests": readiness["actionable_gap_requests"],
                "private_output": _relative(private_output),
                "public_output": _relative(public_output),
                "result_digest": public["result_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
