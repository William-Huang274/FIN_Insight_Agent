from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_official_product_surface_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_official_product_surface_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_official_product_surface_context_rows_from_materialized_html(tmp_path: Path) -> None:
    raw_path = tmp_path / "product.html"
    raw_path.write_text(
        """
        <html>
          <head><title>Test Product - TestCo</title></head>
          <body>
            <h1>Test Accelerator X100</h1>
            <p>TestCo introduces the Test Accelerator X100 with 192GB memory and high-throughput inference.</p>
            <table>
              <tr><th>Model</th><th>Memory</th></tr>
              <tr><td>X100</td><td>192GB</td></tr>
            </table>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    rows = MODULE.build_official_product_surface_context_rows(
        [
            {
                "ticker": "TST",
                "company": "TestCo Inc.",
                "product": "Test Accelerator X100",
                "source_url": "https://www.testco.example/products/x100",
                "raw_path": str(raw_path),
                "title": "Test Product - TestCo",
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        max_rows_per_page=8,
    )

    assert rows
    assert {row["source_id"] for row in rows} == {"company_product_pages"}
    assert {row["source_layer_id"] for row in rows} == {"L2"}
    assert all(row["exact_value_authority"] is False for row in rows)
    assert any(row["structured_context_type"] == "product_spec_context" for row in rows)
    assert any(row["product_binding_status"] == "product_mentioned_in_snapshot" for row in rows)
    assert any(row["issuer_binding_status"] == "company_domain_bound" for row in rows)


def test_official_product_surface_context_rows_cli_writes_runtime_gate(tmp_path: Path) -> None:
    raw_path = tmp_path / "product.html"
    raw_path.write_text(
        "<html><title>Alpha Product</title><body>Alpha Product includes 64GB memory and launch availability.</body></html>",
        encoding="utf-8",
    )
    input_path = tmp_path / "pages.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "ticker": "ALP",
                "company": "Alpha Corp.",
                "product": "Alpha Product",
                "source_url": "https://www.alpha.example/products/alpha",
                "raw_path": str(raw_path),
                "title": "Alpha Product",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    source_layer_path = tmp_path / "source_layer.jsonl"
    source_layer_path.write_text(
        "\n".join(
            [
                json.dumps(_source("sec_edgar_apis", "L1", "exact_authority_ready", exact=True)),
                json.dumps(_source("company_product_pages", "L2", "structured_not_promoted")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output_rows = tmp_path / "rows.jsonl"
    output_summary = tmp_path / "summary.json"
    output_gate = tmp_path / "gate.json"

    exit_code = MODULE.main_with_args if hasattr(MODULE, "main_with_args") else None
    assert exit_code is None
    result = _run_cli_like(
        input_path=input_path,
        source_layer_path=source_layer_path,
        output_rows=output_rows,
        output_summary=output_summary,
        output_gate=output_gate,
    )

    assert result["parser_backed_row_count"] > 0
    assert result["official_product_surface_requirement"]["status"] == "pass"


def _run_cli_like(*, input_path: Path, source_layer_path: Path, output_rows: Path, output_summary: Path, output_gate: Path) -> dict:
    page_rows = MODULE._load_jsonl(input_path)
    context_rows = MODULE.build_official_product_surface_context_rows(
        page_rows,
        generated_at="2026-06-16T00:00:00Z",
        max_rows_per_page=8,
    )
    source_layer_rows = MODULE._load_jsonl(source_layer_path)
    coverage = MODULE.build_source_coverage_gate(
        industry_schema="generic_public_research",
        phase="runtime_case",
        source_layer_capability={"rows": source_layer_rows},
        observed_rows=context_rows,
        specialist_visible_rows={"product_technology_analyst": context_rows},
        required_dimensions=["product_and_production"],
        generated_at="2026-06-16T00:00:00Z",
    )
    summary = MODULE.build_summary(
        page_rows=page_rows,
        context_rows=context_rows,
        coverage_gate=coverage,
        generated_at="2026-06-16T00:00:00Z",
        output_rows=output_rows,
        output_coverage=output_gate,
    )
    MODULE._write_jsonl(output_rows, context_rows)
    MODULE._write_json(output_summary, summary)
    MODULE._write_json(output_gate, coverage)
    return summary


def _source(source_id: str, layer_id: str, status: str, *, exact: bool = False) -> dict[str, object]:
    return {
        "source_id": source_id,
        "layer_id": layer_id,
        "evidence_graph_status": status,
        "runtime_ready_context": status in {"runtime_ready_context", "exact_authority_ready"},
        "exact_value_authority_ready": exact,
        "can_support_company_exact_fact": exact,
        "can_crawl_or_download": True,
        "can_structure": True,
    }
