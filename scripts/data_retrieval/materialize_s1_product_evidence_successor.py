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

from retrieval.product_evidence_successor import (  # noqa: E402
    build_product_evidence_successor,
    compile_product_evidence_adjudication_policy,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


FULL_RESULT_SCHEMA_VERSION = (
    "fin_ia_s1_product_evidence_successor_full_result_v1_0"
)
PUBLIC_RESULT_SCHEMA_VERSION = (
    "fin_ia_s1_product_evidence_successor_public_result_v1_0"
)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"product_evidence_json_invalid:{path.name}")
    return value


def _read_jsonl_by_id(path: Path, id_field: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            _require(
                isinstance(value, dict),
                f"product_evidence_jsonl_row_invalid:{path.name}:{line_number}",
            )
            row_id = str(value.get(id_field) or "")
            _require(
                bool(row_id) and row_id not in rows,
                f"product_evidence_jsonl_identity_invalid:{path.name}:{line_number}",
            )
            rows[row_id] = value
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()


def _require_clean() -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _require(not status, "product_evidence_successor_clean_worktree_required")


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _capture_resolver(reference: str) -> Path:
    raw = Path(reference)
    for candidate in (
        raw,
        ROOT / raw,
        ROOT / "data/workbench_private/source_intake" / raw,
        ROOT / "data/workbench_private" / raw,
    ):
        if candidate.is_file():
            return candidate.resolve()
    return (ROOT / raw).resolve()


def _verify_bound_input(
    *,
    actual_path: Path,
    binding: Mapping[str, Any],
    code: str,
) -> None:
    _require(
        _relative(actual_path) == str(binding.get("ref") or "")
        and _sha256(actual_path) == str(binding.get("sha256") or ""),
        code,
    )


def _public_projection(
    *,
    full_result: Mapping[str, Any],
    private_result_output: Path,
    private_pack_output: Path,
) -> dict[str, Any]:
    core = full_result["successor_result"]
    decisions = core["decision_counts"]
    body = {
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "status": "proposition_bound_evidence_successor_materialized",
        "recorded_at": full_result["recorded_at"],
        "prepared_from_commit": full_result["prepared_from_commit"],
        "case_key": full_result["case_key"],
        "plan_id": full_result["adjudication_plan"]["plan_id"],
        "plan_digest": full_result["adjudication_plan"]["plan_digest"],
        "predecessor_pack_payload_digest": core[
            "predecessor_pack_payload_digest"
        ],
        "successor_pack_payload_digest": core["successor_pack"][
            "pack_payload_digest"
        ],
        "decision_counts": decisions,
        "capture_receipt_count": len(core["capture_receipts"]),
        "coverage_delta": core["coverage_delta"],
        "private_pack_ref": _relative(private_pack_output),
        "private_pack_sha256": _sha256(private_pack_output),
        "full_result_ref": _relative(private_result_output),
        "full_result_sha256": None,
        "authority": core["authority"],
        "known_boundary": (
            "This tracked projection records an internal engineering adjudication. "
            "Accepted claims are immutable-capture-bound and explicitly attached to "
            "a named requirement or request context. Request context does not satisfy "
            "a hard material requirement, metric rows remain delegated to S2, and "
            "this result does not qualify S1, grant qualified-human review or authorize "
            "publication. Candidate text and private object identities remain private."
        ),
    }
    return body


def materialize(
    *,
    replay_path: Path,
    readiness_path: Path,
    predecessor_pack_path: Path,
    compiled_objects_path: Path,
    source_records_path: Path,
    parent_documents_path: Path,
    plan_path: Path,
    private_result_output: Path,
    private_pack_output: Path,
    public_output: Path,
) -> dict[str, Any]:
    _require_clean()
    replay = _read_json(replay_path)
    readiness = _read_json(readiness_path)
    predecessor = _read_json(predecessor_pack_path)
    plan = _read_json(plan_path)
    product_projection = replay.get("product_projection")
    review_packet = readiness.get("candidate_review_packet")
    _require(
        isinstance(product_projection, Mapping)
        and isinstance(review_packet, Mapping),
        "product_evidence_successor_projection_or_packet_missing",
    )
    bindings = readiness.get("source_bindings")
    _require(
        isinstance(bindings, Mapping),
        "product_evidence_successor_source_bindings_missing",
    )
    replay_binding = dict(bindings.get("candidate_replay") or {})
    compiled_binding = dict(bindings.get("compiled_financial_objects") or {})
    source_binding = dict(bindings.get("current_source_records") or {})
    _verify_bound_input(
        actual_path=replay_path,
        binding=replay_binding,
        code="product_evidence_successor_replay_drift",
    )
    _verify_bound_input(
        actual_path=compiled_objects_path,
        binding=compiled_binding,
        code="product_evidence_successor_compiled_object_drift",
    )
    _verify_bound_input(
        actual_path=source_records_path,
        binding=source_binding,
        code="product_evidence_successor_source_record_drift",
    )
    parent_sha256 = _sha256(parent_documents_path)
    _require(
        replay_binding.get("result_digest") == replay.get("result_digest")
        and str(plan.get("parent_documents_sha256") or "") == parent_sha256
        and str(plan.get("predecessor_pack_payload_digest") or "")
        == str(predecessor.get("pack_payload_digest") or "")
        and str(
            dict(bindings.get("current_reviewed_evidence_projection") or {}).get(
                "pack_payload_digest"
            )
            or ""
        )
        == str(predecessor.get("pack_payload_digest") or ""),
        "product_evidence_successor_pack_or_parent_binding_invalid",
    )
    compiled_objects = _read_jsonl_by_id(
        compiled_objects_path, "compiled_object_id"
    )
    source_records = _read_jsonl_by_id(source_records_path, "evidence_id")
    parent_documents = _read_jsonl_by_id(parent_documents_path, "document_id")
    policy = compile_product_evidence_adjudication_policy(
        candidate_review_packet=review_packet,
        plan=plan,
    )
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    successor_result = build_product_evidence_successor(
        predecessor=predecessor,
        product_projection=product_projection,
        candidate_review_packet=review_packet,
        policy=policy,
        compiled_objects_by_id=compiled_objects,
        source_records_by_id=source_records,
        parent_documents_by_id=parent_documents,
        capture_resolver=_capture_resolver,
        recorded_at=recorded_at,
    )
    _write_new(private_pack_output, successor_result["successor_pack"])
    body = {
        "schema_version": FULL_RESULT_SCHEMA_VERSION,
        "status": "proposition_bound_evidence_successor_materialized",
        "recorded_at": recorded_at,
        "prepared_from_commit": _head(),
        "case_key": str(product_projection.get("case_key") or "").upper(),
        "source_bindings": {
            "candidate_replay": replay_binding,
            "product_readiness": {
                "ref": _relative(readiness_path),
                "sha256": _sha256(readiness_path),
                "result_digest": readiness.get("result_digest"),
                "candidate_review_packet_digest": review_packet.get(
                    "review_packet_digest"
                ),
            },
            "predecessor_pack": {
                "ref": _relative(predecessor_pack_path),
                "sha256": _sha256(predecessor_pack_path),
                "pack_payload_digest": predecessor.get("pack_payload_digest"),
            },
            "compiled_financial_objects": compiled_binding,
            "current_source_records": source_binding,
            "parent_documents": {
                "ref": _relative(parent_documents_path),
                "sha256": parent_sha256,
            },
            "adjudication_plan": {
                "ref": _relative(plan_path),
                "sha256": _sha256(plan_path),
                "plan_digest": plan.get("plan_digest"),
            },
        },
        "adjudication_plan": plan,
        "compiled_policy": policy,
        "successor_result": successor_result,
        "private_pack_binding": {
            "ref": _relative(private_pack_output),
            "sha256": _sha256(private_pack_output),
            "pack_payload_digest": successor_result["successor_pack"][
                "pack_payload_digest"
            ],
        },
    }
    full_result = {**body, "result_digest": canonical_digest(body)}
    _write_new(private_result_output, full_result)
    public = _public_projection(
        full_result=full_result,
        private_result_output=private_result_output,
        private_pack_output=private_pack_output,
    )
    public["full_result_sha256"] = _sha256(private_result_output)
    public_result = {**public, "result_digest": canonical_digest(public)}
    _write_new(public_output, public_result)
    return public_result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize a proposition-bound S1 Evidence Pack successor."
    )
    parser.add_argument("--replay", required=True)
    parser.add_argument("--readiness", required=True)
    parser.add_argument("--predecessor-pack", required=True)
    parser.add_argument("--compiled-objects", required=True)
    parser.add_argument("--source-records", required=True)
    parser.add_argument("--parent-documents", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--private-result-output", required=True)
    parser.add_argument("--private-pack-output", required=True)
    parser.add_argument("--public-output", required=True)
    args = parser.parse_args()
    result = materialize(
        replay_path=_resolve(args.replay),
        readiness_path=_resolve(args.readiness),
        predecessor_pack_path=_resolve(args.predecessor_pack),
        compiled_objects_path=_resolve(args.compiled_objects),
        source_records_path=_resolve(args.source_records),
        parent_documents_path=_resolve(args.parent_documents),
        plan_path=_resolve(args.plan),
        private_result_output=_resolve(args.private_result_output),
        private_pack_output=_resolve(args.private_pack_output),
        public_output=_resolve(args.public_output),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
