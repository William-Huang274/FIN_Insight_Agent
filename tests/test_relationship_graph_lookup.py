from __future__ import annotations

import json
from pathlib import Path

from sec_agent.mcp_tool_registry import invoke_mcp_tool
from sec_agent.relationship_graph import query_relationship_graph, relationship_plan_from_lookup


def test_relationship_graph_jsonl_lookup_returns_hypothesis_rows(tmp_path: Path) -> None:
    graph_path = tmp_path / "relationships.jsonl"
    graph_path.write_text(
        json.dumps(
            {
                "ticker": "NVDA",
                "related_ticker": "MSFT",
                "relationship_type": "customer",
                "direction": "downstream_customer",
                "metrics_to_check": ["cloud_capex"],
                "evidence_source_needed": ["primary_sec_filing", "industry_snapshot"],
                "evidence_refs": ["rel_nvda_msft"],
                "inclusion_rationale": "MSFT is a cloud capex readthrough hypothesis.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = query_relationship_graph(
        focus_tickers=["NVDA"],
        relationship_graph_path=graph_path,
        include_sector_depth=False,
    )
    plan = relationship_plan_from_lookup(result, scope_mode="deep_research", focus_tickers=["NVDA"])

    assert result["status"] == "ok"
    assert result["relationship_rows"][0]["source_family"] == "relationship_graph"
    assert result["relationships"][0]["claim_scope"] == "scope_or_hypothesis_only"
    assert result["relationships"][0]["evidence_refs"] == ["rel_nvda_msft"]
    assert result["artifact_refs"][0]["digest"].startswith("sha256:")
    assert plan["relationships"][0]["related_ticker"] == "MSFT"
    assert plan["expanded_tickers"] == ["MSFT"]
    assert plan["included_tickers"] == ["NVDA", "MSFT"]


def test_sector_depth_pack_metadata_can_seed_ai_relationship_scope(tmp_path: Path) -> None:
    sector_path = tmp_path / "sector_depth.yaml"
    sector_path.write_text(
        """
packs:
  - pack_id: "technology_ai_infrastructure_depth"
    industry_group: "information_technology"
    research_questions:
      - "AI infrastructure demand transmission from chips to servers and cloud capex."
    candidate_tickers:
      p0: ["DELL", "ANET"]
      p1: ["VRT"]
    primary_metric_families:
      - "revenue"
      - "capex"
    required_source_families:
      - "us_primary_annual_10k"
      - "market_snapshot"
      - "industry_utilities_power_demand"
""",
        encoding="utf-8",
    )

    result = query_relationship_graph(
        focus_tickers=["NVDA"],
        user_query="AI cloud capex supply chain readthrough",
        sector_depth_pack_path=sector_path,
        max_relationships=2,
    )

    assert result["status"] == "ok"
    assert result["summary"]["sector_depth_rows"] == 2
    assert {row["related_ticker"] for row in result["relationship_rows"]} == {"DELL", "ANET"}
    assert set(result["relationships"][0]["evidence_source_needed"]) == {
        "primary_sec_filing",
        "market_snapshot",
        "industry_snapshot",
    }


def test_sector_depth_pack_scope_match_blocks_power_only_ai_cross_sector_leakage(tmp_path: Path) -> None:
    sector_path = tmp_path / "sector_depth.yaml"
    sector_path.write_text(_cross_sector_pack_yaml(), encoding="utf-8")

    result = query_relationship_graph(
        focus_tickers=["OXY", "SRE"],
        search_scope_tickers=["OXY", "HAL", "SRE", "XEL"],
        user_query="分析 energy infrastructure 和 real estate utilities 的电力负荷和利率背景",
        sector_depth_pack_path=sector_path,
        max_relationships=4,
    )
    refs = {ref for row in result["relationships"] for ref in row["evidence_refs"]}

    assert result["status"] == "ok"
    assert any("sector_depth_pack:energy_infrastructure_depth" in ref for ref in refs)
    assert any("sector_depth_pack:real_estate_utilities_depth" in ref for ref in refs)
    assert not any("sector_depth_pack:technology_ai_infrastructure_depth" in ref for ref in refs)


def test_sector_depth_pack_allows_explicit_ai_power_cross_sector_path(tmp_path: Path) -> None:
    sector_path = tmp_path / "sector_depth.yaml"
    sector_path.write_text(_cross_sector_pack_yaml(), encoding="utf-8")

    result = query_relationship_graph(
        focus_tickers=["SRE"],
        search_scope_tickers=["SRE", "XEL"],
        user_query="分析 utilities 的 data center power load 和 AI infrastructure demand transmission",
        sector_depth_pack_path=sector_path,
        max_relationships=12,
    )
    refs = {ref for row in result["relationships"] for ref in row["evidence_refs"]}

    assert result["status"] == "ok"
    assert any("sector_depth_pack:real_estate_utilities_depth" in ref for ref in refs)
    assert any("sector_depth_pack:technology_ai_infrastructure_depth" in ref for ref in refs)


def test_expected_sector_depth_pack_filters_cross_sector_matches(tmp_path: Path) -> None:
    sector_path = tmp_path / "sector_depth.yaml"
    sector_path.write_text(_cross_sector_pack_yaml(), encoding="utf-8")

    result = query_relationship_graph(
        focus_tickers=["NVDA"],
        search_scope_tickers=["NVDA", "DELL", "ANET", "VRT"],
        user_query="AI infrastructure demand and energy infrastructure readthrough",
        sector_depth_pack_path=sector_path,
        expected_pack_ids=["technology_ai_infrastructure_depth"],
        max_relationships=12,
    )
    refs = {ref for row in result["relationships"] for ref in row["evidence_refs"]}

    assert result["status"] == "ok"
    assert refs
    assert all("sector_depth_pack:technology_ai_infrastructure_depth" in ref for ref in refs)


def test_mcp_registry_invokes_relationship_graph_lookup(tmp_path: Path) -> None:
    graph_path = tmp_path / "relationships.jsonl"
    graph_path.write_text(
        json.dumps(
            {
                "ticker": "AMD",
                "related_ticker": "NVDA",
                "relationship_type": "competitor",
                "evidence_refs": ["rel_amd_nvda"],
                "inclusion_rationale": "GPU peer hypothesis.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke_mcp_tool(
        "relationship_graph_lookup",
        {
            "focus_tickers": ["AMD"],
            "relationship_graph_path": str(graph_path),
            "include_sector_depth": False,
        },
    )

    assert result["status"] == "ok"
    assert result["relationships"][0]["related_ticker"] == "NVDA"
    assert result["summary"]["claim_scope"] == "scope_or_hypothesis_only"


def _cross_sector_pack_yaml() -> str:
    return """
packs:
  - pack_id: "technology_ai_infrastructure_depth"
    industry_group: "information_technology"
    research_questions:
      - "AI infrastructure demand transmission from chips to servers, networking, power, cooling, and software."
    candidate_tickers:
      p0: ["VRT"]
      p1: ["ETN"]
    primary_metric_families:
      - "capex"
    required_source_families:
      - "industry_utilities_power_demand"

  - pack_id: "energy_infrastructure_depth"
    industry_group: "energy"
    research_questions:
      - "Commodity price sensitivity, production, capex discipline, oilfield services orders, LNG, and midstream volumes."
    candidate_tickers:
      p0: ["OXY", "HAL"]
      p1: ["LNG"]
    primary_metric_families:
      - "production"
    required_source_families:
      - "industry_energy_commodities"

  - pack_id: "real_estate_utilities_depth"
    industry_group: "real_estate_utilities"
    research_questions:
      - "Rates, data-center demand, power load growth, regulated returns, and generation mix."
    candidate_tickers:
      p0: ["SRE", "XEL"]
      p1: ["ED"]
    primary_metric_families:
      - "electric_load"
    required_source_families:
      - "industry_housing_real_estate_power"
"""
