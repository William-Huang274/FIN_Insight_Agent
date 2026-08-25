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

from retrieval.dell_report_residual_source_program import (  # noqa: E402
    compile_dell_report_residual_source_program,
)


DEFAULT_POLICY = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_report_residual_source_ladder_policy_v1_0.json"
)
DEFAULT_ADMISSION_MANIFEST = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_report_evidence_admission_manifest_v1_0.json"
)
DEFAULT_OUTPUT = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_report_residual_source_ladder_program_v1_0.json"
)


class DellReportResidualSourceMaterializationError(RuntimeError):
    pass


def _resolve(ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise DellReportResidualSourceMaterializationError(
            "dell_report_residual_path_outside_repository"
        ) from exc


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DellReportResidualSourceMaterializationError(
            f"dell_report_residual_json_object_required:{path.name}"
        )
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
        raise DellReportResidualSourceMaterializationError(
            "dell_report_residual_clean_worktree_required"
        )


def _render_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def _write_new(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(
            f"dell_report_residual_output_exists:{_relative(path)}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(_render_json(payload))


def compile_materialization(
    *,
    policy_path: Path,
    admission_manifest_path: Path,
    recorded_at: str,
    prepared_from_commit: str,
) -> dict[str, Any]:
    policy = _read_json(policy_path)
    payloads: dict[str, dict[str, Any]] = {}
    sha256_by_ref: dict[str, str] = {}
    for name, raw_binding in dict(policy.get("input_bindings") or {}).items():
        binding = dict(raw_binding)
        ref = str(binding.get("ref") or "")
        raw = _resolve(ref).read_bytes()
        sha256_by_ref[ref] = _sha256_bytes(raw)
        if binding.get("digest_field") is not None:
            payloads[name] = json.loads(raw.decode("utf-8"))
    admission_raw = admission_manifest_path.read_bytes()
    return compile_dell_report_residual_source_program(
        policy=policy,
        input_payloads=payloads,
        input_sha256_by_ref=sha256_by_ref,
        admission_manifest=json.loads(admission_raw.decode("utf-8")),
        admission_manifest_ref=_relative(admission_manifest_path),
        admission_manifest_sha256=_sha256_bytes(admission_raw),
        recorded_at=recorded_at,
        prepared_from_commit=prepared_from_commit,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--admission-manifest", default=DEFAULT_ADMISSION_MANIFEST)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    _require_clean_worktree(_git_output("status", "--porcelain"))
    output_path = _resolve(args.output)
    if output_path.exists():
        raise FileExistsError(
            f"dell_report_residual_output_exists:{_relative(output_path)}"
        )
    compiled = compile_materialization(
        policy_path=_resolve(args.policy),
        admission_manifest_path=_resolve(args.admission_manifest),
        recorded_at=datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds"
        ),
        prepared_from_commit=_git_output("rev-parse", "HEAD"),
    )
    _write_new(output_path, compiled)
    print(
        json.dumps(
            {
                "status": compiled["status"],
                "counts": compiled["counts"],
                "program_digest": compiled["program_digest"],
                "output": _relative(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
