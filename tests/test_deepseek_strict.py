from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.providers.deepseek_strict import (
    DeepSeekStrictProjectionError,
    project_deepseek_strict_tool,
    validate_deepseek_strict_submission_profile,
)
from sec_agent.providers.chat_completions import load_chat_completion_profile


def _tool() -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": "submit_safe_atom",
            "description": "Submit one safe atom.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "atom": {
                        "$ref": "#/$defs/t",
                        "description": "No digits.",
                    },
                    "refs": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["A", "B"]},
                        "minItems": 1,
                        "maxItems": 2,
                        "uniqueItems": True,
                    },
                },
                "required": ["atom", "refs"],
                "additionalProperties": False,
                "$defs": {
                    "t": {
                        "type": "string",
                        "pattern": "^(?![\\s\\S]*[0-9])[\\s\\S]+$",
                        "minLength": 12,
                        "maxLength": 200,
                    }
                },
            },
        },
    }


def test_deepseek_strict_projection_preserves_pattern_and_local_contract() -> None:
    canonical = _tool()
    before = deepcopy(canonical)

    projected, receipt = project_deepseek_strict_tool(canonical)

    assert canonical == before
    parameters = projected["function"]["parameters"]
    assert "$defs" not in parameters
    assert parameters["$def"]["t"] == {
        "type": "string",
        "pattern": "^(?![\\s\\S]*[0-9])[\\s\\S]+$",
    }
    assert parameters["properties"]["atom"]["$ref"] == "#/$def/t"
    assert parameters["properties"]["refs"] == {
        "type": "array",
        "items": {"type": "string", "enum": ["A", "B"]},
    }
    assert receipt["removed_schema_keywords"] == {
        "maxItems": 1,
        "maxLength": 1,
        "minItems": 1,
        "minLength": 1,
        "uniqueItems": 1,
    }
    assert receipt["definitions_renamed"] == 1
    assert receipt["references_rewritten"] == 1
    assert receipt["local_full_contract_validation_required"] is True
    assert receipt["finance_contract_weakened"] is False


def test_deepseek_strict_projection_rejects_non_strict_tool() -> None:
    tool = _tool()
    tool["function"]["strict"] = False
    with pytest.raises(DeepSeekStrictProjectionError, match="deepseek_strict_tool_invalid"):
        project_deepseek_strict_tool(tool)
