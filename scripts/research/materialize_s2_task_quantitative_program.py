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

from sec_agent.canonical_runtime.session import canonical_digest  # noqa: E402
from sec_agent.research.task_quantitative_program import (  # noqa: E402
    compile_task_quantitative_program,
)


DEFAULT_PROGRAM = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_dell_task_quantitative_program_v1_0.json"
)
DEFAULT_PRIVATE_OUTPUT = (
    "data/workbench_private/fin_0_1_3_s2_task_quantitative_program/"
    "dell-r1/full_result.json"
)
DEFAULT_PUBLIC_OUTPUT = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_dell_task_quantitative_program_result_v1_0.json"
)


def _resolve(ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"s2_task_quantitative_json_object_required:{path.name}")
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


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(
            f"s2_task_quantitative_output_exists:{_relative(path)}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _require_binding(
    *,
    path: Path,
    binding: Mapping[str, Any],
    ref_key: str,
    sha_key: str,
) -> None:
    if _relative(path) != str(binding.get(ref_key) or ""):
        raise ValueError(f"s2_task_quantitative_{ref_key}_mismatch")
    if _sha256(path) != str(binding.get(sha_key) or ""):
        raise ValueError(f"s2_task_quantitative_{sha_key}_mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--program", default=DEFAULT_PROGRAM)
    parser.add_argument("--private-output", default=DEFAULT_PRIVATE_OUTPUT)
    parser.add_argument("--public-output", default=DEFAULT_PUBLIC_OUTPUT)
    args = parser.parse_args()

    if _git_output("status", "--porcelain"):
        raise RuntimeError("s2_task_quantitative_clean_worktree_required")
    prepared_from_commit = _git_output("rev-parse", "HEAD")
    recorded_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    program_path = _resolve(args.program)
    program = _json(program_path)
    pack_binding = dict(program.get("evidence_pack_binding") or {})
    replay_binding = dict(program.get("source_route_replay_binding") or {})
    pack_path = _resolve(str(pack_binding.get("pack_ref") or ""))
    replay_path = _resolve(str(replay_binding.get("full_result_ref") or ""))
    _require_binding(
        path=pack_path,
        binding=pack_binding,
        ref_key="pack_ref",
        sha_key="pack_sha256",
    )
    _require_binding(
        path=replay_path,
        binding=replay_binding,
        ref_key="full_result_ref",
        sha_key="full_result_sha256",
    )
    evidence_pack = _json(pack_path)
    replay = _json(replay_path)
    if replay.get("result_digest") != replay_binding.get("result_digest"):
        raise ValueError("s2_task_quantitative_replay_digest_mismatch")
    product_projection = replay.get("product_projection")
    if not isinstance(product_projection, Mapping):
        raise ValueError("s2_task_quantitative_product_projection_missing")
    request_results = product_projection.get("request_results")
    if not isinstance(request_results, list):
        raise ValueError("s2_task_quantitative_request_results_missing")

    projection = compile_task_quantitative_program(
        program=program,
        evidence_pack=evidence_pack,
        request_results=request_results,
        recorded_at=recorded_at,
    )
    source_bindings = {
        "program": {"ref": _relative(program_path), "sha256": _sha256(program_path)},
        "evidence_pack": {"ref": _relative(pack_path), "sha256": _sha256(pack_path)},
        "source_route_replay": {
            "ref": _relative(replay_path),
            "sha256": _sha256(replay_path),
        },
    }
    full_body = {
        "schema_version": "fin_ia_s2_task_quantitative_program_full_result_v1_0",
        "status": "completed_zero_call_task_quantitative_program",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "source_bindings": source_bindings,
        "task_quantitative_projection": projection,
        "execution": {
            "network_calls": 0,
            "generation_model_calls": 0,
            "embedding_calls": 0,
            "reranker_calls": 0,
            "numeric_fact_creations": 0,
            "research_estimate_creations": len(
                projection["quantitative_authority"]["research_estimates"]
            ),
            "scenario_creations": len(
                projection["quantitative_authority"]["scenarios"]
            ),
            "public_information_gap_claims": 0,
        },
    }
    full_result = {**full_body, "result_digest": canonical_digest(full_body)}
    private_output = _resolve(args.private_output)
    public_output = _resolve(args.public_output)
    _write_new_json(private_output, full_result)
    private_sha256 = _sha256(private_output)

    quantitative = projection["quantitative_authority"]
    public_body = {
        "schema_version": "fin_ia_s2_task_quantitative_program_public_result_v1_0",
        "status": projection["status"],
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": projection["case_key"],
        "research_as_of": projection["research_as_of"],
        "evidence_pack_binding": projection["evidence_pack_binding"],
        "quantitative_summary": quantitative["summary"],
        "research_estimates": quantitative["research_estimates"],
        "scenarios": quantitative["scenarios"],
        "estimate_bindings": projection["research_estimate_bindings"],
        "scenario_bindings": projection["scenario_bindings"],
        "typed_gap_dispositions": projection["typed_gap_dispositions"],
        "task_readiness": projection["task_readiness"],
        "authority": projection["authority"],
        "source_bindings": source_bindings,
        "full_result_ref": _relative(private_output),
        "full_result_sha256": private_sha256,
        "known_boundary": projection["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new_json(public_output, public)
    print(
        json.dumps(
            {
                "status": public["status"],
                "prepared_from_commit": prepared_from_commit,
                "quantitative_summary": public["quantitative_summary"],
                "task_readiness": public["task_readiness"],
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
