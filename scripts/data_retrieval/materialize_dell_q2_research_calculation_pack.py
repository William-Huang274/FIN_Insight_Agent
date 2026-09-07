from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.data_retrieval.materialize_dell_q2_reviewed_evidence_overlay import (  # noqa: E402
    PACK_STATUS,
    PROJECTION_SCHEMA,
)
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    REVIEWED_EVIDENCE_PACK_SCHEMA,
    canonical_digest,
    validate_reviewed_evidence_pack,
)


CALCULATION_PACK_SCHEMA = (
    "fin_ia_dell_fy27_q2_non_s2_research_calculation_pack_v1_0"
)
CALCULATION_MANIFEST_SCHEMA = (
    "fin_ia_dell_fy27_q2_non_s2_research_calculation_manifest_v1_0"
)
CALCULATION_AUTHORITY_MODE = (
    "deterministic_derivation_from_non_s2_source_observations"
)
SOURCE_OBSERVATION_AUTHORITY_MODE = (
    "issuer_disclosed_unaudited_sec_exhibit_source_visible_observation_"
    "not_s2_numeric_fact"
)
REQUIRED_SHORT_CAVEAT = (
    "非 S2 NumericFact；由发行人未审计 SEC Exhibit 的已审核文字值确定性计算。"
)

_EXPECTED_URL = (
    "https://www.sec.gov/Archives/edgar/data/1571996/"
    "000157199626000039/exhibit991earnings8kq2fy27.htm"
)
_EXPECTED_ACCESSION = "0001571996-26-000039"
_EXPECTED_DOCUMENT = "exhibit991earnings8kq2fy27.htm"
_EXPECTED_PERIOD_END = "2026-07-31"
_EXPECTED_PUBLICATION_DATE = "2026-09-01"
_EXPECTED_PROPOSITIONS = {
    "CURRENT_EVENT",
    "AI_ORDER_REVENUE_BACKLOG",
    "COMPANY_SUMMARY",
    "ISG_SEGMENT",
    "CSG_SEGMENT",
    "FY27_GUIDANCE",
}
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ATTEMPT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+\-]{2,119}")


