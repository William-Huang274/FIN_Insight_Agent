from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping

DEEPSEEK_STRICT_UNSUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "uniqueItems",
    }
)


class DeepSeekStrictProjectionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DeepSeekStrictProjectionError(code)


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _project_schema(
    value: Any,
    *,
    removed: dict[str, int],
    counters: dict[str, int],
) -> Any:
    if isinstance(value, list):
        return [
            _project_schema(item, removed=removed, counters=counters)
            for item in value
        ]
    if not isinstance(value, Mapping):
        return deepcopy(value)

    projected: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        if key in DEEPSEEK_STRICT_UNSUPPORTED_SCHEMA_KEYWORDS:
            removed[key] = removed.get(key, 0) + 1
            continue
        if key == "$defs":
            _require("$def" not in value, "deepseek_strict_schema_def_conflict")
            key = "$def"
            counters["definitions_renamed"] += 1
        if key == "$ref" and isinstance(raw_value, str):
            rewritten = raw_value.replace("#/$defs/", "#/$def/")
            if rewritten != raw_value:
                counters["references_rewritten"] += 1
            projected[key] = rewritten
            continue
        projected[key] = _project_schema(
            raw_value,
            removed=removed,
            counters=counters,
        )
    return projected


def project_deepseek_strict_tool(
    tool: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project one canonical strict tool into DeepSeek's Beta subset.

    The canonical finance contract remains unchanged and is still enforced
    locally.  This provider profile only renames DeepSeek's documented
    ``$def`` surface and removes constraints the strict server does not
    reliably support.
    """

    _require(
        isinstance(tool, Mapping) and set(tool) == {"type", "function"},
        "deepseek_strict_tool_invalid",
    )
    function = tool.get("function")
    _require(
        tool.get("type") == "function"
        and isinstance(function, Mapping)
        and function.get("strict") is True
        and isinstance(function.get("parameters"), Mapping),
        "deepseek_strict_tool_invalid",
    )
    canonical = deepcopy(dict(tool))
    removed: dict[str, int] = {}
    counters = {"definitions_renamed": 0, "references_rewritten": 0}
    projected = deepcopy(canonical)
    projected["function"]["parameters"] = _project_schema(
        canonical["function"]["parameters"],
        removed=removed,
        counters=counters,
    )
    receipt_body = {
        "schema_version": "fin_ia_deepseek_strict_tool_projection_v1_0",
        "provider_id": "deepseek",
        "provider_surface": "chat_completions_beta_strict",
        "canonical_tool_digest": _canonical_digest(canonical),
        "projected_tool_digest": _canonical_digest(projected),
        "removed_schema_keywords": dict(sorted(removed.items())),
        "definitions_renamed": counters["definitions_renamed"],
        "references_rewritten": counters["references_rewritten"],
        "local_full_contract_validation_required": True,
        "finance_contract_weakened": False,
    }
    return projected, {
        **receipt_body,
        "projection_digest": _canonical_digest(receipt_body),
    }


def validate_deepseek_strict_submission_profile(profile: object) -> None:
    defaults = dict(getattr(profile, "request_defaults", {}) or {})
    _require(
        str(getattr(profile, "provider_id", "")) == "deepseek"
        and str(getattr(profile, "model", "")) == "deepseek-v4-pro"
        and str(getattr(profile, "base_url", "")).rstrip("/")
        == "https://api.deepseek.com/beta"
        and str(getattr(profile, "endpoint", "")) == "/chat/completions"
        and defaults
        == {
            "max_tokens": 2000,
            "stream": False,
            "thinking": {"type": "disabled"},
        },
        "deepseek_strict_submission_profile_invalid",
    )


__all__ = [
    "DEEPSEEK_STRICT_UNSUPPORTED_SCHEMA_KEYWORDS",
    "DeepSeekStrictProjectionError",
    "project_deepseek_strict_tool",
    "validate_deepseek_strict_submission_profile",
]
