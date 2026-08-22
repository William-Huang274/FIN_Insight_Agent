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
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.reviewed_public_object_compiler import (  # noqa: E402
    compile_reviewed_public_source_objects,
)
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)


DEFAULT_BASE_KERNEL = Path(
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_3.json"
)
DEFAULT_KERNEL_OUTPUT = Path(
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_4.json"
)
DEFAULT_BASE_ROUTE_POLICY = Path(
    "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_3.json"
)
DEFAULT_ROUTE_POLICY_OUTPUT = Path(
    "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_4.json"
)
DEFAULT_BASE_OBJECTS = Path(
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/"
    "v5/objects.jsonl"
)
DEFAULT_BASE_SOURCE_RECORDS = Path(
    "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
    "v2/records.jsonl"
)
DEFAULT_SOURCE_RECORDS_OUTPUT = Path(
    "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
    "v3/records.jsonl"
)
DEFAULT_PACK = Path(
    "data/workbench_private/fin_0_1_3_s1_dell_external_source_evidence/"
    "dell-r3-capture-replay/successor/pack.json"
)
DEFAULT_OUTPUT_DIR = Path(
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/v6"
)
DEFAULT_RESULT_OUTPUT = Path(
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dynamic_public_reachability_successor_result_v1_0.json"
)


PUBLIC_SLOTS = {
    "demand_volume_quality",
    "pricing_mix_value_capture",
    "capacity_inputs_execution",
    "relationship_attribution",
    "counterevidence_and_what_would_change",
}


DELL_PUBLIC_RELATED_ENTITIES = [
    {
        "ticker": "ORG::05BF3EEF551722C8",
        "legal_name": "International Data Corporation",
        "aliases": ["International Data Corporation", "IDC"],
        "relationship_direction": "industry_market_context_to_subject",
        "economic_role": "industry_market_context",
    },
    {
        "ticker": "ORG::13AAFF874F67F30C",
        "legal_name": "TrendForce",
        "aliases": ["TrendForce"],
        "relationship_direction": "industry_market_context_to_subject",
        "economic_role": "industry_market_context",
    },
    {
        "ticker": "ORG::1663EE18A9AFB7C9",
        "legal_name": "Fortune",
        "aliases": ["Fortune"],
        "relationship_direction": "trusted_analysis_context_to_subject",
        "economic_role": "trusted_analysis_context",
    },
    {
        "ticker": "ORG::397A7B207441AF01",
        "legal_name": "Server Parts Europe",
        "aliases": ["Server Parts Europe"],
        "relationship_direction": "channel_configuration_context_to_subject",
        "economic_role": "channel_configuration_context",
    },
    {
        "ticker": "ORG::8FDBEED39DAE342A",
        "legal_name": "The Next Platform",
        "aliases": ["The Next Platform"],
        "relationship_direction": "trusted_analysis_context_to_subject",
        "economic_role": "trusted_analysis_context",
    },
]


