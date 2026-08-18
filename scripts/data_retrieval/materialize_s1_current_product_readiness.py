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

from apps.workbench.backend.application.research_evidence_pack_service import (  # noqa: E402
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from retrieval.product_pack_readiness import (  # noqa: E402
    compile_product_candidate_decision_ledger,
    compile_product_pack_readiness,
)
from retrieval.product_candidate_review import (  # noqa: E402
    compile_product_candidate_review_packet,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    validate_reviewed_evidence_pack,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths  # noqa: E402


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"product_readiness_json_not_mapping:{path.name}")
    return value


def _read_jsonl_by_id(path: Path, id_field: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(
                    f"product_readiness_jsonl_row_invalid:{path.name}:{line_number}"
                )
            row_id = str(value.get(id_field) or "")
            if not row_id or row_id in rows:
                raise ValueError(
                    f"product_readiness_jsonl_identity_invalid:{path.name}:{line_number}"
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
    if status:
        raise RuntimeError("product_readiness_clean_worktree_required")


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _public_projection(
    *,
    full_result: Mapping[str, Any],
    private_output: Path,
) -> dict[str, Any]:
    readiness = full_result["pack_readiness"]
    review_packet = full_result["candidate_review_packet"]
    review_by_request = {
        row["request_id"]: row for row in review_packet["requests"]
    }
    request_rows = []
    for row in readiness["requests"]:
        requirements = list(row["requirements"])
        review = review_by_request[row["request_id"]]
        request_rows.append(
            {
                "request_id": row["request_id"],
                "slot_id": row["slot_id"],
                "facet_id": row["facet_id"],
                "business_question_zh": row["business_question_zh"],
                "readiness_state": row["readiness_state"],
                "material_scope_ready": row["material_scope_ready"],
                "requirement_count": len(requirements),
                "requirement_state_counts": dict(
                    sorted(
                        {
                            state: sum(
                                requirement["readiness_state"] == state
                                for requirement in requirements
                            )
                            for state in {
                                requirement["readiness_state"]
                                for requirement in requirements
                            }
                        }.items()
                    )
                ),
                "candidate_decision_counts": row["candidate_decision_counts"],
                "numeric_authority_state": {
                    key: row["numeric_authority_state"][key]
                    for key in (
                        "state",
                        "request_count",
                        "resolved_count",
                        "typed_gap_count",
                        "typed_conflict_count",
                    )
                },
                "unexecuted_or_unavailable_routes": row[
                    "route_execution_state"
                ]["unexecuted_or_unavailable_routes"],
                "required_candidate_routes_all_executed": row[
                    "route_execution_state"
                ]["required_candidate_routes_all_executed"],
                "required_candidate_routes_unexecuted": row[
                    "route_execution_state"
                ]["required_candidate_routes_unexecuted"],
                "source_route_execution_truth": {
                    key: row["route_execution_state"][key]
                    for key in (
                        "source_route_execution_truth_bound",
                        "source_supplement_route_required",
                        "source_route_execution_state_counts",
                        "official_or_external_supplement_route_exhausted",
                        "source_non_disclosure_adjudicated",
                    )
                },
                "candidate_review_summary": {
                    "review_item_count": review["review_item_count"],
                    "human_review_required_count": review[
                        "human_review_required_count"
                    ],
                    "issue_class_counts": review["issue_class_counts"],
                    "request_review_digest": review["request_review_digest"],
                },
            }
        )
    body = {
        "schema_version": "fin_ia_s1_current_product_readiness_result_v1_1",
        "status": "current_product_pack_readiness_materialized",
        "recorded_at": full_result["recorded_at"],
        "prepared_from_commit": full_result["prepared_from_commit"],
        "case_key": readiness["case_key"],
        "readiness_state": readiness["readiness_state"],
        "request_count": readiness["request_count"],
        "request_state_counts": readiness["request_state_counts"],
        "candidate_count": readiness["candidate_count"],
        "accepted_reviewed_evidence_count": len(
            readiness["accepted_reviewed_evidence_digests"]
        ),
        "gap_eligibility_receipt_count": len(
            readiness["gap_eligibility_receipts"]
        ),
        "declared_pack_gap_receipt_count": len(
            readiness["declared_pack_gap_receipts"]
        ),
        "requests": request_rows,
        "candidate_review_packet_summary": {
            "schema_version": review_packet["schema_version"],
            "status": review_packet["status"],
            "review_item_count": review_packet["review_item_count"],
            "human_review_required_count": review_packet[
                "human_review_required_count"
            ],
            "issue_class_counts": review_packet["issue_class_counts"],
            "review_packet_digest": review_packet["review_packet_digest"],
            "private_packet_required_for_bounded_excerpt_projection": True,
        },
        "full_result_ref": _relative(private_output),
        "full_result_sha256": None,
        "authority": readiness["authority"],
        "known_boundary": (
            "This public projection reports product CandidateDecision, current reviewed "
            "Evidence reuse, S2 numeric authority and gap eligibility without exposing "
            "candidate text, object identifiers or private source material in the tracked "
            "artifact. A digest-bound private packet may be projected as bounded excerpts "
            "only inside the authenticated local Workbench. It does not qualify S1, "
            "declare a public-information gap or authorize publication."
        ),
    }
    return body


def materialize(
    *,
    replay_path: Path,
    compiled_objects_path: Path,
    source_records_path: Path,
    evidence_pack_path: Path | None,
    private_output: Path,
    public_output: Path,
) -> dict[str, Any]:
    _require_clean()
    replay = _read_json(replay_path)
    projection = replay.get("product_projection")
    if not isinstance(projection, Mapping):
        raise ValueError("product_readiness_product_projection_missing")
    case_key = str(projection.get("case_key") or "").upper()
    if evidence_pack_path is None:
        paths = resolve_runtime_paths(ROOT)
        pack_service = ResearchEvidencePackService.from_runtime_paths(ROOT, paths)
        principal = ResearchEvidencePackPrincipal(
            mode="current", permissions=frozenset({"current_product:read"})
        )
        evidence_pack = pack_service.get_case(case_key, principal)
        evidence_pack_binding = {
            "source_kind": "registered_current_product_projection",
            "result_digest": evidence_pack.get("result_digest"),
            "artifact_digest": evidence_pack.get("artifact_digest"),
            "pack_payload_digest": evidence_pack.get("pack_payload_digest"),
        }
    else:
        evidence_pack = _read_json(evidence_pack_path)
        validate_reviewed_evidence_pack(evidence_pack)
        if str(evidence_pack.get("case_key") or "").upper() != case_key:
            raise ValueError("product_readiness_evidence_pack_case_mismatch")
        evidence_pack_binding = {
            "source_kind": "explicit_digest_bound_product_evidence_successor",
            "ref": _relative(evidence_pack_path),
            "sha256": _sha256(evidence_pack_path),
            "pack_payload_digest": evidence_pack.get("pack_payload_digest"),
        }
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ledgers = [
        compile_product_candidate_decision_ledger(
            request_result=request_result,
            evidence_pack=evidence_pack,
            recorded_at=recorded_at,
        )
        for request_result in projection.get("request_results") or ()
    ]
    compiled_objects = _read_jsonl_by_id(
        compiled_objects_path, "compiled_object_id"
    )
    source_records = _read_jsonl_by_id(source_records_path, "evidence_id")
    review_packet = compile_product_candidate_review_packet(
        product_projection=projection,
        candidate_decision_ledgers=ledgers,
        compiled_objects_by_id=compiled_objects,
        source_records_by_id=source_records,
        recorded_at=recorded_at,
    )
    readiness = compile_product_pack_readiness(
        product_projection=projection,
        evidence_pack=evidence_pack,
        candidate_decision_ledgers=ledgers,
        recorded_at=recorded_at,
    )
    body = {
        "schema_version": "fin_ia_s1_current_product_readiness_full_result_v1_1",
        "status": "current_product_pack_readiness_materialized",
        "recorded_at": recorded_at,
        "prepared_from_commit": _head(),
        "case_key": case_key,
        "source_bindings": {
            "candidate_replay": {
                "ref": _relative(replay_path),
                "sha256": _sha256(replay_path),
                "result_digest": replay.get("result_digest"),
            },
            "current_reviewed_evidence_projection": evidence_pack_binding,
            "compiled_financial_objects": {
                "ref": _relative(compiled_objects_path),
                "sha256": _sha256(compiled_objects_path),
            },
            "current_source_records": {
                "ref": _relative(source_records_path),
                "sha256": _sha256(source_records_path),
            },
        },
        "candidate_decision_ledgers": ledgers,
        "candidate_review_packet": review_packet,
        "pack_readiness": readiness,
        "authority": readiness["authority"],
    }
    full_result = {**body, "result_digest": canonical_digest(body)}
    _write_new(private_output, full_result)
    public = _public_projection(
        full_result=full_result, private_output=private_output
    )
    public["full_result_sha256"] = _sha256(private_output)
    public_result = {**public, "result_digest": canonical_digest(public)}
    _write_new(public_output, public_result)
    return public_result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize current S1 CandidateDecision and PackReadiness."
    )
    parser.add_argument("--replay", required=True)
    parser.add_argument("--compiled-objects", required=True)
    parser.add_argument("--source-records", required=True)
    parser.add_argument("--evidence-pack")
    parser.add_argument("--private-output", required=True)
    parser.add_argument("--public-output", required=True)
    args = parser.parse_args()
    result = materialize(
        replay_path=_resolve(args.replay),
        compiled_objects_path=_resolve(args.compiled_objects),
        source_records_path=_resolve(args.source_records),
        evidence_pack_path=(
            _resolve(args.evidence_pack) if args.evidence_pack else None
        ),
        private_output=_resolve(args.private_output),
        public_output=_resolve(args.public_output),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
