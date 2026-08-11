from __future__ import annotations

import importlib.util
from pathlib import Path


MATERIALIZER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "materialize_official_spec_source_pages.py"
)
MAT_SPEC = importlib.util.spec_from_file_location("materialize_official_spec_source_pages", MATERIALIZER_PATH)
MAT = importlib.util.module_from_spec(MAT_SPEC)
assert MAT_SPEC and MAT_SPEC.loader
MAT_SPEC.loader.exec_module(MAT)

PARSER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_official_product_spec_context_rows.py"
)
PARSER_SPEC = importlib.util.spec_from_file_location("build_official_product_spec_context_rows_for_materializer_test", PARSER_PATH)
PARSER = importlib.util.module_from_spec(PARSER_SPEC)
assert PARSER_SPEC and PARSER_SPEC.loader
PARSER_SPEC.loader.exec_module(PARSER)


class _FakeResponse:
    status_code = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, text: str) -> None:
        self.text = text
        self.content = text.encode("utf-8")


def test_materialized_official_spec_page_can_feed_product_spec_parser(monkeypatch, tmp_path: Path) -> None:
    html = (
        "<html><head><title>NVIDIA H100 Specifications</title></head><body>"
        "NVIDIA H100 SXM GPU Memory 80 GB and GPU Memory Bandwidth 3.35 TB/s. "
        "FP8 Tensor Core performance reaches 1979 teraFLOPS. "
        + "This official product specification page contains detailed architecture context. " * 8
        + "</body></html>"
    )

    def fake_get(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return _FakeResponse(html)

    monkeypatch.setattr(MAT.requests, "get", fake_get)
    result = MAT.materialize_official_spec_source_pages(
        candidates=[
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA Corporation",
                "company": "NVIDIA Corporation",
                "route_id": "technical_product_spec",
                "source_role": "technical_product_spec",
                "source_id": "official_product_spec_pages",
                "family_id": "gpu_accelerator",
                "family_name": "GPU / Accelerator",
                "product": "H100 SXM",
                "candidate_url": "https://www.nvidia.com/en-us/data-center/h100/specifications/",
                "locator_score": 9,
            }
        ],
        existing_rows=[],
        raw_dir=tmp_path / "raw",
        clean_dir=tmp_path / "clean",
        generated_at="2026-06-25T00:00:00Z",
        workers=1,
        min_clean_text_chars=100,
    )
    assert result["summary"]["materialized_count"] == 1
    page_rows = result["rows"]
    assert page_rows[0]["materialization_status"] == "live_fetch_materialized"
    assert Path(page_rows[0]["clean_text_path"]).exists()

    spec_rows, diagnostics = PARSER.build_official_product_spec_context_rows(
        page_rows=page_rows,
        generated_at="2026-06-25T00:00:00Z",
    )
    assert diagnostics["candidate_count"] >= 2
    assert spec_rows
    assert {row["runtime_contract"] for row in spec_rows} == {"ProductSpecSlot"}
    assert all(row["source_role"] == "technical_product_spec" for row in spec_rows)
