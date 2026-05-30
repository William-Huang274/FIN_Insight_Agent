from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.ledger_store import query_ledger_facts, write_ledger_store  # noqa: E402


def _load_interactive_module():
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_ledger_store_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_ledger_store_rehydrates_case_scoped_metric_ids(tmp_path: Path) -> None:
    store_path = tmp_path / "ledger.duckdb"
    write_ledger_store([_fact_row(case_id="store_case")], store_path)

    rows = query_ledger_facts(
        store_path,
        case_id="case_live",
        tickers=["NVDA"],
        years=[2026],
        filing_types=["10-Q"],
        metric_families=["revenue"],
    )

    assert len(rows) == 1
    assert rows[0]["case_id"] == "case_live"
    assert rows[0]["metric_id"].startswith("case_live::NVDA::2026::revenue::total_value")
    assert rows[0]["value"] == 12000.0


def test_runtime_ledger_uses_duckdb_store_without_object_records(tmp_path: Path) -> None:
    interactive = _load_interactive_module()
    store_path = tmp_path / "ledger.duckdb"
    write_ledger_store([_fact_row(case_id="store_case")], store_path)
    case = {
        "case_id": "case_live",
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "query_contract": {
            "focus_tickers": ["NVDA"],
            "ledger_rules": {
                "allowed_metric_families": ["revenue"],
                "prefer_focus_tickers": True,
            },
        },
    }
    context_rows = [
        {
            "source_kind": "structured_object",
            "object_id": "obj_nvda_revenue",
            "ticker": "NVDA",
            "fiscal_year": 2026,
            "form_type": "10-Q",
        }
    ]
    args = Namespace(ledger_store_path=str(store_path), object_bm25_index_dir="missing", ledger_max_rows=10)

    rows = interactive._build_runtime_ledger(case, context_rows, args)

    assert len(rows) == 1
    assert rows[0]["metric_id"].startswith("case_live::")
    assert rows[0]["object_id"] == "obj_nvda_revenue"


def _fact_row(*, case_id: str) -> dict:
    return {
        "metric_id": f"{case_id}::NVDA::2026::revenue::total_value::qtd",
        "case_id": case_id,
        "ticker": "NVDA",
        "fiscal_year": 2026,
        "source_fiscal_year": 2026,
        "period": "2026",
        "period_role": "qtd",
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "metric_family": "revenue",
        "metric_role": "total_value",
        "metric_name": "Revenue",
        "raw_value_text": "$12,000",
        "display_value_zh": "12,000（百万美元）",
        "value": 12000.0,
        "unit": "usd_millions",
        "object_id": "obj_nvda_revenue",
        "source_evidence_id": "NVDA_2026_10Q_ITEM2",
        "section": "Item 2",
        "source_text": "Revenue was $12,000 million.",
    }
