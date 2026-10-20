"""Lossless envelope compatibility still uses MCP scope and source validation."""
import asyncio
from copy import deepcopy
import json

from mcp import Client
import pytest

from sec_agent.agent_runtime.case_review_agent import (
    _scoped_mcp_tools, normalize_source_read_arguments,
)
from sec_agent.research_foundation.source_document_navigation import SourceDocumentResult
from test_research_mcp import _build_server, _method_arguments, GET_RESEARCH_METHOD_TOOL


BRANCH = "Q1_ISSUER_TRUTH"


@pytest.mark.parametrize("outer", [None, BRANCH])
def test_relocation_is_lossless_and_idempotent(outer):
    raw = {"request": {"branch_id": BRANCH, "operation": "read", "node_id": "NODE::selected"}}
    if outer:
        raw["branch_id"] = outer
    before = deepcopy(raw)
    normalized, record = normalize_source_read_arguments(
        "read_source_document", raw, {"selected_branch_ids": [BRANCH]})
    assert raw == before
    assert normalized == {"branch_id": BRANCH, "request": {
        "operation": "read", "node_id": "NODE::selected"}}
    assert record["original_input"] == before
    assert record["normalized_result"] == normalized
    assert record["financial_semantics_verified"] is False
    assert normalize_source_read_arguments(
        "read_source_document", normalized, {"selected_branch_ids": [BRANCH]}) == (normalized, None)


@pytest.mark.parametrize("name,raw,scope", [
    ("other_tool", {"request": {"branch_id": BRANCH}}, {"selected_branch_ids": [BRANCH]}),
    ("read_source_document", {"request": {"branch_id": BRANCH}}, None),
    ("read_source_document", {"request": {"branch_id": "OTHER"}}, {"selected_branch_ids": [BRANCH]}),
    ("read_source_document", {"request": {"branch_id": BRANCH}, "branch_id": "OTHER"},
     {"selected_branch_ids": [BRANCH]}),
    ("read_source_document", {"request": {"branch_id": BRANCH}, "branch_id": None},
     {"selected_branch_ids": [BRANCH]}),
    ("read_source_document", {"request": {}}, {"selected_branch_ids": [BRANCH]}),
    ("read_source_document", {"request": {"branch_id": 1}}, {"selected_branch_ids": [BRANCH]}),
])
def test_no_inference_or_conflict_resolution(name, raw, scope):
    before = deepcopy(raw)
    assert normalize_source_read_arguments(name, raw, scope) == (before, None)
    assert raw == before


@pytest.mark.parametrize("problem", ["none", "extra", "source", "conflict"])
def test_native_mcp_still_validates_and_receipt_preserves_arguments(problem):
    invoked = []

    def reader(*, request, branch_id, **_):
        invoked.append((request.node_id, branch_id))
        if problem == "source":
            raise ValueError("source_node_not_in_selected_document")
        return SourceDocumentResult(operation="read", items=({"node_id": request.node_id,
            "text": "Exact source content."},), total_matches=1, next_offset=None,
            notice="Synthetic source.", source_snapshot_sha256="a" * 64)

    async def run():
        async with Client(_build_server(source_document_reader=reader)) as client:
            method = await client.call_tool(GET_RESEARCH_METHOD_TOOL, _method_arguments([BRANCH]))
            scope = method.structured_content["run_scope"]
            tools = await _scoped_mcp_tools(client, allowed={"read_source_document"},
                required={"read_source_document"}, run_scope=scope)
            raw = {"request": {"branch_id": BRANCH, "operation": "read",
                "document_id": "DOC::selected", "node_id": "NODE::selected"}}
            if problem == "extra":
                raw["request"]["unexpected"] = "Must remain invalid"
            if problem == "conflict":
                raw["branch_id"] = "Q2_DEMAND_QUALITY"
            before = deepcopy(raw)
            result = await tools[0].ainvoke({"name": "read_source_document",
                "args": raw, "id": "original-call", "type": "tool_call"})
            assert raw == before
            assert (result.status == "error") == (problem != "none")
            if problem == "none":
                assert invoked == [("NODE::selected", BRANCH)]
                assert result.artifact["items"][0]["text"] == "Exact source content."
                record = result.artifact["runtime_argument_recovery"][0]
                assert record["original_input"] == before
                assert record["normalized_result"]["branch_id"] == BRANCH
            elif problem != "conflict":
                record = json.loads(result.content)["runtime_argument_recovery"][0]
                assert record["original_input"] == before
            if problem in {"extra", "conflict"}:
                assert not invoked
    asyncio.run(run())
