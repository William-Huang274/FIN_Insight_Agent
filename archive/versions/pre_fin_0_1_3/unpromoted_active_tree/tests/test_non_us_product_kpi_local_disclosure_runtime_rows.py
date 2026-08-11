from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_non_us_product_kpi_local_disclosure_runtime_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_non_us_product_kpi_local_disclosure_runtime_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _parse(text: str, ticker: str, fiscal_year: int = 2025) -> list[dict]:
    return MODULE.parse_product_kpi_rows(
        text=text,
        ticker=ticker,
        candidate={"ticker": ticker, "fiscal_year": fiscal_year},
        generated_at="2026-06-19T00:00:00Z",
    )


def test_kr_hynix_segment_revenue_promotes_krw_millions() -> None:
    rows = _parse(
        """
        (나) 공시대상 사업부문의 구분 [제78기] (단위: 백만원)
        구분 매출액 매출액 비중 주요제품
        반도체 부문 97,146,675 100.0% DRAM, NAND Flash 등
        합계 97,146,675 100.0% -
        """,
        "000660.KS",
    )

    assert len(rows) == 1
    assert rows[0]["product_or_segment"] == "반도체 부문 (DRAM, NAND Flash 등)"
    assert rows[0]["value"] == 97146675000000.0
    assert rows[0]["unit"] == "KRW"


def test_samsung_major_product_sales_promotes_segment_rows() -> None:
    rows = _parse(
        """
        (단위 : 억원, %) 부 문 주요 제품 매출액 비중
        DX 부문 TV, 모니터, 냉장고, 세탁기, 에어컨,스마트폰, 네트워크시스템, PC 등 1,879,673 56.3%
        DS 부문 DRAM, NAND Flash, 모바일AP 등 1,301,282 39.0%
        SDC 스마트폰용 OLED패널 등 298,417 8.9%
        Harman 디지털 콕핏, 카오디오, 포터블 스피커 등 157,833 4.7%
        기타 부문간 내부거래 제거 등 △301,146 △8.9%
        총 계 3,336,059 100.00% ※ 각 부문별 매출액은 부문 등 간 내부거래를 포함하고 있습니다.
        """,
        "005930.KS",
    )

    by_segment = {row["product_or_segment"].split(" ", 1)[0]: row for row in rows}
    assert len(rows) == 4
    assert by_segment["DX"]["value"] == 187967300000000.0
    assert by_segment["DS"]["unit"] == "KRW"


def test_byd_segment_revenue_promotes_external_revenue_only() -> None:
    rows = _parse(
        """
        RMB’000
        Mobile handset components, assembly and other products Automobiles and related products and other products
        Adjustments and eliminations Total 2025 二零二五年
        Revenue from external trading 對外交易收入 155,236,528 648,645,636 82,794 803,964,958
        Revenue from inter-segment trading 分部間交易收入 26,342,005 3,836,361 (30,178,366) –
        """,
        "1211.HK",
    )

    assert len(rows) == 2
    assert rows[0]["value"] == 155236528000.0
    assert rows[1]["value"] == 648645636000.0


def test_catl_product_revenue_and_margin_promotes_exact_rows() -> None:
    rows = _parse(
        """
        单位：千元 项目 2025年 2024年 同比增减 金额 占营业收入比重 金额 占营业收入比重
        分产品 动力电池系统 316,506,369 74.70% 253,041,337 69.90% 25.08%
        储能电池系统 62,439,820 14.74% 57,290,460 15.83% 8.99%
        单位：千元 项目 营业收入 营业成本 毛利率
        分产品 动力电池系统 316,506,369 241,064,397 23.84% 25.08% 25.25% -0.10%
        储能电池系统 62,439,820 45,763,689 26.71% 8.99% 9.18% -0.13%
        """,
        "300750.SZ",
    )

    families = {(row["product_or_segment"], row["metric_family"]): row for row in rows}
    assert families[("动力电池系统", "product_revenue")]["value"] == 316506369000.0
    assert families[("动力电池系统", "product_gross_margin")]["value"] == 23.84
    assert families[("储能电池系统", "product_gross_margin")]["unit"] == "PERCENT"


def test_infineon_panasonic_and_advantest_segment_sales() -> None:
    infineon = _parse(
        """
        Revenue by segment 14,662 14,955 (2)
        Automotive 7,402 50 7,716 52 (4)
        Green Industrial Power 1,631 11 1,934 13 (16)
        Power & Sensor Systems 4,208 29 3,795 25 11
        Connected Secure Systems 1,418 10 1,506 10 (6)
        Selected results of operations key data Gross profit/Gross margin
        """,
        "IFX.DE",
    )
    panasonic = _parse(
        "Lifestyle 3,584.2 Energy 873.2 Industry 1,083.6 Connect 1,333.2 Sales ¥7,785.0 billion",
        "6752.T",
    )
    advantest = _parse(
        "Net Sales 779.7 billion yen 682.8 billion yen Test System Business 96.9 billion yen Services and Others",
        "6857.T",
    )

    assert {row["product_or_segment"] for row in infineon} == {
        "Automotive",
        "Green Industrial Power",
        "Power & Sensor Systems",
        "Connected Secure Systems",
    }
    assert panasonic[0]["value"] == 3584200000000.0
    assert advantest[0]["product_or_segment"] == "Test System Business"
    assert advantest[0]["value"] == 682800000000.0


