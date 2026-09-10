"""Archived diagnostic guards: no provider calls or synthetic financial claims."""
import json
import sys

import pytest

from scripts.qualification.dell_q1_specialist_paid_shadow import compare_review_model_once as comparison


@pytest.mark.parametrize("failure", [None, "input_budget", "output_budget", "duplicate_tool"])
def test_archived_preparation_preserves_evidence_and_checks_budget_before_credentials(tmp_path, monkeypatch, failure):
    message = {"type": "human", "content": "Exact archived source text."}
    if failure == "input_budget":
        message["content"] *= 500
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"call_id": "archived-call", "actor": "writer", "messages": [message]}), encoding="utf-8")
    schemas = [{"type": "function", "function": {"name": "submit_case_answer", "description": "Native shape fixture only.",
        "parameters": {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}}}]
    if failure == "duplicate_tool":
        schemas *= 2
    tools = tmp_path / "tools.json"
    tools.write_text(json.dumps(schemas), encoding="utf-8")
    basis = {"node_role": "lead", "node_purpose": "Guard-only fixture.", "input_scale": "One preserved message.",
        "required_outputs": ["one diagnostic next action"], "schema_burden": "One native tool.",
        "materiality_quality_risk": "Do not spend or drop evidence during preparation.",
        "comparable_run_evidence": "No paid claim.", "reasoning_profile": "agentic_message_history_thinking_enabled",
        "max_input_characters": 10000, "max_output_tokens": 2000 if failure == "output_budget" else 1000,
        "timeout_seconds": 60, "max_transport_attempts": 1, "retry_policy": "none",
        "truncation_stop_behavior": "fail_closed_no_partial_promotion", "input_ceiling_behavior": "fail_before_transport"}
    budget = tmp_path / "budget.json"
    budget.write_text(json.dumps(basis), encoding="utf-8")
    output = tmp_path / "prepared"
    monkeypatch.setattr(sys, "argv", ["compare", "--source-audit", str(source), "--output-dir", str(output),
        "--model", "deepseek-v4-pro", "--effort", "max", "--task", "archived-action", "--tools-file", str(tools),
        "--budget-basis", str(budget), "--max-output-tokens", "1000", "--prepare-only"])

    def forbidden():
        pytest.fail("Preparation must never load credentials or spend tokens.")

    monkeypatch.setattr(comparison, "_dotenv", forbidden)
    if failure:
        expected = {"input_budget": "input_budget_exceeded", "output_budget": "output_budget_mismatch",
                    "duplicate_tool": "unique_native_tools_required"}[failure]
        with pytest.raises(ValueError, match=expected):
            comparison.main()
        assert not (output / "request.json").exists()
    else:
        comparison.main()
        saved = json.loads((output / "messages.private.json").read_text(encoding="utf-8"))
        assert saved[0]["content"] == message["content"]
        assert json.loads((output / "tools.json").read_text(encoding="utf-8")) == schemas
