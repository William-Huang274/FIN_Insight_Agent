from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from retrieval.evidence_admission import (  # noqa: E402
    compile_qualified_human_admission_packet,
)
from retrieval.human_operability import (  # noqa: E402
    load_human_operability_program,
)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "admission_materializer_json_object_required")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    _require(
        rows and all(isinstance(row, dict) for row in rows),
        "admission_materializer_jsonl_invalid",
    )
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def materialize(
    *,
    program_path: Path,
    private_output: Path,
    public_manifest_output: Path,
    recorded_at: str,
) -> dict[str, Any]:
    program = load_human_operability_program(program_path)
    case_results: list[dict[str, Any]] = []
    compiled_binding: dict[str, Any] | None = None
    source_binding: dict[str, Any] | None = None
    readiness_bindings: list[dict[str, Any]] = []
    for binding in program.get("development_case_readiness") or ():
        public_path = ROOT / str(binding["ref"])
        _require(
            public_path.is_file() and _sha256(public_path) == binding["sha256"],
            "admission_materializer_public_readiness_drift",
        )
        public = _read_json(public_path)
        private_path = ROOT / str(public["full_result_ref"])
        _require(
            private_path.is_file()
            and _sha256(private_path) == public["full_result_sha256"],
            "admission_materializer_private_readiness_drift",
        )
        current = _read_json(private_path)
        case_results.append(current)
        current_compiled = dict(
            (current.get("source_bindings") or {}).get(
                "compiled_financial_objects"
            )
            or {}
        )
        current_source = dict(
            (current.get("source_bindings") or {}).get("current_source_records")
            or {}
        )
        if compiled_binding is None:
            compiled_binding = current_compiled
            source_binding = current_source
        _require(
            current_compiled == compiled_binding and current_source == source_binding,
            "admission_materializer_case_snapshot_drift",
        )
        readiness_bindings.append(
            {
                "case_key": public["case_key"],
                "public_ref": _relative(public_path),
                "public_sha256": binding["sha256"],
                "private_ref": _relative(private_path),
                "private_sha256": public["full_result_sha256"],
            }
        )
    _require(
        compiled_binding is not None and source_binding is not None,
        "admission_materializer_bindings_missing",
    )
    compiled_path = ROOT / str(compiled_binding["ref"])
    source_path = ROOT / str(source_binding["ref"])
    _require(
        compiled_path.is_file()
        and _sha256(compiled_path) == compiled_binding["sha256"],
        "admission_materializer_compiled_snapshot_drift",
    )
    _require(
        source_path.is_file() and _sha256(source_path) == source_binding["sha256"],
        "admission_materializer_source_snapshot_drift",
    )
    packet = compile_qualified_human_admission_packet(
        current_case_results=case_results,
        compiled_objects=_read_jsonl(compiled_path),
        source_records=_read_jsonl(source_path),
        recorded_at=recorded_at,
    )
    _write_new(private_output, packet)
    manifest = {
        "schema_version": "fin_ia_s1_qualified_human_evidence_admission_manifest_v1_0",
        "status": "review_packet_ready_qualified_human_receipts_pending",
        "recorded_at": recorded_at,
        "program_ref": _relative(program_path),
        "program_sha256": _sha256(program_path),
        "readiness_bindings": readiness_bindings,
        "compiled_object_snapshot": compiled_binding,
        "source_record_snapshot": source_binding,
        "private_packet_ref": _relative(private_output),
        "private_packet_sha256": _sha256(private_output),
        "private_packet_digest": packet["packet_digest"],
        "case_count": packet["case_count"],
        "pending_request_count": packet["pending_request_count"],
        "pending_requirement_count": packet["pending_requirement_count"],
        "candidate_binding_count": packet["candidate_binding_count"],
        "authority": {
            "candidate_is_evidence": False,
            "numeric_fact_authority": False,
            "qualified_human_receipts_pending": True,
            "S1_qualification_authority": False,
        },
    }
    _write_new(public_manifest_output, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize the current three-case qualified-human Evidence admission packet."
    )
    parser.add_argument("--program", required=True)
    parser.add_argument("--private-output", required=True)
    parser.add_argument("--public-manifest-output", required=True)
    parser.add_argument(
        "--recorded-at",
        default=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    args = parser.parse_args()
    result = materialize(
        program_path=_resolve(args.program),
        private_output=_resolve(args.private_output),
        public_manifest_output=_resolve(args.public_manifest_output),
        recorded_at=args.recorded_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