class DellQ2ResearchCalculationError(ValueError):
    """A reviewed-source calculation crossed a case or authority boundary."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellQ2ResearchCalculationError(code)


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decimal_string(value: Decimal) -> str:
    with localcontext() as context:
        context.prec = 36
        rendered = format(value.normalize(), "f")
    return "0" if rendered in {"", "-0"} else rendered


def _parse_source_value(surface: str, code: str) -> Decimal:
    normalized = (
        surface.replace("$", "")
        .replace(",", "")
        .replace("billion", "")
        .strip()
    )
    try:
        value = Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise DellQ2ResearchCalculationError(code) from exc
    _require(value.is_finite() and value >= 0, code)
    return value


def _evidence_id(item: Mapping[str, Any]) -> str:
    return "EV::" + canonical_digest(
        {
            "case_key": "DELL",
            "target_id": item.get("target_id"),
            "evidence_item_digest": item.get("evidence_item_digest"),
        }
    )[:16].upper()


def _validate_evidence_item_digest(item: Mapping[str, Any]) -> None:
    body = deepcopy(dict(item))
    body.pop("source", None)
    digest = str(body.pop("evidence_item_digest", ""))
    _require(
        bool(digest) and digest == canonical_digest(body),
        "research_calculation_evidence_item_digest_invalid",
    )


def _normalize_projection(value: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
    body = deepcopy(dict(value))
    projection_digest = str(body.pop("projection_digest", ""))
    authority = body.get("authority")
    items = body.get("evidence_items")
    _require(
        body.get("schema_version") == PROJECTION_SCHEMA
        and body.get("status") == "case_only_reviewed_evidence_projection_ready"
        and body.get("case_key") == "DELL"
        and projection_digest == canonical_digest(body)
        and isinstance(authority, Mapping)
        and authority.get("reviewed_evidence") is True
        and authority.get("s2_numeric_fact_authority") is False
        and authority.get("product_pack_mutation_authorized") is False
        and isinstance(items, list)
        and bool(items),
        "research_calculation_projection_input_invalid",
    )
    normalized: list[dict[str, Any]] = []
    for raw_item in items:
        _require(
            isinstance(raw_item, Mapping) and isinstance(raw_item.get("source"), Mapping),
            "research_calculation_projection_item_invalid",
        )
        item = deepcopy(dict(raw_item))
        source = deepcopy(dict(item["source"]))
        source["source_text"] = str(source.pop("reviewed_source_excerpt", ""))
        item["source"] = source
        _validate_evidence_item_digest(item)
        normalized.append(item)
    return normalized, projection_digest


def _normalize_pack(value: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
    try:
        validate_reviewed_evidence_pack(value)
    except ValueError as exc:
        raise DellQ2ResearchCalculationError(
            "research_calculation_reviewed_pack_invalid"
        ) from exc
    materials = {
        str(row.get("material_ref") or ""): deepcopy(dict(row))
        for row in value.get("source_materials") or ()
        if isinstance(row, Mapping)
    }
    items: list[dict[str, Any]] = []
    for raw_item in value.get("evidence_items") or ():
        _require(
            isinstance(raw_item, Mapping),
            "research_calculation_reviewed_pack_item_invalid",
        )
        item = deepcopy(dict(raw_item))
        material_ref = str(item.get("source_material_ref") or "")
        _require(
            material_ref in materials,
            "research_calculation_source_material_missing",
        )
        item["source"] = materials[material_ref]
        _validate_evidence_item_digest(item)
        items.append(item)
    return items, str(value.get("pack_payload_digest") or "")


def _load_reviewed_input(
    input_path: Path,
    expected_input_sha256: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _require(
        _SHA256.fullmatch(expected_input_sha256) is not None,
        "research_calculation_expected_input_sha256_invalid",
    )
    raw = input_path.read_bytes()
    file_sha256 = _sha256_bytes(raw)
    _require(
        file_sha256 == expected_input_sha256,
        "research_calculation_input_file_sha256_mismatch",
    )
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DellQ2ResearchCalculationError(
            "research_calculation_input_json_invalid"
        ) from exc
    _require(
        isinstance(value, Mapping),
        "research_calculation_input_not_object",
    )
    if value.get("schema_version") == PROJECTION_SCHEMA:
        items, payload_digest = _normalize_projection(value)
        input_kind = "reviewed_evidence_case_projection"
    elif value.get("schema_version") == REVIEWED_EVIDENCE_PACK_SCHEMA:
        _require(
            value.get("status") == PACK_STATUS and value.get("case_key") == "DELL",
            "research_calculation_reviewed_pack_scope_invalid",
        )
        items, payload_digest = _normalize_pack(value)
        input_kind = "reviewed_evidence_pack"
    else:
        raise DellQ2ResearchCalculationError(
            "research_calculation_input_schema_unsupported"
        )
    return items, {
        "input_kind": input_kind,
        "input_schema_version": str(value.get("schema_version") or ""),
        "input_status": str(value.get("status") or ""),
        "input_payload_digest": payload_digest,
        "input_file_sha256": file_sha256,
    }


def _validate_and_index_items(
    items: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], str]:
    propositions = [str(item.get("proposition_id") or "") for item in items]
    _require(
        len(propositions) == len(set(propositions))
        and set(propositions) == _EXPECTED_PROPOSITIONS,
        "research_calculation_q2_proposition_set_invalid",
    )
    indexed: dict[str, dict[str, Any]] = {}
    research_dates: set[str] = set()
    raw_digests: set[str] = set()
    parsed_digests: set[str] = set()
    for item in items:
        source = dict(item.get("source") or {})
        source_identity = dict(source.get("source_identity") or {})
        locator = dict(source.get("source_locator") or {})
        excerpt = str(source.get("source_text") or "")
        excerpt_digest = _sha256_bytes(excerpt.encode("utf-8"))
        raw_digest = str(source_identity.get("raw_body_sha256") or "")
        parsed_digest = str(source_identity.get("parsed_search_text_sha256") or "")
        _require(
            item.get("case_key") == "DELL"
            and item.get("writer_citable") is True
            and item.get("causal_attribution_authorized") is False
            and item.get("target_company_exact_numeric_authority")
            == "source_visible_quote_only_not_s2_numeric_fact"
            and str(item.get("source_material_ref") or "")
            == str(source.get("material_ref") or "")
            and str(item.get("source_record_id") or "")
            == str(source.get("source_record_id") or "")
            and str(item.get("source_content_digest") or "") == excerpt_digest
            and str(source.get("source_text_digest") or "") == excerpt_digest
            and str(locator.get("quote_sha256") or "") == excerpt_digest
            and source.get("source_url") == _EXPECTED_URL
            and source.get("period_end") == _EXPECTED_PERIOD_END
            and item.get("source_reporting_period_end") == _EXPECTED_PERIOD_END
            and source.get("publication_date") == _EXPECTED_PUBLICATION_DATE
            and item.get("publication_date") == _EXPECTED_PUBLICATION_DATE
            and source.get("source_tier")
            == "company_authored_unaudited_sec_filing"
            and source.get("evidence_owner_ticker") == "DELL"
            and source_identity.get("accession_number") == _EXPECTED_ACCESSION
            and source_identity.get("exhibit_document") == _EXPECTED_DOCUMENT
            and _SHA256.fullmatch(raw_digest) is not None
            and _SHA256.fullmatch(parsed_digest) is not None
            and locator.get("raw_body_sha256") == raw_digest
            and locator.get("parsed_search_text_sha256") == parsed_digest
            and int(locator.get("char_end") or 0) > int(locator.get("char_start") or -1),
            "research_calculation_reviewed_source_binding_invalid",
        )
        research_as_of = str(item.get("research_as_of") or "")
        _require(
            research_as_of >= _EXPECTED_PUBLICATION_DATE,
            "research_calculation_research_as_of_invalid",
        )
        research_dates.add(research_as_of)
        raw_digests.add(raw_digest)
        parsed_digests.add(parsed_digest)
        indexed[str(item["proposition_id"])] = item
    _require(
        len(research_dates) == 1
        and len(raw_digests) == 1
        and len(parsed_digests) == 1,
        "research_calculation_cross_item_source_identity_invalid",
    )
    return indexed, next(iter(research_dates))


_OBSERVATION_SPECS: tuple[dict[str, str], ...] = (
    {
        "observation_id": "dell_ai_server_orders_q2_fy27",
        "proposition_id": "AI_ORDER_REVENUE_BACKLOG",
        "pattern": r"booked a record (?P<surface>\$\s*[0-9][0-9,.]*\s+billion) in orders",
        "unit": "USD_billions",
        "period_label": "FY27 Q2",
        "period_role": "quarter_order_flow",
    },
    {
        "observation_id": "dell_ai_server_backlog_q2_fy27",
        "proposition_id": "AI_ORDER_REVENUE_BACKLOG",
        "pattern": r"record (?P<surface>\$\s*[0-9][0-9,.]*\s+billion) backlog",
        "unit": "USD_billions",
        "period_label": "FY27 Q2 quarter end",
        "period_role": "quarter_end_backlog_stock",
    },
    {
        "observation_id": "dell_company_revenue_q2_fy27",
        "proposition_id": "COMPANY_SUMMARY",
        "pattern": r"Record revenue of (?P<surface>\$\s*[0-9][0-9,.]*\s+billion)",
        "unit": "USD_billions",
        "period_label": "FY27 Q2",
        "period_role": "quarter_revenue_flow",
    },
    {
        "observation_id": "dell_isg_revenue_q2_fy27",
        "proposition_id": "ISG_SEGMENT",
        "pattern": r"Record revenue:\s*(?P<surface>\$\s*[0-9][0-9,.]*\s+billion)",
        "unit": "USD_billions",
        "period_label": "FY27 Q2",
        "period_role": "quarter_revenue_flow",
    },
    {
        "observation_id": "dell_ai_server_revenue_q2_fy27",
        "proposition_id": "ISG_SEGMENT",
        "pattern": (
            r"Record AI-Optimized Servers revenue:\s*"
            r"(?P<surface>\$\s*[0-9][0-9,.]*\s+billion)"
        ),
        "unit": "USD_billions",
        "period_label": "FY27 Q2",
        "period_role": "quarter_revenue_flow",
    },
    {
        "observation_id": "dell_isg_operating_income_q2_fy27",
        "proposition_id": "ISG_SEGMENT",
        "pattern": r"Record operating income:\s*(?P<surface>\$\s*[0-9][0-9,.]*\s+billion)",
        "unit": "USD_billions",
        "period_label": "FY27 Q2",
        "period_role": "quarter_operating_income_flow",
    },
    {
        "observation_id": "dell_company_revenue_guidance_previous_fy27",
        "proposition_id": "FY27_GUIDANCE",
        "pattern": r"Full-Year Guidance.*?\bRevenue\s+(?P<surface>\$\s*[0-9][0-9,.]*)\s+\$",
        "unit": "source_presented_usd_guidance_scale",
        "period_label": "FY27 full-year guidance",
        "period_role": "previous_management_guidance",
    },
    {
        "observation_id": "dell_company_revenue_guidance_updated_fy27",
        "proposition_id": "FY27_GUIDANCE",
        "pattern": (
            r"Full-Year Guidance.*?\bRevenue\s+\$\s*[0-9][0-9,.]*\s+"
            r"(?P<surface>\$\s*[0-9][0-9,.]*)"
        ),
        "unit": "source_presented_usd_guidance_scale",
        "period_label": "FY27 full-year guidance",
        "period_role": "updated_management_guidance",
    },
    {
        "observation_id": "dell_ai_server_revenue_guidance_previous_fy27",
        "proposition_id": "FY27_GUIDANCE",
        "pattern": r"AI-Optimized Servers revenue\s+(?P<surface>\$\s*[0-9][0-9,.]*)\s+\$",
        "unit": "source_presented_usd_guidance_scale",
        "period_label": "FY27 full-year guidance",
        "period_role": "previous_management_guidance",
    },
    {
        "observation_id": "dell_ai_server_revenue_guidance_updated_fy27",
        "proposition_id": "FY27_GUIDANCE",
        "pattern": (
            r"AI-Optimized Servers revenue\s+\$\s*[0-9][0-9,.]*\s+"
            r"(?P<surface>\$\s*[0-9][0-9,.]*)"
        ),
        "unit": "source_presented_usd_guidance_scale",
        "period_label": "FY27 full-year guidance",
        "period_role": "updated_management_guidance",
    },
)


def _build_observations(
    items: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for spec in _OBSERVATION_SPECS:
        item = items[spec["proposition_id"]]
        source = dict(item["source"])
        excerpt = str(source["source_text"])
        matches = list(re.finditer(spec["pattern"], excerpt, flags=re.IGNORECASE))
        _require(
            len(matches) == 1,
            "research_calculation_source_observation_missing_or_ambiguous:"
            + spec["observation_id"],
        )
        surface = matches[0].group("surface")
        _require(
            surface in excerpt,
            "research_calculation_source_visible_surface_unverified:"
            + spec["observation_id"],
        )
        value = _parse_source_value(
            surface,
            "research_calculation_source_value_invalid:" + spec["observation_id"],
        )
        body = {
            "observation_id": spec["observation_id"],
            "metric_id": spec["observation_id"],
            "value_decimal": _decimal_string(value),
            "source_visible_surface": surface,
            "source_visible_surface_verified": True,
            "unit": spec["unit"],
            "period_label": spec["period_label"],
            "period_role": spec["period_role"],
            "source_reporting_period_end": item["source_reporting_period_end"],
            "evidence_id": _evidence_id(item),
            "evidence_item_digest": item["evidence_item_digest"],
            "source_material_ref": item["source_material_ref"],
            "source_record_id": item["source_record_id"],
            "source_url": source["source_url"],
            "source_content_digest": item["source_content_digest"],
            "source_locator": deepcopy(dict(source["source_locator"])),
            "source_authority": "official_issuer_unaudited_sec_exhibit",
            "authority_mode": SOURCE_OBSERVATION_AUTHORITY_MODE,
            "issuer_disclosed_value": True,
            "numeric_fact_authority": False,
            "s2_numeric_fact_authority": False,
            "s2_mart_write_authorized": False,
            "case_only_calculation_input_authorized": True,
        }
        observations.append(
            {**body, "source_observation_digest": canonical_digest(body)}
        )
    return observations


_CALCULATION_SPECS: tuple[dict[str, Any], ...] = (
    {
        "calculation_id": "dell_ai_server_revenue_share_of_isg_q2_fy27",
        "formula_id": "percent_of",
        "formula": "ai_server_revenue / isg_revenue * 100",
        "inputs": (
            "dell_ai_server_revenue_q2_fy27",
            "dell_isg_revenue_q2_fy27",
        ),
        "unit": "percent",
        "metric_label": "AI-optimized server revenue share of ISG revenue",
        "semantic_type": "same_quarter_revenue_mix_recalculation",
        "semantic_caveat": (
            "Mechanically calculated from rounded same-quarter issuer-disclosed "
            "revenue values; it is not an issuer-reported mix metric."
        ),
    },
    {
        "calculation_id": "dell_ai_server_revenue_share_of_company_q2_fy27",
        "formula_id": "percent_of",
        "formula": "ai_server_revenue / company_revenue * 100",
        "inputs": (
            "dell_ai_server_revenue_q2_fy27",
            "dell_company_revenue_q2_fy27",
        ),
        "unit": "percent",
        "metric_label": "AI-optimized server revenue share of company revenue",
        "semantic_type": "same_quarter_revenue_mix_recalculation",
        "semantic_caveat": (
            "Mechanically calculated from rounded same-quarter issuer-disclosed "
            "revenue values; it is not an issuer-reported company mix metric."
        ),
    },
    {
        "calculation_id": "dell_isg_operating_margin_recalculated_q2_fy27",
        "formula_id": "percent_of",
        "formula": "isg_operating_income / isg_revenue * 100",
        "inputs": (
            "dell_isg_operating_income_q2_fy27",
            "dell_isg_revenue_q2_fy27",
        ),
        "unit": "percent",
        "metric_label": "ISG operating margin recalculation",
        "semantic_type": "segment_operating_margin_recalculation",
        "semantic_caveat": (
            "This is ISG segment operating margin calculated from rounded disclosed "
            "figures; it is not AI-server margin or product-level profit."
        ),
    },
    {
        "calculation_id": "dell_ai_server_orders_to_revenue_multiple_q2_fy27",
        "formula_id": "ratio_multiple",
        "formula": "ai_server_orders / ai_server_revenue",
        "inputs": (
            "dell_ai_server_orders_q2_fy27",
            "dell_ai_server_revenue_q2_fy27",
        ),
        "unit": "multiple",
        "metric_label": "AI-server orders-to-quarterly-revenue multiple",
        "semantic_type": "same_quarter_flow_multiple",
        "semantic_caveat": (
            "Order flow divided by recognized quarterly revenue flow; this is not "
            "a conversion rate, delivery duration, backlog burn rate, or forecast."
        ),
    },
    {
        "calculation_id": "dell_ai_server_backlog_to_revenue_multiple_q2_fy27",
        "formula_id": "ratio_multiple",
        "formula": "quarter_end_ai_server_backlog / ai_server_quarterly_revenue",
        "inputs": (
            "dell_ai_server_backlog_q2_fy27",
            "dell_ai_server_revenue_q2_fy27",
        ),
        "unit": "multiple",
        "metric_label": "Quarter-end AI-server backlog-to-quarterly-revenue multiple",
        "semantic_type": "stock_over_quarter_flow_multiple",
        "semantic_caveat": (
            "Quarter-end backlog stock divided by one quarter of recognized revenue; "
            "this is not conversion, backlog duration, quarters of coverage, or a "
            "delivery forecast."
        ),
    },
    {
        "calculation_id": "dell_ai_server_revenue_guidance_uplift_fy27",
        "formula_id": "relative_uplift_percent",
        "formula": (
            "(updated_ai_server_guidance - previous_ai_server_guidance) / "
            "previous_ai_server_guidance * 100"
        ),
        "inputs": (
            "dell_ai_server_revenue_guidance_updated_fy27",
            "dell_ai_server_revenue_guidance_previous_fy27",
        ),
        "unit": "percent",
        "metric_label": "FY27 AI-server revenue guidance uplift",
        "semantic_type": "management_guidance_revision",
        "semantic_caveat": (
            "Relative change from previous to updated management guidance; it is "
            "not realized revenue growth or achieved performance."
        ),
    },
    {
        "calculation_id": "dell_company_revenue_guidance_uplift_fy27",
        "formula_id": "relative_uplift_percent",
        "formula": (
            "(updated_company_guidance - previous_company_guidance) / "
            "previous_company_guidance * 100"
        ),
        "inputs": (
            "dell_company_revenue_guidance_updated_fy27",
            "dell_company_revenue_guidance_previous_fy27",
        ),
        "unit": "percent",
        "metric_label": "FY27 company revenue guidance uplift",
        "semantic_type": "management_guidance_revision",
        "semantic_caveat": (
            "Relative change from previous to updated management guidance; it is "
            "not realized company revenue growth or achieved performance."
        ),
    },
)


def _calculate_value(spec: Mapping[str, Any], inputs: list[Decimal]) -> Decimal:
    _require(
        len(inputs) == 2 and inputs[1] != 0,
        "research_calculation_denominator_zero:" + str(spec["calculation_id"]),
    )
    with localcontext() as context:
        context.prec = 36
        if spec["formula_id"] == "percent_of":
            return inputs[0] / inputs[1] * Decimal("100")
        if spec["formula_id"] == "ratio_multiple":
            return inputs[0] / inputs[1]
        if spec["formula_id"] == "relative_uplift_percent":
            return (inputs[0] - inputs[1]) / inputs[1] * Decimal("100")
    raise DellQ2ResearchCalculationError(
        "research_calculation_formula_not_whitelisted"
    )


def _display_value(value: Decimal, unit: str) -> str:
    if unit == "percent":
        return format(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), "f") + "%"
    _require(unit == "multiple", "research_calculation_display_unit_invalid")
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f") + "x"


def _build_calculations(
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    indexed = {row["observation_id"]: row for row in observations}
    calculations: list[dict[str, Any]] = []
    for spec in _CALCULATION_SPECS:
        input_rows = [indexed[observation_id] for observation_id in spec["inputs"]]
        _require(
            input_rows[0]["unit"] == input_rows[1]["unit"],
            "research_calculation_input_unit_mismatch:"
            + str(spec["calculation_id"]),
        )
        label = str(spec["metric_label"]).lower()
        _require(
            not (
                spec["semantic_type"] == "stock_over_quarter_flow_multiple"
                and ("conversion" in label or "duration" in label)
            ),
            "research_calculation_stock_flow_label_invalid",
        )
        values = [Decimal(str(row["value_decimal"])) for row in input_rows]
        value = _calculate_value(spec, values)
        evidence_ids = list(dict.fromkeys(row["evidence_id"] for row in input_rows))
        source_urls = list(dict.fromkeys(row["source_url"] for row in input_rows))
        source_digests = list(
            dict.fromkeys(row["source_content_digest"] for row in input_rows)
        )
        short_caveat = REQUIRED_SHORT_CAVEAT
        if spec["semantic_type"] == "stock_over_quarter_flow_multiple":
            short_caveat += " 该值为时点存量/季度流量比，不是转化率或持续期。"
        body = {
            "calculation_id": spec["calculation_id"],
            "metric_label": spec["metric_label"],
            "semantic_type": spec["semantic_type"],
            "value_decimal": _decimal_string(value),
            "display_value": _display_value(value, str(spec["unit"])),
            "unit": spec["unit"],
            "formula_id": spec["formula_id"],
            "formula": spec["formula"],
            "input_observation_ids": list(spec["inputs"]),
            "input_observation_digests": [
                row["source_observation_digest"] for row in input_rows
            ],
            "evidence_ids": evidence_ids,
            "source_urls": source_urls,
            "source_content_digests": source_digests,
            "semantic_caveat": spec["semantic_caveat"],
            "required_short_caveat": short_caveat,
            "reasoning_caveat_required": True,
            "model_reasoning_allowed": True,
            "source_authority": "official_issuer_unaudited_sec_exhibit",
            "authority_mode": CALCULATION_AUTHORITY_MODE,
            "calculation_reproducible": True,
            "issuer_reported_metric": False,
            "numeric_fact_authority": False,
            "s2_numeric_fact_authority": False,
            "s2_mart_write_authorized": False,
        }
        calculations.append(
            {**body, "research_calculation_digest": canonical_digest(body)}
        )
    return calculations


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_bytes(_canonical_bytes(dict(value)))


def materialize_research_calculation_pack(
    reviewed_evidence_input_path: Path,
    output_root: Path,
    attempt_id: str,
    *,
    expected_input_sha256: str,
    materialized_at: str | None = None,
) -> dict[str, Any]:
    _require(
        _ATTEMPT_ID.fullmatch(attempt_id) is not None,
        "research_calculation_attempt_id_invalid",
    )
    timestamp = materialized_at or datetime.now().astimezone().isoformat(
        timespec="seconds"
    )
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise DellQ2ResearchCalculationError(
            "research_calculation_materialized_at_invalid"
        ) from exc
    _require(
        parsed_timestamp.tzinfo is not None,
        "research_calculation_materialized_at_timezone_missing",
    )

    input_path = reviewed_evidence_input_path.resolve()
    _require(
        input_path.is_file(),
        "research_calculation_reviewed_input_missing",
    )
    items, input_binding = _load_reviewed_input(
        input_path,
        expected_input_sha256,
    )
    indexed_items, research_as_of = _validate_and_index_items(items)
    observations = _build_observations(indexed_items)
    calculations = _build_calculations(observations)

    pack_body = {
        "schema_version": CALCULATION_PACK_SCHEMA,
        "status": "case_only_non_s2_research_calculations_ready",
        "attempt_id": attempt_id,
        "case_key": "DELL",
        "research_as_of": research_as_of,
        "materialized_at": timestamp,
        "source_input": deepcopy(input_binding),
        "source_numeric_observations": observations,
        "research_calculations": calculations,
        "observed_counts": {
            "reviewed_evidence_items": len(items),
            "source_numeric_observations": len(observations),
            "research_calculations": len(calculations),
        },
        "authority": {
            "source_authority": "official_issuer_unaudited_sec_exhibit",
            "successor_authority_basis": (
                "owner_approved_case_only_non_s2_research_calculation_lane"
            ),
            "source_visible_surface_required": True,
            "deterministic_formula_whitelist_required": True,
            "model_raw_numbers_accepted": False,
            "model_reasoning_allowed_with_caveat": True,
            "issuer_reported_metric_authority": False,
            "numeric_fact_authority": False,
            "s2_numeric_fact_authority": False,
            "s2_mart_write_authorized": False,
            "reviewed_evidence_pack_mutation_authorized": False,
            "runtime_or_mcp_mutation_authorized": False,
        },
        "known_boundary": (
            "This case-only pack preserves official issuer-source lineage while "
            "keeping every observation and derivation outside S2 NumericFact. "
            "Calculations use rounded source-visible values, are not separately "
            "reported issuer metrics, and must retain their short caveat when used "
            "in reasoning or presentation."
        ),
    }
    pack = {
        **pack_body,
        "calculation_pack_payload_digest": canonical_digest(pack_body),
    }

    attempt_root = output_root.resolve() / attempt_id
    _require(
        not attempt_root.exists(),
        "research_calculation_attempt_already_exists",
    )
    attempt_root.mkdir(parents=True, exist_ok=False)
    pack_path = attempt_root / "research-calculation-pack.json"
    _write_json(pack_path, pack)
    manifest_body = {
        "schema_version": CALCULATION_MANIFEST_SCHEMA,
        "status": "case_only_non_s2_research_calculation_artifacts_materialized",
        "attempt_id": attempt_id,
        "case_key": "DELL",
        "materialized_at": timestamp,
        "source_input": {
            **deepcopy(input_binding),
            "path": input_path.as_posix(),
        },
        "artifacts": {
            "research_calculation_pack": {
                "path": pack_path.as_posix(),
                "bytes": pack_path.stat().st_size,
                "sha256": _sha256_file(pack_path),
                "payload_digest": pack["calculation_pack_payload_digest"],
            }
        },
        "checks": {
            "all_source_visible_surfaces_verified": all(
                row["source_visible_surface_verified"] for row in observations
            ),
            "all_numeric_fact_authority_false": all(
                row["numeric_fact_authority"] is False
                for row in [*observations, *calculations]
            ),
            "all_calculations_have_formula_and_input_lineage": all(
                row["formula_id"] and row["input_observation_ids"]
                for row in calculations
            ),
            "all_calculations_have_required_short_caveat": all(
                row["required_short_caveat"] for row in calculations
            ),
            "s2_mart_written": False,
            "reviewed_evidence_pack_mutated": False,
            "mcp_or_runtime_mutated": False,
            "model_called": False,
        },
    }
    manifest = {
        **manifest_body,
        "manifest_payload_digest": canonical_digest(manifest_body),
    }
    manifest_path = attempt_root / "manifest.json"
    _write_json(manifest_path, manifest)
    return {
        **manifest,
        "manifest_path": manifest_path.as_posix(),
        "manifest_file_sha256": _sha256_file(manifest_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize deterministic, case-only Dell FY27 Q2 research "
            "calculations from a digest-bound Reviewed Evidence overlay or pack."
        )
    )
    parser.add_argument("--reviewed-evidence-input", type=Path, required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()
    result = materialize_research_calculation_pack(
        args.reviewed_evidence_input,
        args.output_root,
        args.attempt_id,
        expected_input_sha256=args.expected_input_sha256,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CALCULATION_AUTHORITY_MODE",
    "CALCULATION_MANIFEST_SCHEMA",
    "CALCULATION_PACK_SCHEMA",
    "DellQ2ResearchCalculationError",
    "REQUIRED_SHORT_CAVEAT",
    "SOURCE_OBSERVATION_AUTHORITY_MODE",
    "materialize_research_calculation_pack",
]
