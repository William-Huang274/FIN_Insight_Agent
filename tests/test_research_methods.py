import asyncio

import pytest
from mcp import Client

from sec_agent.research_foundation.research_methods import METHODS, get_research_method
from test_research_mcp import _build_server


def test_method_catalog_is_compact_answer_free_and_content_is_packaged():
    catalog = get_research_method()
    assert {row["method_id"] for row in catalog["methods"]} == set(METHODS)
    assert all("content" not in row for row in catalog["methods"])
    for method_id in METHODS:
        method = get_research_method(method_id)
        assert method["content"] and method["answer_free"] and not method["grants_authority"]
        assert "Dell" not in method["content"] and "DELL" not in method["content"]


@pytest.mark.parametrize("method_id", ["../../.env", "D:/private.txt", "unknown", "finance.md"])
def test_method_reader_does_not_accept_paths_or_unknown_resources(method_id):
    with pytest.raises(ValueError, match="unknown_research_method"):
        get_research_method(method_id)


def test_actual_mcp_progressive_method_read_and_rejection():
    async def exercise():
        async with Client(_build_server(), raise_exceptions=False) as client:
            catalog = await client.call_tool("get_research_method", {})
            assert not catalog.is_error and len(catalog.structured_content["methods"]) == 6
            method = await client.call_tool("get_research_method", {"method_id": "finance"})
            assert not method.is_error
            assert "利润率变化用百分点" in method.structured_content["content"]
            assert "不是预测" in method.structured_content["content"]
            rejected = await client.call_tool("get_research_method", {"method_id": "../../.env"})
            assert rejected.is_error
    asyncio.run(exercise())


@pytest.mark.parametrize("method_id", ["finance", "writer", "verifier"])
def test_actual_mcp_method_preserves_disclosure_vs_achievement_distinction(method_id):
    async def exercise():
        async with Client(_build_server(), raise_exceptions=False) as client:
            method = await client.call_tool("get_research_method", {"method_id": method_id})
            assert not method.is_error
            assert "未单独披露不等于未实现" in method.structured_content["content"]
            assert method.structured_content["answer_free"]
            assert not method.structured_content["grants_authority"]
    asyncio.run(exercise())
