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
from sec_agent.research.product_value_bridge import (  # noqa: E402
    compile_product_value_bridge,
)


DEFAULT_PROGRAM = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_dell_product_value_bridge_program_v1_0.json"
)
DEFAULT_PRIVATE_OUTPUT = (
    "data/workbench_private/fin_0_1_3_s2_product_value_bridge/"
    "dell-r1/full_result.json"
)
DEFAULT_PUBLIC_OUTPUT = (
    "configs/financial_facts/"
    "fin_ia_0_1_3_s2_dell_product_value_bridge_result_v1_0.json"
)


def _resolve(ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"product_value_bridge_json_object_required:{path.name}")
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


def _write_new(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"product_value_bridge_output_exists:{_relative(path)}")
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
        raise RuntimeError("product_value_bridge_clean_worktree_required")
    prepared_from_commit = _git_output("rev-parse", "HEAD")
    recorded_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    program_path = _resolve(args.program)
    program = _json(program_path)
    pack_binding = dict(program.get("evidence_pack_binding") or {})
    quantitative_binding = dict(program.get("task_quantitative_result_binding") or {})
    pack_path = _resolve(str(pack_binding.get("ref") or ""))
    quantitative_public_path = _resolve(str(quantitative_binding.get("ref") or ""))
    if (
        _relative(pack_path) != pack_binding.get("ref")
        or _sha256(pack_path) != pack_binding.get("sha256")
    ):
        raise ValueError("product_value_bridge_pack_file_binding_invalid")
    if (
        _relative(quantitative_public_path) != quantitative_binding.get("ref")
        or _sha256(quantitative_public_path) != quantitative_binding.get("sha256")
    ):
        raise ValueError("product_value_bridge_quantitative_file_binding_invalid")
    quantitative_public = _json(quantitative_public_path)
    if quantitative_public.get("result_digest") != quantitative_binding.get(
        "result_digest"
    ):
        raise ValueError("product_value_bridge_quantitative_digest_invalid")
    quantitative_private_path = _resolve(
        str(quantitative_public.get("full_result_ref") or "")
    )
    if _sha256(quantitative_private_path) != quantitative_public.get(
        "full_result_sha256"
    ):
        raise ValueError("product_value_bridge_quantitative_private_invalid")
    quantitative_full = _json(quantitative_private_path)
    projection = quantitative_full.get("task_quantitative_projection")
    if not isinstance(projection, Mapping):
        raise ValueError("product_value_bridge_quantitative_projection_missing")

    bridge = compile_product_value_bridge(
        program=program,
        evidence_pack=_json(pack_path),
        quantitative_projection=projection,
        recorded_at=recorded_at,
    )
    source_bindings = {
        "program": {"ref": _relative(program_path), "sha256": _sha256(program_path)},
        "evidence_pack": {"ref": _relative(pack_path), "sha256": _sha256(pack_path)},
        "task_quantitative_public_result": {
            "ref": _relative(quantitative_public_path),
            "sha256": _sha256(quantitative_public_path),
            "result_digest": quantitative_public.get("result_digest"),
        },
        "task_quantitative_private_result": {
            "ref": _relative(quantitative_private_path),
            "sha256": _sha256(quantitative_private_path),
        },
    }
    full_body = {
        "schema_version": "fin_ia_s2_product_value_bridge_full_result_v1_0",
        "status": "completed_zero_call_product_value_bridge",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "source_bindings": source_bindings,
        "product_value_bridge": bridge,
        "execution": {
            "network_calls": 0,
            "provider_calls": 0,
            "generation_model_calls": 0,
            "embedding_calls": 0,
            "reranker_calls": 0,
            "numeric_fact_creations": 0,
            "deterministic_source_surface_derivations": len(
                bridge["deterministic_source_surface_derivations"]
            ),
            "public_information_gap_claims": 0,
        },
    }
    full = {**full_body, "result_digest": canonical_digest(full_body)}
    private_output = _resolve(args.private_output)
    public_output = _resolve(args.public_output)
    _write_new(private_output, full)
    private_sha = _sha256(private_output)
    public_body = {
        "schema_version": "fin_ia_s2_product_value_bridge_public_result_v1_0",
        "status": bridge["status"],
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": bridge["case_key"],
        "research_as_of": bridge["research_as_of"],
        "evidence_pack_payload_digest": bridge["evidence_pack_payload_digest"],
        "task_quantitative_projection_digest": bridge[
            "task_quantitative_projection_digest"
        ],
        "source_numeric_observations": bridge["source_numeric_observations"],
        "deterministic_source_surface_derivations": bridge[
            "deterministic_source_surface_derivations"
        ],
        "company_context": bridge["company_context"],
        "pvm_bridge": bridge["pvm_bridge"],
        "product_profit_bridge": bridge["product_profit_bridge"],
        "bridge_gap_receipts": bridge["bridge_gap_receipts"],
        "bridge_readiness": bridge["bridge_readiness"],
        "authority": bridge["authority"],
        "source_bindings": source_bindings,
        "full_result_ref": _relative(private_output),
        "full_result_sha256": private_sha,
        "known_boundary": bridge["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(public_output, public)
    print(
        json.dumps(
            {
                "status": public["status"],
                "prepared_from_commit": prepared_from_commit,
                "bridge_readiness": public["bridge_readiness"],
                "pvm_state": public["pvm_bridge"]["state"],
                "profit_bridge_state": public["product_profit_bridge"]["state"],
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
