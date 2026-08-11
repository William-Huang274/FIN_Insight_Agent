from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_r17_known_public_product_kpi_repair_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_r17_known_public_product_kpi_repair_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_parse_deck_brand_net_sales_uses_first_fy_block_only() -> None:
    text = """
    UGG® brand net sales increased 13.1% to $2.531 billion compared to $2.239 billion.
    HOKA® brand net sales increased 23.6% to $2.233 billion compared to $1.807 billion.
    Other brands net sales decreased 8.6% to $221.2 million compared to $241.9 million.
    UGG® brand net sales increased 3.6% to $374.3 million compared to $361.3 million.
    HOKA® brand net sales increased 10.0% to $586.1 million compared to $533.0 million.
    """

    rows = MODULE.parse_deck_brand_net_sales_rows(
        text=text,
        raw_path=Path("deck.html"),
        generated_at="2026-06-22T00:00:00Z",
    )

    by_brand = {row["product_or_segment"]: row for row in rows}
    assert set(by_brand) == {"UGG", "HOKA", "Other brands"}
    assert by_brand["UGG"]["value"] == 2_531_000_000
    assert by_brand["HOKA"]["value"] == 2_233_000_000
    assert by_brand["Other brands"]["value"] == 221_200_000
    assert by_brand["Other brands"]["growth_pct"] == -8.6
    assert all(row["product_node_type"] == "category_or_brand_family" for row in rows)
    assert all(row["runtime_action"] == "promote_product_kpi_exact" for row in rows)


def test_known_public_summary_requires_hoka_and_ugg() -> None:
    rows = MODULE.parse_deck_brand_net_sales_rows(
        text=(
            "UGG® brand net sales increased 13.1% to $2.531 billion compared to $2.239 billion. "
            "HOKA® brand net sales increased 23.6% to $2.233 billion compared to $1.807 billion."
        ),
        raw_path=Path("deck.html"),
        generated_at="2026-06-22T00:00:00Z",
    )

    summary = MODULE.build_summary(
        rows=rows,
        generated_at="2026-06-22T00:00:00Z",
        output_rows=Path("rows.jsonl"),
    )

    assert summary["status"] == "pass"
    assert summary["runtime_row_count"] == 2
    assert summary["brands"] == ["HOKA", "UGG"]
