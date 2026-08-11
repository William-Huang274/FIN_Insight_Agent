from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
import re
from typing import Any, Mapping


PROMPT_METADATA_TYPE_POLICY_REF = (
    "fin_0_1_3.S2.prompt_metadata_native_scalar_policy:v1"
)

INTEGER_FIELDS = frozenset(
    {
        "count",
        "row_count",
        "ready_count",
        "gap_count",
        "line_item_count",
        "input_row_count",
        "product_spec_count",
        "product_kpi_count",
        "customer_deployment_count",
        "omitted_key_count",
        "key_count",
    }
)
BOOLEAN_FIELDS = frozenset(
    {
        "available",
        "valid",
        "ready",
        "bounded_answer_allowed",
        "three_statement_coverage",
        "peer_comparison_ready",
        "product_financial_bridge_ready",
        "capital_funding_bridge_ready",
        "thesis_driver_authority",
        "financial_fact_authority",
        "relationship_fact_only",
        "relationship_context_available",
        "source_exhaustion_proven",
    }
)
DECIMAL_STRING_FIELDS = frozenset(
    {
        "coverage_ratio",
        "evidence_utilization",
        "required_slot_recall",
        "confidence_score",
    }
)
STRING_LIST_FIELDS = frozenset(
    {
        "issuer_matched_terms",
        "product_matched_terms",
        "counterparty_matched_terms",
        "keys",
    }
)
STRING_FIELDS = frozenset(
    {
        "schema_version",
        "pack_id",
        "artifact_ref",
        "artifact_uri",
        "path",
        "source_id",
        "source_family",
        "source_role",
        "source_url",
        "snapshot_url",
        "url",
        "ticker",
        "company",
        "product",
        "product_family",
        "metric",
        "metric_family",
        "period",
        "confidence",
        "authority_boundary",
        "status",
        "coverage_status",
        "source_entity_role",
        "issuer_binding_status",
        "product_binding_status",
        "counterparty_binding_status",
        "binding_claim_boundary",
        "content_policy",
    }
)

_DECIMAL_PATTERN = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
_OMITTED = object()


class PromptMetadataContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def prompt_metadata_type_policy() -> dict[str, Any]:
    """Return the one machine-readable policy used by projection and validation."""

    return {
        "contract_ref": PROMPT_METADATA_TYPE_POLICY_REF,
        "integer_fields": sorted(INTEGER_FIELDS),
        "boolean_fields": sorted(BOOLEAN_FIELDS),
        "decimal_string_fields": sorted(DECIMAL_STRING_FIELDS),
        "string_list_fields": sorted(STRING_LIST_FIELDS),
        "string_fields": sorted(STRING_FIELDS),
        "unknown_short_string_policy": "bounded_text_allowed",
        "unknown_numeric_or_boolean_policy": "omit_fail_closed",
        "financial_decimal_policy": (
            "only named ratio/score metadata may use canonical decimal strings; "
            "financial values remain governed aliases or exact Numeric-pack fields"
        ),
    }