PUBLIC_FACETS = {
    "demand_volume_quality": [
        {
            "facet_id": "industry_demand_context",
            "business_question_zh": "行业机构披露的服务器需求、出货和买方投入如何约束本案需求判断？",
            "evidence_owner_scope": "related_only",
            "related_economic_roles": ["industry_market_context"],
            "required_source_roles": ["industry_market_context"],
            "exact_phrases": ["AI server shipments", "AI infrastructure spending"],
            "lexical_terms": [
                "AI server shipments",
                "AI infrastructure spending",
                "buyer commitment",
                "server market",
                "shipment growth",
            ],
        }
    ],
    "pricing_mix_value_capture": [
        {
            "facet_id": "industry_pricing_mix_context",
            "business_question_zh": "行业出货、价值量与平台组合能否为价格、数量和组合桥提供有界输入？",
            "evidence_owner_scope": "related_only",
            "related_economic_roles": ["industry_market_context"],
            "required_source_roles": ["industry_market_context"],
            "exact_phrases": ["industry value", "shipment growth", "product mix"],
            "lexical_terms": [
                "industry value",
                "shipment growth",
                "AI server mix",
                "GPU ASIC mix",
                "price volume mix",
            ],
        },
        {
            "facet_id": "channel_configuration_context",
            "business_question_zh": "公开渠道配置样本能说明哪些可售产品组合，且其边界是什么？",
            "evidence_owner_scope": "related_only",
            "related_economic_roles": ["channel_configuration_context"],
            "required_source_roles": ["channel_configuration_context"],
            "exact_phrases": ["Dell PowerEdge", "configured with"],
            "lexical_terms": [
                "Dell PowerEdge",
                "server configuration",
                "GPU memory CPU mix",
                "channel configuration",
            ],
        },
        {
            "facet_id": "trusted_value_pool_context",
            "business_question_zh": "可信媒体或产业分析提供了哪些 OEM 利润池、供应商议价和利润率机制线索？",
            "evidence_owner_scope": "related_only",
            "related_economic_roles": ["trusted_analysis_context"],
            "required_source_roles": ["trusted_analysis_context"],
            "exact_phrases": ["operating margin", "gross margin", "value pool"],
            "lexical_terms": [
                "operating margin",
                "gross margin",
                "OEM value pool",
                "supplier bargaining power",
                "AI server profitability",
            ],
        },
    ],
    "capacity_inputs_execution": [
        {
            "facet_id": "industry_supply_context",
            "business_question_zh": "行业机构披露的先进制程、封装和 HBM 供给如何约束本案供给判断？",
            "evidence_owner_scope": "related_only",
            "related_economic_roles": ["industry_market_context"],
            "required_source_roles": ["industry_market_context"],
            "exact_phrases": ["advanced packaging capacity", "HBM supply"],
            "lexical_terms": [
                "advanced process capacity",
                "advanced packaging capacity",
                "HBM supply",
                "capacity constraint",
            ],
        }
    ],
    "relationship_attribution": [
        {
            "facet_id": "industry_relationship_context",
            "business_question_zh": "行业资料能否提供需要进一步回到原始披露核验的供应链或客户关系线索？",
            "evidence_owner_scope": "related_only",
            "related_economic_roles": ["industry_market_context"],
            "required_source_roles": ["industry_market_context"],
            "exact_phrases": ["supplier", "customer", "allocation"],
            "lexical_terms": [
                "supplier",
                "customer",
                "allocation",
                "supply chain relationship",
                "named counterparty",
            ],
        }
    ],
    "counterevidence_and_what_would_change": [
        {
            "facet_id": "trusted_or_industry_counterevidence",
            "business_question_zh": "可信行业或媒体资料提供了哪些可能削弱需求、利润或供给判断的反方机制？",
            "evidence_owner_scope": "related_only",
            "related_economic_roles": [
                "industry_market_context",
                "trusted_analysis_context",
            ],
            "required_source_roles": ["bounded_counterevidence_context"],
            "exact_phrases": ["pricing pressure", "demand slowdown", "margin pressure"],
            "lexical_terms": [
                "pricing pressure",
                "demand slowdown",
                "margin pressure",
                "inventory digestion",
                "supplier value capture",
            ],
        }
    ],
}


