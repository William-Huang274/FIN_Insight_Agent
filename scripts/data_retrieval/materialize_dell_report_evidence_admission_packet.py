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

from retrieval.dell_report_evidence_admission import (  # noqa: E402
    compile_dell_report_evidence_admission_packet,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


DEFAULT_PROGRAM = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_report_evidence_admission_program_v1_0.json"
)
DEFAULT_PRIVATE_OUTPUT = (
    "data/workbench_private/fin_0_1_3_dell_report_evidence_admission/"
    "dell-r1/full_result.json"
)
DEFAULT_PUBLIC_OUTPUT = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_report_evidence_admission_manifest_v1_0.json"
)


class DellReportEvidenceAdmissionMaterializationError(RuntimeError):
    pass


def _resolve(ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise DellReportEvidenceAdmissionMaterializationError(
            "dell_report_admission_path_outside_repository"
        ) from exc


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DellReportEvidenceAdmissionMaterializationError(
            f"dell_report_admission_json_object_required:{path.name}"
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
        raise DellReportEvidenceAdmissionMaterializationError(
            "dell_report_admission_clean_worktree_required"
        )


def _render_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def _write_new(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(
            f"dell_report_admission_output_exists:{_relative(path)}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(_render_json(payload))


def compile_materialization(
    *,
    program_path: Path,
    private_output_path: Path,
    recorded_at: str,
    prepared_from_commit: str,
) -> dict[str, dict[str, Any]]:
    program = _read_json(program_path)
    payloads: dict[str, dict[str, Any]] = {}
    sha256_by_ref: dict[str, str] = {}
    for name, raw_binding in dict(program.get("input_bindings") or {}).items():
        binding = dict(raw_binding)
        ref = str(binding.get("ref") or "")
        raw = _resolve(ref).read_bytes()
        sha256_by_ref[ref] = _sha256_bytes(raw)
        if binding.get("digest_field") is not None:
            payloads[name] = json.loads(raw.decode("utf-8"))
    compiled = compile_dell_report_evidence_admission_packet(
        program=program,
        input_payloads=payloads,
        input_sha256_by_ref=sha256_by_ref,
        private_output_ref=_relative(private_output_path),
        recorded_at=recorded_at,
        prepared_from_commit=prepared_from_commit,
    )
    private_bytes = _render_json(compiled["private"])
    public_body = {
        key: value
        for key, value in compiled["public"].items()
        if key != "result_digest"
    }
    public_body["private_full_result_sha256"] = _sha256_bytes(private_bytes)
    compiled["public"] = {
        **public_body,
        "result_digest": canonical_digest(public_body),
    }
    return compiled


def main() -> int:
    parser = argparse.ArgumentParser()
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
            f"dell_report_admission_output_exists:{_relative(existing)}"
        )
    compiled = compile_materialization(
        program_path=_resolve(args.program),
        private_output_path=private_output,
        recorded_at=datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds"
        ),
        prepared_from_commit=_git_output("rev-parse", "HEAD"),
    )
    _write_new(private_output, compiled["private"])
    _write_new(public_output, compiled["public"])
    print(
        json.dumps(
            {
                "status": compiled["public"]["status"],
                "counts": compiled["public"]["counts"],
                "admission_packet_digest": compiled["public"][
                    "admission_packet_digest"
                ],
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
