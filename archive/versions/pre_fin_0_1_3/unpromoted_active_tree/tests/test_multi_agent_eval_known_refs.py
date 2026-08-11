from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_eval_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "eval_multi_agent" / "eval_multi_agent_real_llm_chain.py"
    spec = importlib.util.spec_from_file_location("eval_multi_agent_real_llm_chain_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_specialist_eval_known_refs_include_role_visible_packs() -> None:
    module = _load_eval_module()

    refs = module._known_data_view_refs(
        {
            "fundamental_statement_pack": {
                "statement_line_items": [
                    {
                        "line_item_id": "line_1",
                        "evidence_refs": ["pack_ref_1"],
                        "source_fact_id": "source_fact_1",
                    }
                ],
                "integration_bridges": [{"evidence_ref": "__mcp__::DELL::2026::product_revenue::total_value::ai_optimized_servers"}],
            },
            "product_spec_pack_ref": {
                "product_kpi_refs": [{"evidence_refs": ["product_ref_1"]}],
                "commercial_gaps": [{"gap_id": "commercial_gap_1"}],
            },
        },
        [{"evidence_ref": "bounded_ref_1", "source_id": "source_1"}],
    )

    assert "bounded_ref_1" in refs
    assert "pack_ref_1" in refs
    assert "source_fact_1" in refs
    assert "__mcp__::DELL::2026::product_revenue::total_value::ai_optimized_servers" in refs
    assert "product_ref_1" in refs
    assert "commercial_gap_1" in refs