FAMILY_BY_PUBLIC_FACET = {
    "industry_demand_context": "customer_demand_read_through",
    "industry_pricing_mix_context": "pricing_and_value_capture",
    "channel_configuration_context": "pricing_and_value_capture",
    "trusted_value_pool_context": "pricing_and_value_capture",
    "industry_supply_context": "supply_capacity_execution",
    "industry_relationship_context": "relationship_attribution",
    "trusted_or_industry_counterevidence": "counterevidence_and_risk",
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


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
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


def _successor_kernel(base: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(base))
    slots = value.get("evidence_slots")
    if not isinstance(slots, list):
        raise ValueError("successor_kernel_slots_invalid")
    seen_public_facets: set[str] = set()
    for slot in slots:
        slot_id = str(slot.get("slot_id") or "")
        if slot_id in PUBLIC_SLOTS:
            source_types = list(slot.get("source_types") or ())
            if "PUBLIC_WEB" not in source_types:
                source_types.append("PUBLIC_WEB")
            slot["source_types"] = source_types
        additions = PUBLIC_FACETS.get(slot_id, ())
        existing = {str(row.get("facet_id") or "") for row in slot.get("facets") or ()}
        for facet in additions:
            facet_id = str(facet["facet_id"])
            if facet_id in existing:
                raise ValueError(f"successor_kernel_facet_duplicate:{facet_id}")
            slot["facets"].append(deepcopy(facet))
            seen_public_facets.add(facet_id)
    if seen_public_facets != set(FAMILY_BY_PUBLIC_FACET):
        raise ValueError("successor_kernel_public_facet_incomplete")

    cases = value.get("cases")
    if not isinstance(cases, list):
        raise ValueError("successor_kernel_cases_invalid")
    dell = next((row for row in cases if row.get("case_key") == "DELL"), None)
    if not isinstance(dell, dict):
        raise ValueError("successor_kernel_dell_missing")
    existing_entities = {
        str(row.get("ticker") or "") for row in dell.get("related_entities") or ()
    }
    for entity in DELL_PUBLIC_RELATED_ENTITIES:
        if entity["ticker"] in existing_entities:
            raise ValueError(f"successor_kernel_related_duplicate:{entity['ticker']}")
        dell["related_entities"].append(deepcopy(entity))
    value["status"] = "provider_neutral_s1_retrieval_contract"
    return value


def _successor_route(
    base: Mapping[str, Any], *, kernel_ref: str, kernel_sha256: str
) -> dict[str, Any]:
    value = deepcopy(dict(base))
    value["bound_kernel"] = {"ref": kernel_ref, "sha256": kernel_sha256}
    families = value.get("query_families")
    if not isinstance(families, list):
        raise ValueError("successor_route_families_invalid")
    by_id = {str(row.get("family_id") or ""): row for row in families}
    for facet_id, family_id in FAMILY_BY_PUBLIC_FACET.items():
        family = by_id.get(family_id)
        if family is None:
            raise ValueError(f"successor_route_family_missing:{family_id}")
        facets = list(family.get("facet_ids") or ())
        if facet_id in facets:
            raise ValueError(f"successor_route_facet_duplicate:{facet_id}")
        facets.append(facet_id)
        family["facet_ids"] = facets
    return value


def materialize(
    *,
    base_kernel_path: Path,
    kernel_output_path: Path,
    base_route_policy_path: Path,
    route_policy_output_path: Path,
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

    evidence_pack = _read_json(evidence_pack_path)
    public = compile_reviewed_public_source_objects(
        evidence_pack=evidence_pack,
        route_policy=route_policy,
    )
    base_source_records = _read_jsonl(base_source_records_path)
    base_source_ids = {
        str(row.get("evidence_id") or "") for row in base_source_records
    }
    if len(base_source_ids) != len(base_source_records) or "" in base_source_ids:
        raise ValueError("successor_base_source_record_identity_invalid")
    public_source_records = [dict(row) for row in public.source_records]
    public_canonical_ids = {
        str(row.get("evidence_id") or "") for row in public_source_records
    }
    if (
        len(public_canonical_ids) != len(public_source_records)
        or "" in public_canonical_ids
        or base_source_ids.intersection(public_canonical_ids)
    ):
        raise ValueError("successor_public_source_record_identity_invalid")
    source_records = [*base_source_records, *public_source_records]
    _write_jsonl(source_records_output_path, source_records)
    base_objects = _read_jsonl(base_objects_path)
    base_ids = {str(row.get("compiled_object_id") or "") for row in base_objects}
    if len(base_ids) != len(base_objects) or "" in base_ids:
        raise ValueError("successor_base_object_identity_invalid")
    public_ids = {str(row.get("compiled_object_id") or "") for row in public.objects}
    if base_ids.intersection(public_ids):
        raise ValueError("successor_public_object_identity_collision")
    objects = [*base_objects, *(dict(row) for row in public.objects)]
    objects_path = output_dir / "objects.jsonl"
    diagnostics_path = output_dir / "diagnostics.jsonl"
    _write_jsonl(objects_path, objects)
    _write_jsonl(diagnostics_path, [dict(row) for row in public.diagnostics])

    public_source_ids = set(public.summary["source_page_record_ids"])
    indexed_public_source_ids = {
        str(
            (row["base_object_view"].get("source_lineage") or {}).get(
                "source_page_record_id"
            )
            or ""
        )
        for row in objects
        if str(row["base_object_view"].get("source_type") or "") == "PUBLIC_WEB"
    }
    if indexed_public_source_ids != public_source_ids:
        raise ValueError("successor_public_source_index_coverage_invalid")
    unsigned = {
        "schema_version": "fin_ia_s1_dynamic_public_reachability_successor_result_v1_0",
        "status": "reviewed_public_sources_compiled_into_current_candidate_successor",
        "recorded_at": "2026-08-23",
        "inputs": {
            "base_kernel_ref": _repo_ref(base_kernel_path),
            "base_kernel_sha256": _sha256(base_kernel_path),
            "base_route_policy_ref": _repo_ref(base_route_policy_path),
            "base_route_policy_sha256": _sha256(base_route_policy_path),
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
            "objects_ref": _repo_ref(objects_path),
            "objects_sha256": _sha256(objects_path),
            "source_records_ref": _repo_ref(source_records_output_path),
            "source_records_sha256": _sha256(source_records_output_path),
            "diagnostics_ref": _repo_ref(diagnostics_path),
            "diagnostics_sha256": _sha256(diagnostics_path),
        },
        "summary": {
            "base_object_count": len(base_objects),
            "public_object_count": len(public.objects),
            "successor_object_count": len(objects),
            "public_source_count": len(public_source_ids),
            "public_source_slice_count": len(
                public.summary["source_slice_record_ids"]
            ),
            "public_canonical_source_record_count": len(public_source_records),
            "base_source_record_count": len(base_source_records),
            "successor_source_record_count": len(source_records),
            "public_related_entity_count": len(DELL_PUBLIC_RELATED_ENTITIES),
            "public_facet_count": len(FAMILY_BY_PUBLIC_FACET),
            "public_source_ids": sorted(public_source_ids),
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "reviewed_relevance_labels_copied_into_candidate_index": False,
            "exact_lineage_join_required_for_evidence_reselection": True,
            "model_calls": 0,
            "network_calls": 0,
        },
        "acceptance": {
            "all_reviewed_public_sources_indexed": indexed_public_source_ids
            == public_source_ids,
            "base_objects_retained_exactly": objects[: len(base_objects)] == base_objects,
            "kernel_and_route_contracts_load": True,
            "external_owner_identity_preserved": all(
                str(row["base_object_view"].get("ticker") or "")
                in {
                    "DELL",
                    "NVDA",
                    *(row["ticker"] for row in DELL_PUBLIC_RELATED_ENTITIES),
                }
                for row in public.objects
            ),
            "all_public_page_and_slice_lineage_internalized": {
                str(value)
                for row in public.objects
                for value in row.get("lineage_source_record_ids") or ()
            }
            == public_canonical_ids,
        },
        "known_boundary": (
            "This successor makes already-reviewed, capture-bound PUBLIC_WEB source "
            "materials reachable as label-free S1 candidates. It does not promote "
            "new Evidence, grant numeric authority, prove ranking quality or authorize "
            "a natural model run. Authority is recovered only by exact lineage join "
            "against the immutable reviewed Pack."
        ),
    }
    unsigned["output_binding"] = {
        "objects_ref": unsigned["outputs"]["objects_ref"],
        "objects_sha256": unsigned["outputs"]["objects_sha256"],
        "diagnostics_ref": unsigned["outputs"]["diagnostics_ref"],
        "diagnostics_sha256": unsigned["outputs"]["diagnostics_sha256"],
    }
    unsigned["object_compilation_summary"] = {
        "source_record_count": len(source_records),
        "compiled_object_count": len(objects),
        "compiled_object_kind_counts": dict(
            sorted(
                {
                    kind: sum(1 for row in objects if row.get("object_kind") == kind)
                    for kind in {str(row.get("object_kind") or "") for row in objects}
                }.items()
            )
        ),
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-kernel", type=Path, default=DEFAULT_BASE_KERNEL)
    parser.add_argument("--kernel-output", type=Path, default=DEFAULT_KERNEL_OUTPUT)
    parser.add_argument("--base-route-policy", type=Path, default=DEFAULT_BASE_ROUTE_POLICY)
    parser.add_argument("--route-policy-output", type=Path, default=DEFAULT_ROUTE_POLICY_OUTPUT)
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
        base_objects_path=_resolve(args.base_objects),
        base_source_records_path=_resolve(args.base_source_records),
        source_records_output_path=_resolve(args.source_records_output),
        evidence_pack_path=_resolve(args.evidence_pack),
        output_dir=_resolve(args.output_dir),
    )
    result_output = _resolve(args.result_output)
    _write_json(result_output, result)
    print(result_output)
    print(result["result_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
