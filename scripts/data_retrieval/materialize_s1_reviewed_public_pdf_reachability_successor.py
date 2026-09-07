from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.contracts import (  # noqa: E402
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.reviewed_public_object_compiler import (  # noqa: E402
    compile_reviewed_public_source_objects,
)
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)


DEFAULT_BASE_KERNEL = Path(
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_4.json"
)
DEFAULT_KERNEL_OUTPUT = Path(
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_5.json"
)
DEFAULT_BASE_ROUTE_POLICY = Path(
    "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_4.json"
)
DEFAULT_ROUTE_POLICY_OUTPUT = Path(
    "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_5.json"
)
DEFAULT_BASE_PROGRAM = Path(
    "configs/retrieval/fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_2.json"
)
DEFAULT_PROGRAM_OUTPUT = Path(
    "configs/retrieval/fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_3.json"
)
DEFAULT_BASE_OBJECTS = Path(
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/"
    "v6/objects.jsonl"
)
DEFAULT_BASE_SOURCE_RECORDS = Path(
    "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
    "v3/records.jsonl"
)
DEFAULT_SOURCE_RECORDS_OUTPUT = Path(
    "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
    "v4/records.jsonl"
)
DEFAULT_PACK = Path(
    "data/workbench_private/fin_0_1_3_s1_dell_direct_source_evidence/"
    "r4/successor/pack.json"
)
DEFAULT_OUTPUT_DIR = Path(
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/v7"
)
DEFAULT_RESULT_OUTPUT = Path(
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_reviewed_public_pdf_reachability_successor_result_v1_0.json"
)


PDF_RELATED_ENTITIES = (
    {
        "ticker": "ORG::E1BF978301A42974",
        "legal_name": "Principled Technologies, Inc.",
        "aliases": ["Principled Technologies", "Principled Technologies, Inc."],
        "relationship_direction": "technical_study_context_to_subject",
        "economic_role": "channel_configuration_context",
    },
    {
        "ticker": "ORG::88D1082A31CB2777",
        "legal_name": "Mississippi Institutions of Higher Learning",
        "aliases": [
            "Mississippi Institutions of Higher Learning",
            "Mississippi IHL",
        ],
        "relationship_direction": "public_procurement_context_to_subject",
        "economic_role": "customer_demand_context",
    },
)


PDF_FACETS = {
    "demand_volume_quality": (
        {
            "facet_id": "bounded_unit_volume_context",
            "business_question_zh": (
                "公司披露与公开采购文件能提供哪些数量观察，且为何项目样本不能外推为公司销量或份额？"
            ),
            "evidence_owner_scope": "subject_and_related",
            "related_economic_roles": ["customer_demand_context"],
            "required_source_roles": ["issuer_or_bounded_customer_demand_context"],
            "exact_phrases": ["AI server", "PowerEdge XE9680"],
            "lexical_terms": [
                "AI server orders",
                "AI server backlog",
                "AI server units",
                "public procurement",
                "PowerEdge XE9680",
                "systems",
                "units",
                "purchase contract",
            ],
        },
    ),
    "pricing_mix_value_capture": (
        {
            "facet_id": "bounded_price_configuration_context",
            "business_question_zh": (
                "公司披露、技术研究与公开采购能提供哪些价格、配置和组合观察，且其边界是什么？"
            ),
            "evidence_owner_scope": "subject_and_related",
            "related_economic_roles": [
                "channel_configuration_context",
                "customer_demand_context"
            ],
            "required_source_roles": ["issuer_or_bounded_price_configuration_context"],
            "exact_phrases": ["Dell recommended price", "PowerEdge XE9680"],
            "lexical_terms": [
                "AI server revenue",
                "average selling price",
                "product mix",
                "Dell recommended price",
                "public procurement",
                "contract value",
                "PowerEdge XE9680",
                "bundled services",
                "configuration",
            ],
        },
    ),
    "relationship_attribution": (
        {
            "facet_id": "current_platform_relationship_context",
            "business_question_zh": (
                "研究主体或注册供应商当前材料是否直接点名对方并披露合作、交付或可用状态？"
            ),
            "evidence_owner_scope": "subject_and_related",
            "related_economic_roles": ["supplier_capacity_context"],
            "required_source_roles": ["issuer_or_registered_supplier_direct_mention"],
            "exact_phrases": ["Dell AI Factory with NVIDIA", "available"],
            "lexical_terms": [
                "Dell AI Factory with NVIDIA",
                "collaboration",
                "partnership",
                "available",
                "PowerEdge",
            ],
        },
    ),
}


