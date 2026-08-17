from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
for candidate in (ROOT, SRC_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from apps.workbench.backend.application.research_evidence_pack_service import (  # noqa: E402
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.artifact_spine import (  # noqa: E402
    canonical_json_digest,
    load_artifact_spine_policy,
    sha256_file,
)
from retrieval.vertical_slice import (  # noqa: E402
    VS1_RESULT_SCHEMA_VERSION,
    VS1_RESULT_RESOURCE_ID,
    build_vs1_artifact_chain,
    compile_candidate_decision_ledger,
    compile_evidence_coverage_state,
    compile_evidence_pack_readiness,
    compile_workbench_projection,
    load_s1_vs1_vertical_slice_result,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths  # noqa: E402
from sec_agent.runtime_resource_registry import (  # noqa: E402
    DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
    read_registered_runtime_json,
)


CURRENT_VS1_RESOURCE_ID = VS1_RESULT_RESOURCE_ID
CURRENT_PACK_RESOURCE_ID = "application.result.current_research_local_evidence_packs"
CURRENT_SNAPSHOT_RESOURCE_ID = "application.result.current_research_retrieval_snapshot"
CURRENT_SPINE_POLICY_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_canonical_artifact_spine_policy_v1_0.json"
)
CURRENT_SOURCE_MANIFEST_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1b_current_source_object_manifest_v1_1.json"
)
CURRENT_OBJECT_STORE_RESULT_REF = (
    "configs/runtime/fin_ia_0_1_3_s1b_current_financial_object_store_result_v1_1.json"
)
CURRENT_REQUEST_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_vs1_dell_pricing_mix_request_v1_0.json"
)
DEFAULT_OUTPUT_REF = (
    "configs/runtime/fin_ia_0_1_3_s1_vs1_vertical_slice_result_v1_1.json"
)
RECORDED_AT = "2026-08-17"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_mapping_required:{path.name}")
    return value


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _repo_ref(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _strict_relative(value: str) -> Path:
    normalized = str(value).replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts or normalized != path.as_posix():
        raise ValueError("vs1_path_invalid")
    return path


def _source_payload_bindings(
    *,
    source_manifest: Mapping[str, Any],
    object_store_result: Mapping[str, Any],
    inline_prefix: str,
) -> dict[str, dict[str, Any]]:
    results = {
        str(row.get("source_id") or ""): row
        for row in object_store_result.get("source_results") or ()
    }
    bindings: dict[str, dict[str, Any]] = {}
    for source in source_manifest.get("sources") or ():
        source_id = str(source.get("source_id") or "")
        result = results[source_id]
        source_path = _resolve(str(source["path"]))
        source_sha = sha256_file(source_path)
        if source.get("input_kind") == "parsed_official_pdf_document":
            parsed = _read_json(source_path)
            raw_ref = (
                ROOT
                / "data/workbench_private/source_intake"
                / _strict_relative(str(parsed["raw_object_ref"]))
            ).resolve()
            raw_ref.relative_to(ROOT)
            if sha256_file(raw_ref) != str(parsed["raw_object_sha256"]):
                raise ValueError(f"vs1_raw_pdf_digest_drift:{source_id}")
            bindings[source_id] = {
                "capture_ref": _repo_ref(raw_ref),
                "capture_sha256": str(parsed["raw_object_sha256"]),
                "capture_schema_version": "fin_ia_capture_first_raw_binary_v1_0",
                "parsed_ref": _repo_ref(source_path),
                "parsed_sha256": source_sha,
                "parsed_schema_version": str(parsed["schema_version"]),
            }
        else:
            parsed_receipt = {
                "source_id": source_id,
                "input_kind": source.get("input_kind"),
                "source_sha256": result.get("source_sha256"),
                "document_parents_added": result.get("document_parents_added"),
                "invalid_records_excluded": result.get("invalid_records_excluded"),
            }
            bindings[source_id] = {
                "capture_ref": _repo_ref(source_path),
                "capture_sha256": source_sha,
                "capture_schema_version": "fin_ia_existing_immutable_source_v1_0",
                "parsed_ref": f"{inline_prefix}/parsed_receipts/{source_id}",
                "parsed_sha256": canonical_json_digest(parsed_receipt),
                "parsed_schema_version": "fin_ia_vs1_existing_parser_receipt_v1_0",
            }
    return bindings


def _pack_artifact(result: Mapping[str, Any], case_key: str) -> dict[str, Any]:
    raw = (result.get("pack_artifacts") or {}).get(case_key)
    if not isinstance(raw, Mapping):
        raise ValueError("vs1_pack_artifact_missing")
    return deepcopy(dict(raw))


def _inline_payloads(
    *,
    source_manifest: Mapping[str, Any],
    object_store_result: Mapping[str, Any],
    request_result: Mapping[str, Any],
    source_bindings: Mapping[str, Mapping[str, Any]],
    ledger: Mapping[str, Any],
    coverage: Mapping[str, Any],
    readiness: Mapping[str, Any],
    workbench: Mapping[str, Any],
    frozen_probe: Mapping[str, Any],
) -> dict[str, Any]:
    """Materialize every result-local payload asserted by an envelope."""

    results = {
        str(row.get("source_id") or ""): row
        for row in object_store_result.get("source_results") or ()
    }
    source_routes: dict[str, Any] = {}
    parsed_receipts: dict[str, Any] = {}
    financial_objects: dict[str, Any] = {}
    for source in source_manifest.get("sources") or ():
        source_id = str(source.get("source_id") or "")
        result = results[source_id]
        source_routes[source_id] = {
            "source_id": source_id,
            "input_kind": source.get("input_kind"),
            "source_url": source.get("source_url"),
            "route_id": source.get("route_id"),
            "expected_sha256": source.get("expected_sha256"),
            "required": source.get("required"),
        }
        if str(source_bindings[source_id]["parsed_ref"]).startswith(
            f"{CURRENT_VS1_RESOURCE_ID}#"
        ):
            parsed_receipts[source_id] = {
                "source_id": source_id,
                "input_kind": source.get("input_kind"),
                "source_sha256": result.get("source_sha256"),
                "document_parents_added": result.get("document_parents_added"),
                "invalid_records_excluded": result.get("invalid_records_excluded"),
            }
        financial_objects[source_id] = {
            "source_id": source_id,
            "document_parents_added": result.get("document_parents_added"),
            "retrieval_children_added": result.get("retrieval_children_added"),
            "invalid_records_excluded": result.get("invalid_records_excluded"),
            "source_sha256": result.get("source_sha256"),
        }

    candidate_ids: list[str] = []
    seen: set[str] = set()
    for lane in request_result.get("lanes") or ():
        for candidate in lane.get("candidates") or ():
            source_record_id = str(candidate.get("source_record_id") or "")
            if source_record_id and source_record_id not in seen:
                seen.add(source_record_id)
                candidate_ids.append(source_record_id)

    return {
        "source_routes": source_routes,
        "parsed_receipts": parsed_receipts,
        "financial_objects": financial_objects,
        "evidence_request": deepcopy(request_result["request"]),
        "query_facet_plan": deepcopy(request_result["query_plan"]),
        "candidate_set": {
            "candidate_state": "candidate_not_evidence",
            "request_id": request_result["request"].get("request_id"),
            "source_record_ids": candidate_ids,
        },
        "candidate_ranking": {
            "ranking_contract": "current_typed_financial_candidate_order",
            "candidate_state": "candidate_not_evidence",
            "rows": [
                {
                    "rank": row["rank"],
                    "source_record_id": row["source_record_id"],
                    "score": row.get("score"),
                }
                for row in ledger.get("decisions") or ()
            ],
        },
        "candidate_decision_ledger": deepcopy(dict(ledger)),
        "evidence_coverage_state": deepcopy(dict(coverage)),
        "evidence_pack_readiness": deepcopy(dict(readiness)),
        "workbench_projection": deepcopy(dict(workbench)),
        "frozen_consumer_probe": deepcopy(dict(frozen_probe)),
        "source_payload_bindings": deepcopy(dict(source_bindings)),
    }


def compile_result(
    *,
    evidence_pack_result_ref: str | None = None,
    reviewed_anchor_catalog_ref: str | None = None,
) -> dict[str, Any]:
    runtime_paths = resolve_runtime_paths(ROOT)
    # Bootstrap from the predecessor Runtime without trying to read the VS1
    # result that this command is currently materializing.
    retrieval = ResearchRetrievalService.from_runtime_paths(
        ROOT,
        runtime_paths,
        load_s1_vertical_slice=False,
    )
    if evidence_pack_result_ref is None:
        evidence_packs = ResearchEvidencePackService.from_runtime_paths(
            ROOT,
            runtime_paths,
            load_s1_vertical_slice=False,
        )
        pack_result = read_registered_runtime_json(ROOT, CURRENT_PACK_RESOURCE_ID)
    else:
        evidence_config = read_registered_runtime_json(
            ROOT, "application.config.current_research_evidence_pack_projection"
        )
        if reviewed_anchor_catalog_ref is None:
            raise ValueError("vs1_historical_anchor_catalog_required")
        pack_result = _read_json(_resolve(evidence_pack_result_ref))
        evidence_packs = ResearchEvidencePackService(
            config=evidence_config,
            result=pack_result,
            private_object_root=(
                runtime_paths.reviewed_evidence_root
                / str(evidence_config["private_object_root_relative"])
            ),
            private_root_base=runtime_paths.reviewed_evidence_root,
            reviewed_anchor_catalog=_read_json(
                _resolve(reviewed_anchor_catalog_ref)
            ),
        )
    request = _read_json(_resolve(CURRENT_REQUEST_REF))
    principal = ResearchRetrievalPrincipal(
        mode="current", permissions=frozenset({"current_product:read"})
    )
    request_result = retrieval.execute_request("DELL", request, principal)
    pack_projection = evidence_packs.get_case(
        "DELL",
        ResearchEvidencePackPrincipal(
            mode="current", permissions=frozenset({"current_product:read"})
        ),
    )
    # The safe projection is enough for decisions, but the pack artifact and
    # capture-bound successor lineage remain bound through the current result.
    pack_artifact = _pack_artifact(pack_result, "DELL")
    pack_root = runtime_paths.reviewed_evidence_root
    if pack_artifact.get("private_object_root_relative"):
        pack_root = pack_root / _strict_relative(
            str(pack_artifact["private_object_root_relative"])
        )
    pack_path = (
        pack_root / _strict_relative(str(pack_artifact["object_key"]))
    ).resolve()
    pack_path.relative_to(runtime_paths.reviewed_evidence_root.resolve())
    if sha256_file(pack_path) != str(pack_artifact["digest"]):
        raise ValueError("vs1_pack_artifact_digest_drift")
    pack = _read_json(pack_path)
    if (
        pack.get("pack_payload_digest")
        != pack_projection.get("pack_payload_digest")
    ):
        raise ValueError("vs1_pack_projection_payload_drift")

    ledger = compile_candidate_decision_ledger(
        request_result=request_result,
        evidence_pack=pack,
        recorded_at=RECORDED_AT,
    )
    coverage = compile_evidence_coverage_state(
        request_result=request_result,
        decision_ledger=ledger,
        evidence_pack=pack,
        recorded_at=RECORDED_AT,
    )
    readiness = compile_evidence_pack_readiness(
        coverage=coverage,
        decision_ledger=ledger,
        evidence_pack=pack,
        pack_artifact_digest=str(pack_artifact["digest"]),
        recorded_at=RECORDED_AT,
    )
    workbench = compile_workbench_projection(
        decision_ledger=ledger,
        coverage=coverage,
        readiness=readiness,
        recorded_at=RECORDED_AT,
    )
    frozen_probe_body = {
        "schema_version": "fin_ia_s1_frozen_consumer_probe_v1_0",
        "status": "pack_and_workbench_share_readiness_lineage",
        "case_key": "DELL",
        "evidence_pack_consumer_binding": deepcopy(readiness["pack_binding"]),
        "workbench_consumer_binding": deepcopy(readiness["pack_binding"]),
        "readiness_digest": readiness["readiness_digest"],
        "same_pack_binding": True,
        "same_readiness_lineage": True,
    }
    frozen_probe = {
        **frozen_probe_body,
        "frozen_consumer_probe_digest": canonical_json_digest(frozen_probe_body),
    }

    object_store_result = _read_json(_resolve(CURRENT_OBJECT_STORE_RESULT_REF))
    source_manifest_path = _resolve(CURRENT_SOURCE_MANIFEST_REF)
    source_manifest = _read_json(source_manifest_path)
    snapshot_path = _resolve(
        "configs/runtime/fin_ia_0_1_3_current_retrieval_snapshot_v1_0.json"
    )
    output_ref = DEFAULT_OUTPUT_REF
    inline_prefix = f"{CURRENT_VS1_RESOURCE_ID}#/payloads"
    source_bindings = _source_payload_bindings(
        source_manifest=source_manifest,
        object_store_result=object_store_result,
        inline_prefix=inline_prefix,
    )
    policy = load_artifact_spine_policy(_resolve(CURRENT_SPINE_POLICY_REF))
    envelopes = build_vs1_artifact_chain(
        policy=policy,
        source_manifest=source_manifest,
        source_results=object_store_result["source_results"],
        source_payload_bindings=source_bindings,
        object_manifest_ref=CURRENT_SOURCE_MANIFEST_REF,
        object_manifest_sha256=sha256_file(source_manifest_path),
        index_snapshot_ref=_repo_ref(snapshot_path),
        index_snapshot_sha256=sha256_file(snapshot_path),
        request_result=request_result,
        decision_ledger=ledger,
        coverage=coverage,
        readiness=readiness,
        workbench_projection=workbench,
        frozen_consumer_probe=frozen_probe,
        inline_payload_ref_prefix=inline_prefix,
    )
    artifact_refs: dict[str, list[dict[str, Any]]] = {}
    for envelope in envelopes:
        artifact_refs.setdefault(envelope.artifact_type, []).append(
            {
                "artifact_id": envelope.artifact_id,
                "artifact_version": envelope.artifact_version,
                "payload_sha256": envelope.payload_sha256,
                "lineage_digest": envelope.lineage_digest,
            }
        )
    case_payload = {
        "candidate_decision_ledger": ledger,
        "candidate_decision_ledger_digest": ledger[
            "candidate_decision_ledger_digest"
        ],
        "coverage_state": coverage,
        "coverage_state_digest": coverage["coverage_state_digest"],
        "readiness": readiness,
        "readiness_digest": readiness["readiness_digest"],
        "workbench_projection": workbench,
        "workbench_projection_digest": workbench[
            "workbench_projection_digest"
        ],
        "frozen_consumer_probe": frozen_probe,
        "frozen_consumer_probe_digest": frozen_probe[
            "frozen_consumer_probe_digest"
        ],
        "artifact_refs": artifact_refs,
    }
    body = {
        "schema_version": VS1_RESULT_SCHEMA_VERSION,
        "status": "vs1_current_digital_native_vertical_integrated",
        "recorded_at": RECORDED_AT,
        "slice_id": "FIN-0.1.3-S1-VS1-DELL-PRICING-MIX-V1.0",
        "scope": {
            "case_keys": ["DELL"],
            "source_shapes": [
                "official_sec_html",
                "official_hosted_text_pdf_transcript",
                "legacy_immutable_financial_objects",
                "point_in_time_market_snapshot",
            ],
            "network_calls": 0,
            "model_calls": 0,
            "index_rebuilds": 0,
            "new_evidence_promotions": 0,
            "capture_bound_reviewed_promotion_replayed": True,
        },
        "payloads": _inline_payloads(
            source_manifest=source_manifest,
            object_store_result=object_store_result,
            request_result=request_result,
            source_bindings=source_bindings,
            ledger=ledger,
            coverage=coverage,
            readiness=readiness,
            workbench=workbench,
            frozen_probe=frozen_probe,
        ),
        "cases": {"DELL": case_payload},
        "envelopes": [row.model_dump(mode="json") for row in envelopes],
        "stage_acceptance": {
            "component_engineering_pass": True,
            "vertical_slice_integrated": True,
            "S1_qualified_stable": False,
            "complete_product_chain_authorized": False,
        },
        "known_boundary": (
            "VS1 integrates one current DELL digital-native source-to-Workbench "
            "vertical. Existing capture-bound reviewed Evidence is replayed, not "
            "newly promoted. OCR, complex tables, multi-route ranking qualification, "
            "second-round supplementation, hidden holdout and full S1 qualification "
            "remain later slices."
        ),
    }
    result = {**body, "result_digest": canonical_json_digest(body)}
    load_s1_vs1_vertical_slice_result(result, policy=policy)
    return result


def _render_json(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )


def _write_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(_render_json(payload))
    temporary.replace(path)


def _update_runtime_registry(result_path: Path) -> None:
    registry_path = _resolve(DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF)
    registry = _read_json(registry_path)
    registry["registry_id"] = (
        "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R16"
    )
    result_bytes = result_path.read_bytes()
    result_row = {
        "resource_id": CURRENT_VS1_RESOURCE_ID,
        "repo_relative_path": _repo_ref(result_path),
        "sha256": hashlib.sha256(result_bytes).hexdigest(),
        "bytes": len(result_bytes),
        "classification": "digest_bound_read_only_s1_vertical_slice_result",
        "consumer_ids": [
            "apps.workbench.research_evidence_pack_service.ResearchEvidencePackService.from_runtime_paths",
            "apps.workbench.research_retrieval_service.ResearchRetrievalService.from_runtime_paths"
        ],
        "load_phase": "workbench_startup",
        "required": True,
        "source_owner": "S1_canonical_vertical_slice_program",
    }
    policy_path = _resolve(CURRENT_SPINE_POLICY_REF)
    policy_bytes = policy_path.read_bytes()
    policy_row = {
        "resource_id": "application.config.current_s1_artifact_spine_policy",
        "repo_relative_path": _repo_ref(policy_path),
        "sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "bytes": len(policy_bytes),
        "classification": "provider_neutral_s1_canonical_artifact_spine_policy",
        "consumer_ids": [
            "apps.workbench.research_evidence_pack_service.ResearchEvidencePackService.from_runtime_paths",
            "apps.workbench.research_retrieval_service.ResearchRetrievalService.from_runtime_paths",
            "scripts.data_retrieval.materialize_s1_vs1_vertical_slice.compile_result",
        ],
        "load_phase": "workbench_startup",
        "required": True,
        "source_owner": "S1_canonical_artifact_spine_program",
    }
    updated_ids = {
        CURRENT_VS1_RESOURCE_ID,
        policy_row["resource_id"],
    }
    resources = [
        deepcopy(dict(item))
        for item in registry["resources"]
        if item.get("resource_id") not in updated_ids
    ]
    resources.extend((policy_row, result_row))
    resources.sort(key=lambda item: str(item["resource_id"]))
    registry["resources"] = resources
    registry["resource_count"] = len(resources)
    registry["resource_bytes"] = sum(int(item["bytes"]) for item in resources)
    registry["resource_canonical_digest"] = canonical_json_digest(resources)
    _write_atomic(registry_path, registry)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the deterministic FIN 0.1.3 S1 VS1 vertical."
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT_REF)
    parser.add_argument("--update-runtime-registry", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = compile_result()
    output = _resolve(args.output)
    _write_atomic(output, result)
    if args.update_runtime_registry:
        _update_runtime_registry(output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "result_digest": result["result_digest"],
                "output": _repo_ref(output),
                "stage_acceptance": result["stage_acceptance"],
                "decision_counts": result["cases"]["DELL"][
                    "candidate_decision_ledger"
                ]["decision_counts"],
                "coverage_state": result["cases"]["DELL"][
                    "coverage_state"
                ]["coverage_state"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