def test_tw_mops_product_sales_volume_value_promotes_product_region_rows() -> None:
    rows = _parse(
        """
        數量單位：千台/千片/千個 金額單位：新台幣千元 年度 銷售量值 主要產品
        113 年度 114 年度 內銷 外銷 內銷 外銷 銷量 銷值 銷量 銷值 銷量 銷值 銷量 銷值
        3C 電子產品 1,391 26,350,581 61,477 982,384,829 1,357 17,875,582 64,677 2,136,717,476
        其他產品 225 786,166 3,169 39,734,205 301 1,323,070 428 30,606,508
        """,
        "3231.TW",
    )

    by_key = {(row["product_or_segment"], row["metric_family"]): row for row in rows}
    assert by_key[("3C electronic products (export)", "product_revenue")]["value"] == 2136717476000.0
    assert by_key[("3C electronic products (export)", "shipments")]["value"] == 64677000.0
    assert by_key[("other products (domestic)", "product_revenue")]["unit"] == "TWD"


def test_quanta_notebook_shipments_promotes_absolute_units_only() -> None:
    rows = _parse(
        "2025年AI伺服器營業額翻倍，帶動公司全年合併營收再創新高；筆記型電腦年出貨量達4,650萬台，較2024年小幅成長1.3%。",
        "2382.TW",
    )

    assert len(rows) == 1
    assert rows[0]["product_or_segment"] == "notebook computers"
    assert rows[0]["metric_family"] == "shipments"
    assert rows[0]["value"] == 46500000.0


def test_disco_shipment_value_promotes_with_product_context() -> None:
    rows = _parse(
        """
        shipments of precision processing equipment centered on high value-added products remained strong,
        and shipments of precision processing tools (consumables) also remained at a high level.
        As a result, both the full-year shipment value and sales reached a record high.
        Shipment value – 442.824 billion yen
        """,
        "6146.T",
    )

    assert len(rows) == 1
    assert rows[0]["product_or_segment"] == "precision processing equipment and tools"
    assert rows[0]["metric_family"] == "shipment_value"
    assert rows[0]["value"] == 442824000000.0


def test_lges_official_news_promotes_exact_order_backlog_without_thresholds() -> None:
    rows = _parse(
        """
        The company expanded its ESS battery order backlog to approximately 120GWh (as of the end of Q3 2025).
        It also won 107GWh in new contracts for its 46-Series cylindrical batteries from leading automakers.
        The order backlog for 46-Series cylindrical batteries exceeds 300GWh.
        """,
        "373220.KS",
    )

    by_product = {row["product_or_segment"]: row for row in rows}
    assert len(rows) == 2
    assert by_product["ESS batteries"]["metric_family"] == "backlog_or_orders"
    assert by_product["ESS batteries"]["value"] == 120.0
    assert by_product["ESS batteries"]["unit"] == "GWH"
    assert by_product["46-Series cylindrical batteries"]["metric_name"] == "new contracts"
    assert by_product["46-Series cylindrical batteries"]["value"] == 107.0


def test_stale_document_reason_detects_old_integrated_report() -> None:
    reason = MODULE._stale_document_reason("TOKYO ELECTRON Integrated Report 2021", {"fiscal_year": 2025})

    assert reason == "stale_document_year_mismatch"


def test_runtime_row_satisfies_exact_slot_contract_shape() -> None:
    parsed = _parse(
        "Revenue by segment 14,662 14,955 (2) Automotive 7,402 50 7,716 52 (4) Selected results of operations",
        "IFX.DE",
    )[0]
    row = MODULE._runtime_row(
        parsed,
        candidate={
            "ticker": "IFX.DE",
            "company_name": "Infineon Technologies AG",
            "source_url": "https://example.com/ifx.pdf",
            "cleaned_text_path": "ifx.txt",
            "fiscal_year": 2025,
        },
        company_by_ticker={},
        generated_at="2026-06-19T00:00:00Z",
    )

    assert row["source_id"] == "company_reported_product_operating_metrics"
    assert row["parser_status"] == "value_unit_period_product_citation_parser_pass"
    assert row["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert row["product_binding_status"] == "product_mentioned_in_snapshot"