FAMILY_BY_PDF_FACET = {
    "bounded_unit_volume_context": "customer_demand_read_through",
    "bounded_price_configuration_context": "pricing_and_value_capture",
    "current_platform_relationship_context": "relationship_attribution",
}


REQUEST_SUCCESSORS = {
    "REQ::DELL::PRICE_CONFIGURATION::V1": {
        "facets": ("bounded_price_configuration_context",),
        "targets": (
            "ORG::E1BF978301A42974",
            "ORG::88D1082A31CB2777",
        ),
        "product_intents": (),
    },
    "REQ::DELL::PVM_BRIDGE::V1": {
        "facets": ("bounded_price_configuration_context",),
        "targets": (
            "ORG::E1BF978301A42974",
            "ORG::88D1082A31CB2777",
        ),
        "product_intents": (),
    },
    "REQ::DELL::UNIT_VOLUME::V1": {
        "facets": ("bounded_unit_volume_context",),
        "targets": ("ORG::88D1082A31CB2777",),
        "product_intents": (),
    },
    "REQ::DELL::SUPPLY_RELATIONSHIP::V1": {
        "facets": ("current_platform_relationship_context",),
        "targets": (),
        "product_intents": ("Dell NVIDIA partnership and product availability",),
    },
}


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"jsonl_object_required:{path}:{line_number}")
            rows.append(value)
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _repo_ref(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _count_by(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _successor_kernel(base: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(base))
    slots = value.get("evidence_slots")
    if not isinstance(slots, list):
        raise ValueError("pdf_successor_kernel_slots_invalid")
    added_facets: set[str] = set()
    for slot in slots:
        slot_id = str(slot.get("slot_id") or "")
        additions = PDF_FACETS.get(slot_id, ())
        if additions:
            source_types = list(slot.get("source_types") or ())
            if "PUBLIC_PDF" not in source_types:
                source_types.append("PUBLIC_PDF")
            slot["source_types"] = source_types
        existing = {str(row.get("facet_id") or "") for row in slot.get("facets") or ()}
        for facet in additions:
            facet_id = str(facet["facet_id"])
            if facet_id in existing:
                raise ValueError(f"pdf_successor_kernel_facet_duplicate:{facet_id}")
            slot["facets"].append(deepcopy(facet))
            added_facets.add(facet_id)
    if added_facets != set(FAMILY_BY_PDF_FACET):
        raise ValueError("pdf_successor_kernel_facet_incomplete")

    cases = value.get("cases")
    if not isinstance(cases, list):
        raise ValueError("pdf_successor_kernel_cases_invalid")
    dell = next((row for row in cases if row.get("case_key") == "DELL"), None)
    if not isinstance(dell, dict):
        raise ValueError("pdf_successor_kernel_dell_missing")
    existing_entities = {
        str(row.get("ticker") or "") for row in dell.get("related_entities") or ()
    }
    for entity in PDF_RELATED_ENTITIES:
        if entity["ticker"] in existing_entities:
            raise ValueError(
                f"pdf_successor_kernel_related_duplicate:{entity['ticker']}"
            )
        dell["related_entities"].append(deepcopy(entity))
    return value


def _successor_route(
    base: Mapping[str, Any], *, kernel_ref: str, kernel_sha256: str
) -> dict[str, Any]:
    value = deepcopy(dict(base))
    value["bound_kernel"] = {"ref": kernel_ref, "sha256": kernel_sha256}
    families = value.get("query_families")
    if not isinstance(families, list):
        raise ValueError("pdf_successor_route_families_invalid")
    by_id = {str(row.get("family_id") or ""): row for row in families}
    for facet_id, family_id in FAMILY_BY_PDF_FACET.items():
        family = by_id.get(family_id)
        if family is None:
            raise ValueError(f"pdf_successor_route_family_missing:{family_id}")
        facets = list(family.get("facet_ids") or ())
        if facet_id in facets:
            raise ValueError(f"pdf_successor_route_facet_duplicate:{facet_id}")
        facets.append(facet_id)
        family["facet_ids"] = facets
    value["status"] = "provider_neutral_successor_policy_no_model_or_evidence_authority"
    return value


def _successor_program(
    base: Mapping[str, Any], *, kernel: Any
) -> dict[str, Any]:
    value = deepcopy(dict(base))
    requests = value.get("evidence_requests")
    if not isinstance(requests, list):
        raise ValueError("pdf_successor_program_requests_invalid")
    changed: set[str] = set()
    for request in requests:
        request_id = str(request.get("request_id") or "")
        successor = REQUEST_SUCCESSORS.get(request_id)
        if successor is None:
            load_evidence_request(request, kernel)
            continue
        sources = list(request.get("acceptable_sources") or ())
        if "PUBLIC_PDF" not in sources:
            sources.append("PUBLIC_PDF")
        request["acceptable_sources"] = sources
        request["requested_facet_ids"] = list(successor["facets"])
        targets = list(request.get("target_entities") or ())
        for target in successor["targets"]:
            if target not in targets:
                targets.append(target)
        request["target_entities"] = targets
        product_intents = list(request.get("product_intents") or ())
        for product_intent in successor["product_intents"]:
            if product_intent not in product_intents:
                product_intents.append(product_intent)
        request["product_intents"] = product_intents
        load_evidence_request(request, kernel)
        changed.add(request_id)
    if changed != set(REQUEST_SUCCESSORS):
        raise ValueError("pdf_successor_program_request_coverage_invalid")
    value["program_id"] = "FIN-0.1.3-S1-DELL-PROPOSITION-COVERAGE-R4-PDF-RECALL"
    value["status"] = (
        "approved_ai_free_stage_owned_vertical_execution_program_with_reviewed_public_pdf_recall"
    )
    value["predecessor"] = {
        "program_id": str(base.get("program_id") or ""),
        "ref": _repo_ref(DEFAULT_BASE_PROGRAM),
        "sha256": _sha256(_resolve(DEFAULT_BASE_PROGRAM)),
    }
    value["successor_change"] = {
        "owned_defect": "reviewed_public_pdf_absent_from_current_compiled_object_and_index_runtime",
        "reviewed_public_pdf_enabled_request_ids": sorted(changed),
        "reviewed_public_pdf_target_entities": sorted(
            entity["ticker"] for entity in PDF_RELATED_ENTITIES
        ),
        "candidate_is_not_evidence": True,
        "numeric_authority": False,
        "public_procurement_unit_is_not_company_units_or_share": True,
        "bundled_quote_or_contract_is_not_company_asp": True,
        "issuer_relationship_pdf_does_not_prove_private_allocation": True,
        "public_information_gap_authority": False,
    }
    return value


def materialize(
    *,
    base_kernel_path: Path,
    kernel_output_path: Path,
    base_route_policy_path: Path,
    route_policy_output_path: Path,
    base_program_path: Path,
    program_output_path: Path,
    base_objects_path: Path,
    base_source_records_path: Path,
    source_records_output_path: Path,
    evidence_pack_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    kernel_payload = _successor_kernel(_read_json(base_kernel_path))
    _write_json(kernel_output_path, kernel_payload)
    kernel_sha256 = _sha256(kernel_output_path)
    kernel = load_financial_research_kernel(kernel_payload)

    route_payload = _successor_route(
        _read_json(base_route_policy_path),
        kernel_ref=_repo_ref(kernel_output_path),
        kernel_sha256=kernel_sha256,
    )
    _write_json(route_policy_output_path, route_payload)
    route_policy = load_query_object_fact_route_policy(route_payload, kernel)

    program_payload = _successor_program(
        _read_json(base_program_path),
        kernel=kernel,
    )
    _write_json(program_output_path, program_payload)

    evidence_pack = _read_json(evidence_pack_path)
    public_pdf = compile_reviewed_public_source_objects(
        evidence_pack=evidence_pack,
        route_policy=route_policy,
        allowed_source_types=("PUBLIC_PDF",),
    )
    if public_pdf.summary.get("allowed_source_types") != ["PUBLIC_PDF"]:
        raise ValueError("pdf_successor_compiler_source_scope_invalid")

    base_source_records = _read_jsonl(base_source_records_path)
    base_source_ids = [str(row.get("evidence_id") or "") for row in base_source_records]
    pdf_source_records = [dict(row) for row in public_pdf.source_records]
    pdf_source_ids = [str(row.get("evidence_id") or "") for row in pdf_source_records]
    if (
        not all(base_source_ids)
        or len(base_source_ids) != len(set(base_source_ids))
        or not all(pdf_source_ids)
        or len(pdf_source_ids) != len(set(pdf_source_ids))
        or set(base_source_ids).intersection(pdf_source_ids)
    ):
        raise ValueError("pdf_successor_source_record_identity_invalid")
    source_records = [*base_source_records, *pdf_source_records]
    _write_jsonl(source_records_output_path, source_records)

    base_objects = _read_jsonl(base_objects_path)
    base_object_ids = [str(row.get("compiled_object_id") or "") for row in base_objects]
    pdf_objects = [dict(row) for row in public_pdf.objects]
    pdf_object_ids = [str(row.get("compiled_object_id") or "") for row in pdf_objects]
    if (
        not all(base_object_ids)
        or len(base_object_ids) != len(set(base_object_ids))
        or not all(pdf_object_ids)
        or len(pdf_object_ids) != len(set(pdf_object_ids))
        or set(base_object_ids).intersection(pdf_object_ids)
        or any(
            str(row.get("base_object_view", {}).get("source_type") or "")
            != "PUBLIC_PDF"
            for row in pdf_objects
        )
    ):
        raise ValueError("pdf_successor_compiled_object_identity_invalid")
    objects = [*base_objects, *pdf_objects]
    objects_path = output_dir / "objects.jsonl"
    diagnostics_path = output_dir / "diagnostics.jsonl"
    _write_jsonl(objects_path, objects)
    _write_jsonl(
        diagnostics_path,
        [dict(row) for row in public_pdf.diagnostics],
    )

    expected_page_ids = set(public_pdf.summary["source_page_record_ids"])
    indexed_page_ids = {
        str(
            (row["base_object_view"].get("source_lineage") or {}).get(
                "source_page_record_id"
            )
            or ""
        )
        for row in pdf_objects
    }
    if indexed_page_ids != expected_page_ids:
        raise ValueError("pdf_successor_page_index_coverage_invalid")

    kind_counts = _count_by(objects, "object_kind")
    unsigned = {
        "schema_version": "fin_ia_s1_reviewed_public_pdf_reachability_successor_result_v1_0",
        "status": "reviewed_public_pdf_compiled_into_current_candidate_successor",
        "recorded_at": "2026-08-25",
        "inputs": {
            "base_kernel_ref": _repo_ref(base_kernel_path),
            "base_kernel_sha256": _sha256(base_kernel_path),
            "base_route_policy_ref": _repo_ref(base_route_policy_path),
            "base_route_policy_sha256": _sha256(base_route_policy_path),
            "base_program_ref": _repo_ref(base_program_path),
            "base_program_sha256": _sha256(base_program_path),
            "base_objects_ref": _repo_ref(base_objects_path),
            "base_objects_sha256": _sha256(base_objects_path),
            "base_source_records_ref": _repo_ref(base_source_records_path),
            "base_source_records_sha256": _sha256(base_source_records_path),
            "evidence_pack_ref": _repo_ref(evidence_pack_path),
            "evidence_pack_sha256": _sha256(evidence_pack_path),
            "evidence_pack_payload_digest": evidence_pack.get("pack_payload_digest"),
            "records": {
                "ref": _repo_ref(source_records_output_path),
                "sha256": _sha256(source_records_output_path),
            },
        },
        "outputs": {
            "kernel_ref": _repo_ref(kernel_output_path),
            "kernel_sha256": kernel_sha256,
            "route_policy_ref": _repo_ref(route_policy_output_path),
            "route_policy_sha256": _sha256(route_policy_output_path),
            "request_program_ref": _repo_ref(program_output_path),
            "request_program_sha256": _sha256(program_output_path),
            "objects_ref": _repo_ref(objects_path),
            "objects_sha256": _sha256(objects_path),
            "source_records_ref": _repo_ref(source_records_output_path),
            "source_records_sha256": _sha256(source_records_output_path),
            "diagnostics_ref": _repo_ref(diagnostics_path),
            "diagnostics_sha256": _sha256(diagnostics_path),
        },
        "output_binding": {
            "objects_ref": _repo_ref(objects_path),
            "objects_sha256": _sha256(objects_path),
            "diagnostics_ref": _repo_ref(diagnostics_path),
            "diagnostics_sha256": _sha256(diagnostics_path),
        },
        "object_compilation_summary": {
            "source_record_count": len(source_records),
            "compiled_object_count": len(objects),
            "compiled_object_kind_counts": kind_counts,
        },
        "summary": {
            "base_source_record_count": len(base_source_records),
            "pdf_canonical_source_record_count": len(pdf_source_records),
            "successor_source_record_count": len(source_records),
            "base_object_count": len(base_objects),
            "pdf_object_count": len(pdf_objects),
            "successor_object_count": len(objects),
            "pdf_source_count": len(expected_page_ids),
            "pdf_source_slice_count": len(public_pdf.summary["source_slice_record_ids"]),
            "pdf_source_ids": sorted(expected_page_ids),
            "pdf_related_entity_count": len(PDF_RELATED_ENTITIES),
            "pdf_facet_count": len(FAMILY_BY_PDF_FACET),
            "changed_request_count": len(REQUEST_SUCCESSORS),
        },
        "acceptance": {
            "base_source_records_retained_exactly": source_records[
                : len(base_source_records)
            ]
            == base_source_records,
            "base_objects_retained_exactly": objects[: len(base_objects)] == base_objects,
            "all_reviewed_pdf_pages_and_slices_internalized": True,
            "all_reviewed_pdf_sources_indexed": True,
            "external_owner_identity_preserved": True,
            "kernel_route_and_request_contracts_load": True,
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "reviewed_relevance_labels_copied_into_candidate_index": False,
            "exact_lineage_join_required_for_evidence_reselection": True,
            "public_procurement_unit_is_not_company_units_or_share": True,
            "bundled_quote_or_contract_is_not_company_asp": True,
            "issuer_relationship_pdf_does_not_prove_private_allocation": True,
            "network_calls": 0,
            "model_calls": 0,
        },
        "known_boundary": (
            "This successor appends only six already-reviewed PUBLIC_PDF slices and "
            "their three page-lineage parents to the current S1 source/object surface. "
            "It makes those documents retrievable as label-free candidates; it does "
            "not convert a bundled quote into Dell ASP, a single procurement into "
            "company units/share, or a public collaboration into private allocation. "
            "Evidence authority still requires an exact immutable-Pack lineage join."
        ),
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Append reviewed PUBLIC_PDF page/slice lineage to the immutable current "
            "S1 source and compiled-object prefixes."
        )
    )
    parser.add_argument("--base-kernel", type=Path, default=DEFAULT_BASE_KERNEL)
    parser.add_argument("--kernel-output", type=Path, default=DEFAULT_KERNEL_OUTPUT)
    parser.add_argument(
        "--base-route-policy", type=Path, default=DEFAULT_BASE_ROUTE_POLICY
    )
    parser.add_argument(
        "--route-policy-output", type=Path, default=DEFAULT_ROUTE_POLICY_OUTPUT
    )
    parser.add_argument("--base-program", type=Path, default=DEFAULT_BASE_PROGRAM)
    parser.add_argument("--program-output", type=Path, default=DEFAULT_PROGRAM_OUTPUT)
    parser.add_argument("--base-objects", type=Path, default=DEFAULT_BASE_OBJECTS)
    parser.add_argument(
        "--base-source-records", type=Path, default=DEFAULT_BASE_SOURCE_RECORDS
    )
    parser.add_argument(
        "--source-records-output", type=Path, default=DEFAULT_SOURCE_RECORDS_OUTPUT
    )
    parser.add_argument("--evidence-pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--result-output", type=Path, default=DEFAULT_RESULT_OUTPUT)
    args = parser.parse_args()

    result = materialize(
        base_kernel_path=_resolve(args.base_kernel),
        kernel_output_path=_resolve(args.kernel_output),
        base_route_policy_path=_resolve(args.base_route_policy),
        route_policy_output_path=_resolve(args.route_policy_output),
        base_program_path=_resolve(args.base_program),
        program_output_path=_resolve(args.program_output),
        base_objects_path=_resolve(args.base_objects),
        base_source_records_path=_resolve(args.base_source_records),
        source_records_output_path=_resolve(args.source_records_output),
        evidence_pack_path=_resolve(args.evidence_pack),
        output_dir=_resolve(args.output_dir),
    )
    result_path = _resolve(args.result_output)
    _write_json(result_path, result)
    print(result_path)
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