def compact_prompt_metadata(
    value: Any,
    *,
    max_items: int,
    text_limit: int,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact: dict[str, Any] = {}
    omitted_keys: list[str] = []
    for key, item in list(value.items())[:max_items]:
        key_text = str(key)
        if _value_empty(item):
            continue
        if isinstance(item, Mapping):
            projected = _compact_nested_mapping(
                item,
                max_items=max_items,
                text_limit=text_limit,
            )
        else:
            projected = _project_scalar_or_list(
                key_text,
                item,
                text_limit=text_limit,
            )
        if projected is _OMITTED:
            omitted_keys.append(key_text)
        else:
            compact[key_text] = projected
    if omitted_keys:
        compact["omitted_keys"] = omitted_keys[:6]
        compact["omitted_key_count"] = len(omitted_keys)
        compact["content_policy"] = "metadata_ref_only_nested_payload_omitted"
    validate_prompt_metadata_types(compact)
    return compact


def validate_prompt_metadata_types(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping):
        raise PromptMetadataContractError("prompt_metadata_not_mapping")
    for key, item in value.items():
        key_text = str(key)
        if isinstance(item, Mapping):
            validate_prompt_metadata_types(item)
            continue
        if key_text in INTEGER_FIELDS:
            if isinstance(item, bool) or not isinstance(item, int):
                raise PromptMetadataContractError(
                    f"prompt_metadata_integer_type_invalid:{key_text}"
                )
        elif key_text in BOOLEAN_FIELDS:
            if not isinstance(item, bool):
                raise PromptMetadataContractError(
                    f"prompt_metadata_boolean_type_invalid:{key_text}"
                )
        elif key_text in DECIMAL_STRING_FIELDS:
            if not isinstance(item, str) or not _DECIMAL_PATTERN.fullmatch(item):
                raise PromptMetadataContractError(
                    f"prompt_metadata_decimal_string_invalid:{key_text}"
                )
        elif key_text in STRING_LIST_FIELDS or key_text == "omitted_keys":
            if not isinstance(item, list) or any(
                not isinstance(part, str) for part in item
            ):
                raise PromptMetadataContractError(
                    f"prompt_metadata_string_list_invalid:{key_text}"
                )
        elif isinstance(item, (bool, int, float, Decimal)):
            raise PromptMetadataContractError(
                f"prompt_metadata_unregistered_native_scalar:{key_text}"
            )


def _compact_nested_mapping(
    value: Mapping[str, Any],
    *,
    max_items: int,
    text_limit: int,
) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    omitted: list[str] = []
    for key, item in list(value.items())[:max_items]:
        key_text = str(key)
        if _value_empty(item):
            continue
        if isinstance(item, Mapping):
            omitted.append(key_text)
            continue
        projected = _project_scalar_or_list(
            key_text,
            item,
            text_limit=text_limit,
        )
        if projected is _OMITTED:
            omitted.append(key_text)
        else:
            compact[key_text] = projected
    if compact:
        all_omitted = [str(key) for key in value if str(key) not in compact]
        if all_omitted:
            compact["omitted_keys"] = all_omitted[:6]
            compact["omitted_key_count"] = len(all_omitted)
            compact["content_policy"] = "metadata_ref_only_nested_payload_omitted"
        return compact
    return {
        "keys": [str(key) for key in list(value)[:6]],
        "key_count": len(value),
        "content_policy": "metadata_ref_only_nested_payload_omitted",
    }


def _project_scalar_or_list(key: str, value: Any, *, text_limit: int) -> Any:
    if isinstance(value, (list, tuple, set)):
        if key not in STRING_LIST_FIELDS:
            return _OMITTED
        return [
            _truncate(str(part), text_limit)
            for part in list(value)[:4]
            if not isinstance(part, Mapping) and not _value_empty(part)
        ]
    if isinstance(value, bool):
        return value if key in BOOLEAN_FIELDS else _OMITTED
    if isinstance(value, int):
        return value if key in INTEGER_FIELDS else _OMITTED
    if isinstance(value, (float, Decimal)):
        if key not in DECIMAL_STRING_FIELDS:
            return _OMITTED
        return _canonical_decimal_string(value)
    if isinstance(value, str):
        if key in DECIMAL_STRING_FIELDS:
            return _canonical_decimal_string(value)
        if key in STRING_FIELDS or len(value) <= min(text_limit, 80):
            return _truncate(value, text_limit)
        return _OMITTED
    return _OMITTED


def _canonical_decimal_string(value: Any) -> str:
    if isinstance(value, float) and not math.isfinite(value):
        raise PromptMetadataContractError("prompt_metadata_decimal_not_finite")
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PromptMetadataContractError(
            "prompt_metadata_decimal_invalid"
        ) from exc
    if not decimal_value.is_finite():
        raise PromptMetadataContractError("prompt_metadata_decimal_not_finite")
    normalized = format(decimal_value.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    if normalized in {"-0", ""}:
        normalized = "0"
    return normalized


def _truncate(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _value_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


__all__ = [
    "PROMPT_METADATA_TYPE_POLICY_REF",
    "PromptMetadataContractError",
    "compact_prompt_metadata",
    "prompt_metadata_type_policy",
    "validate_prompt_metadata_types",
]
