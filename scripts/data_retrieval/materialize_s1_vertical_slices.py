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

from ingestion.pdf_layout import (  # noqa: E402
    parse_captured_pdf_layout,
    public_pdf_layout_projection,
)
from retrieval.artifact_spine import (  # noqa: E402
    canonical_json_digest,
    load_artifact_spine_policy,
    sha256_file,
)
from retrieval.complex_pdf_vertical import (  # noqa: E402
    VS2_RESULT_RESOURCE_ID,
    VS2_RESULT_SCHEMA_VERSION,
    build_vs2_artifact_chain,
    compile_vs2_evaluation,
    compile_vs2_inline_payloads,
    validate_vs2_result,
)
from retrieval.pdf_layout_objects import compile_pdf_layout_document  # noqa: E402
from retrieval.vertical_slice import VS1_RESULT_RESOURCE_ID  # noqa: E402
from sec_agent.runtime_resource_registry import (  # noqa: E402
    DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
)


VS1_OUTPUT_REF = (
    "configs/runtime/fin_ia_0_1_3_s1_vs1_vertical_slice_result_v1_1.json"
)
VS2_OUTPUT_REF = (
    "configs/runtime/fin_ia_0_1_3_s1_vs2_complex_pdf_vertical_result_v1_1.json"
)
VS2_RESOURCE_ID = VS2_RESULT_RESOURCE_ID
SPINE_POLICY_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_canonical_artifact_spine_policy_v1_0.json"
)
KERNEL_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_2.json"
)
SOURCE_SPEC_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_vs2_ifx_complex_pdf_source_spec_v1_0.json"
)
INPUT_REF = (
    "eval_sets/fin_0_1_3_s1/inputs/train_internal/"
    "vs2_complex_pdf_inputs_v1_0.jsonl"
)
REFERENCE_REF = (
    "eval_sets/fin_0_1_3_s1/references/train_internal/"
    "vs2_complex_pdf_references_v1_0.jsonl"
)
PRIVATE_ROOT_REF = "data/workbench_private/s1_vs2_complex_pdf/v1"
RECORDED_AT = "2026-08-17"


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _repo_ref(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_mapping_required:{path.name}")
    return value


def _read_one_jsonl(path: Path) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError(f"single_jsonl_mapping_required:{path.name}")
    return rows[0]


def _render_json(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )


def _write_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(_render_json(payload))
    temporary.replace(path)


def _write_jsonl_atomic(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def compile_vs2_result() -> dict[str, Any]:
    source_spec = _read_json(_resolve(SOURCE_SPEC_REF))
    input_record = _read_one_jsonl(_resolve(INPUT_REF))
    reference_record = _read_one_jsonl(_resolve(REFERENCE_REF))
    input_case = deepcopy(dict(input_record.get("runtime_input") or {}))
    reference = deepcopy(dict(reference_record.get("expected_outcome") or {}))
    if not (
        input_record.get("example_id") == reference_record.get("example_id")
        and
        input_case["case_id"] == source_spec["case_id"] == reference["case_id"]
        and reference["reference_visibility"]
        == "evaluator_only_after_candidate_generation"
    ):
        raise ValueError("vs2_split_safe_case_binding_invalid")
    metadata_path = _resolve(str(input_case["source_metadata_ref"]))
    capture = _read_json(metadata_path)
    native = parse_captured_pdf_layout(
        capture,
        repository_root=ROOT,
        selected_page_numbers=input_case["selected_page_numbers"],
    )
    ocr_mutation = parse_captured_pdf_layout(
        capture,
        repository_root=ROOT,
        selected_page_numbers=input_case["forced_ocr_mutation_page_numbers"],
        force_ocr_page_numbers=input_case["forced_ocr_mutation_page_numbers"],
    )
    _validate_gold(native, ocr_mutation, reference)

    private_root = _resolve(PRIVATE_ROOT_REF)
    native_ref = private_root / "parsed_native_layout.json"
    ocr_ref = private_root / "parsed_ocr_mutation.json"
    _write_atomic(native_ref, native)
    _write_atomic(ocr_ref, ocr_mutation)
    parent, children, object_set = compile_pdf_layout_document(
        native,
        source_spec=source_spec,
        parsed_ref=_repo_ref(native_ref),
        parsed_sha256=sha256_file(native_ref),
    )
    parent_ref = private_root / "document_parent.json"
    children_ref = private_root / "financial_objects.jsonl"
    object_set_ref = private_root / "object_set.json"
    index_ref = private_root / "index_snapshot.json"
    _write_atomic(parent_ref, parent)
    _write_jsonl_atomic(children_ref, children)
    _write_atomic(object_set_ref, object_set)
    index_snapshot = {
        "schema_version": "fin_ia_s1_vs2_complex_pdf_index_snapshot_v1_0",
        "status": "immutable_train_internal_object_snapshot",
        "document_id": parent["document_id"],
        "object_set_digest": object_set["object_set_digest"],
        "object_count": len(children),
        "object_ids": [row["evidence_id"] for row in children],
        "candidate_is_not_evidence": True,
    }
    index_snapshot["snapshot_digest"] = canonical_json_digest(index_snapshot)
    _write_atomic(index_ref, index_snapshot)

    evaluation = compile_vs2_evaluation(
        base_kernel_payload=_read_json(_resolve(KERNEL_REF)),
        source_spec=source_spec,
        parsed=native,
        objects=children,
        object_set=object_set,
        reference=reference,
        recorded_at=RECORDED_AT,
    )
    policy = load_artifact_spine_policy(_resolve(SPINE_POLICY_REF))
    inline_prefix = f"{VS2_RESOURCE_ID}#/payloads"
    envelopes = build_vs2_artifact_chain(
        policy=policy,
        source_spec=source_spec,
        parsed=native,
        parsed_ref=_repo_ref(native_ref),
        parsed_sha256=sha256_file(native_ref),
        object_set=object_set,
        object_set_ref=_repo_ref(object_set_ref),
        object_set_sha256=sha256_file(object_set_ref),
        index_ref=_repo_ref(index_ref),
        index_sha256=sha256_file(index_ref),
        evaluation=evaluation,
        inline_payload_ref_prefix=inline_prefix,
    )
    inline_payloads = compile_vs2_inline_payloads(
        source_spec=source_spec,
        parsed=native,
        object_set=object_set,
        evaluation=evaluation,
    )
    reviewed_count = len(evaluation["reviewed_object_ids"])
    accepted_count = len(
        evaluation["coverage"]["accepted_evidence_item_digests"]
    )
    body = {
        "schema_version": VS2_RESULT_SCHEMA_VERSION,
        "status": "vs2_complex_pdf_vertical_integrated",
        "recorded_at": RECORDED_AT,
        "slice_id": "FIN-0.1.3-S1-VS2-COMPLEX-PDF-IFX-V1.0",
        "scope": {
            "development_case_id": source_spec["case_id"],
            "usage_role": "train_internal_development_only_not_product_case",
            "source_shapes": [
                "official_native_layout_annual_report",
                "complex_multi_header_table",
                "financial_table_footnote",
                "revision_or_restatement_context",
                "cross_page_table_continuation",
                "rasterized_official_page_ocr_mutation",
            ],
            "network_calls": 0,
            "model_calls": 0,
            "paid_calls": 0,
            "index_rebuilds": 0,
            "new_product_evidence_promotions": 0,
        },
        "payloads": {
            **inline_payloads,
            "source_spec": deepcopy(source_spec),
            "native_layout_public_projection": public_pdf_layout_projection(native),
            "ocr_mutation_public_projection": public_pdf_layout_projection(
                ocr_mutation
            ),
            "object_set": deepcopy(object_set),
            "index_snapshot": index_snapshot,
        },
        "evaluation": {
            "candidate_decision_ledger": evaluation["decision_ledger"],
            "coverage": evaluation["coverage"],
            "readiness": evaluation["readiness"],
            "workbench_projection": evaluation["workbench_projection"],
            "reviewed_target_count": reviewed_count,
            "reviewed_target_recalled_and_accepted_count": accepted_count,
            "reviewed_target_not_recalled_count": reviewed_count - accepted_count,
            "labels_joined_after_candidate_generation": True,
        },
        "business_result": {
            "parser_preserved_revision_context": True,
            "parser_preserved_complex_table_regions": True,
            "parser_preserved_financial_footnote": True,
            "parser_preserved_cross_page_continuation": True,
            "ocr_mutation_preserved_all_material_gold_anchors": True,
            "current_retrieval_recalled_all_reviewed_complex_objects": (
                accepted_count == reviewed_count
            ),
            "current_retrieval_failure_zh": (
                f"4 个经复核复杂文档目标只有 {accepted_count} 个进入当前前 20 候选；"
                "重述说明被召回，但分部结果总计行、脚注和跨页续表未进入。"
                "对象没有丢失，最早未闭合层已从 S1-B/C 转移到 VS3 的排序与金融角色判断。"
            ),
        },
        "envelopes": [row.model_dump(mode="json") for row in envelopes],
        "stage_acceptance": {
            "component_engineering_pass": True,
            "vertical_slice_integrated": True,
            "real_scanned_source_qualified": False,
            "S1_qualified_stable": False,
            "complete_product_chain_authorized": False,
        },
        "known_boundary": (
            "VS2 carries one real complex official annual report and one rasterized "
            "official-page OCR mutation through the shared spine to CandidateDecision, "
            "Coverage and Operations Workbench. IFX is not a product case. The result "
            "does not qualify naturally scanned sources, NumericFact, VS3 ranking, S1 "
            "or the complete financial-research product chain."
        ),
    }
    result = {**body, "result_digest": canonical_json_digest(body)}
    validate_vs2_result(result, policy=policy)
    return result


def _validate_gold(
    native: Mapping[str, Any],
    ocr_mutation: Mapping[str, Any],
    reference: Mapping[str, Any],
) -> None:
    quality = native["quality_receipt"]
    if not (
        native["page_count"] == reference["expected_page_count"]
        and native["selected_page_numbers"]
        == reference["expected_selected_page_numbers"]
        and quality["table_region_count"]
        == reference["expected_native_table_region_count"]
        and quality["footnote_count"]
        == reference["expected_native_footnote_count"]
    ):
        raise ValueError("vs2_native_layout_gold_mismatch")
    text = "\n".join(str(page["text"]) for page in ocr_mutation["pages"])
    missing = [
        anchor
        for anchor in reference["expected_ocr_anchors"]
        if anchor not in text
    ]
    if missing or not (
        ocr_mutation["quality_receipt"]["forced_ocr_pages"]
        == [166]
        and ocr_mutation["quality_receipt"][
            "accepted_evidence_authority_granted"
        ]
        is False
        and ocr_mutation["quality_receipt"]["numeric_fact_authority_granted"]
        is False
    ):
        raise ValueError(f"vs2_ocr_mutation_gold_mismatch:{missing}")


def _update_runtime_registry(vs1_path: Path, vs2_path: Path) -> None:
    registry_path = _resolve(DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF)
    registry = _read_json(registry_path)
    registry["registry_id"] = (
        "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R16"
    )
    policy_resource_id = "application.config.current_s1_artifact_spine_policy"
    rows = [
        deepcopy(dict(row))
        for row in registry["resources"]
        if row.get("resource_id")
        not in {VS1_RESULT_RESOURCE_ID, VS2_RESOURCE_ID}
    ]
    for row in rows:
        if row.get("resource_id") == policy_resource_id:
            consumers = set(row.get("consumer_ids") or ())
            consumers.add(
                "scripts.data_retrieval.materialize_s1_vertical_slices.compile_vs2_result"
            )
            row["consumer_ids"] = sorted(consumers)
    for resource_id, result_path, classification, consumers, load_phase in (
        (
            VS1_RESULT_RESOURCE_ID,
            vs1_path,
            "digest_bound_read_only_s1_vertical_slice_result",
            [
                "apps.workbench.research_evidence_pack_service.ResearchEvidencePackService.from_runtime_paths",
                "apps.workbench.research_retrieval_service.ResearchRetrievalService.from_runtime_paths",
            ],
            "workbench_startup",
        ),
        (
            VS2_RESOURCE_ID,
            vs2_path,
            "digest_bound_read_only_s1_complex_document_vertical_result",
            [
                "apps.workbench.backend.api.operations.get_s1_complex_document_quality"
            ],
            "operations_request",
        ),
    ):
        payload = result_path.read_bytes()
        rows.append(
            {
                "resource_id": resource_id,
                "repo_relative_path": _repo_ref(result_path),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "classification": classification,
                "consumer_ids": consumers,
                "load_phase": load_phase,
                "required": True,
                "source_owner": "S1_canonical_vertical_slice_program",
            }
        )
    rows.sort(key=lambda row: str(row["resource_id"]))
    registry["resources"] = rows
    registry["resource_count"] = len(rows)
    registry["resource_bytes"] = sum(int(row["bytes"]) for row in rows)
    registry["resource_canonical_digest"] = canonical_json_digest(rows)
    _write_atomic(registry_path, registry)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the canonical FIN 0.1.3 S1 vertical slices."
    )
    parser.add_argument("--slice", choices=("vs1", "vs2", "all"), default="vs2")
    parser.add_argument("--update-runtime-registry", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary: dict[str, Any] = {}
    if args.slice in {"vs1", "all"}:
        from scripts.data_retrieval.materialize_s1_vs1_vertical_slice import (
            compile_result as compile_vs1_result,
        )

        vs1 = compile_vs1_result()
        _write_atomic(_resolve(VS1_OUTPUT_REF), vs1)
        summary["vs1"] = {
            "status": vs1["status"],
            "result_digest": vs1["result_digest"],
        }
    if args.slice in {"vs2", "all"}:
        vs2 = compile_vs2_result()
        output = _resolve(VS2_OUTPUT_REF)
        _write_atomic(output, vs2)
        summary["vs2"] = {
            "status": vs2["status"],
            "result_digest": vs2["result_digest"],
            "stage_acceptance": vs2["stage_acceptance"],
            "business_result": vs2["business_result"],
        }
    if args.update_runtime_registry:
        _update_runtime_registry(
            _resolve(VS1_OUTPUT_REF),
            _resolve(VS2_OUTPUT_REF),
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
