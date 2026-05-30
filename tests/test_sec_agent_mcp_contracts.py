from __future__ import annotations

import json
from pathlib import Path

from sec_agent.mcp_contracts import export_mcp_tool_contracts, list_mcp_tool_contracts, validate_mcp_tool_contracts
from sec_agent.mcp_runtime import read_bounded_artifact
from sec_agent.research_skills import list_research_skills, research_skill_prompt


def test_mcp_tool_contracts_are_valid_and_cover_core_sources() -> None:
    contracts = list_mcp_tool_contracts()
    validate_mcp_tool_contracts(contracts)
    names = {contract["name"] for contract in contracts}
    assert {
        "sec_search_filings",
        "sec_query_exact_value_ledger",
        "market_get_snapshot",
        "industry_get_snapshot",
        "run_inspect_artifacts",
        "run_read_artifact",
    } <= names
    for contract in contracts:
        assert contract["input_schema"]["type"] == "object"
        assert contract["output_schema"]["type"] == "object"
        assert contract["source_boundaries"]["allowed_claim_types"]
        assert contract["source_boundaries"]["prohibited_claims"]


def test_mcp_tool_contracts_export_json(tmp_path: Path) -> None:
    output = tmp_path / "contracts.json"
    payload = export_mcp_tool_contracts(output)
    assert output.exists()
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == payload["schema_version"]
    assert len(persisted["tools"]) == len(payload["tools"])


def test_read_bounded_artifact_enforces_bounds(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    answer = run_dir / "qwen" / "rendered_answer.md"
    answer.parent.mkdir(parents=True)
    answer.write_text("# Answer\n\nhello world", encoding="utf-8")

    ok = read_bounded_artifact(run_dir=run_dir, artifact_id="rendered_answer", max_bytes=100)
    assert ok["status"] == "ok"
    assert ok["artifact_id"] == "rendered_answer"
    assert ok["truncated"] is False
    assert "hello world" in ok["content"]

    truncated = read_bounded_artifact(run_dir=run_dir, artifact_id="rendered_answer", max_bytes=4)
    assert truncated["status"] == "truncated"
    assert truncated["truncated"] is True

    escaped = read_bounded_artifact(run_dir=run_dir, rel_path="../outside.json")
    assert escaped["status"] == "error"
    assert escaped["error"] == "artifact_id_or_rel_path_required"


def test_research_skills_are_loadable_and_role_scoped() -> None:
    inventory = list_research_skills()
    assert "investment_research_workflow" in inventory["skill_files"]
    planner_skill = research_skill_prompt("planner", max_chars=2400)
    reflection_skill = research_skill_prompt("reflection", max_chars=3000)
    assert "EvidenceRequirementPlan" in planner_skill
    assert "Second-Pass Policy" in reflection_skill
