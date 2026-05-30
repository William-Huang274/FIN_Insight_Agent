from __future__ import annotations

import json
from pathlib import Path

from sec_agent.workbench import profile_from_env_file, validate_profile_sources
from sec_agent.workbench.profiles import SourceArtifactsProfile, WorkbenchProfile, parse_env_file


def test_profile_from_env_file_maps_public_runtime_values_without_secret(tmp_path: Path) -> None:
    env_file = tmp_path / "full_source.env"
    env_file.write_text(
        "\n".join(
            [
                "export LLM_BACKEND=openai_compatible",
                'BASE_URL="https://example.test/v1"',
                "MODEL_NAME=demo-model",
                "API_KEY_ENV=DEMO_API_KEY",
                "DEMO_API_KEY=redacted-do-not-copy",
                "QUERY_PLANNER=llm",
                "BGE_MODEL=/models/bge-reranker-v2-m3",
                "BGE_DEVICE=cpu # local smoke",
                "SEC_AGENT_SOURCE_POLICY=SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
                "MANIFEST_PATH=data/private/manifest.jsonl",
                "BM25_INDEX_DIR=data/indexes/demo",
                "OBJECT_BM25_INDEX_DIR=data/indexes/demo_objects",
                "MARKET_EVIDENCE_PATH=data/private/market.jsonl",
                "MARKET_AS_OF_DATE=2026-05-22",
                "WORKBENCH_EXECUTION_SHELL=wsl",
                "WORKBENCH_WSL_DISTRO=Ubuntu-22.04",
                "WORKBENCH_WSL_REPO_ROOT=/mnt/d/FIN_Insight_Agent",
            ]
        ),
        encoding="utf-8",
    )

    parsed = parse_env_file(env_file)
    profile = profile_from_env_file(env_file, profile_id="demo")
    runtime_env = profile.to_runtime_env()

    assert parsed["BASE_URL"] == "https://example.test/v1"
    assert parsed["BGE_DEVICE"] == "cpu"
    assert profile.model_route.backend == "openai_compatible"
    assert profile.model_route.api_key_env == "DEMO_API_KEY"
    assert profile.sources.market_as_of_date == "2026-05-22"
    assert profile.runtime.bge_model == "/models/bge-reranker-v2-m3"
    assert profile.runtime.execution_shell == "wsl"
    assert profile.runtime.wsl_distro == "Ubuntu-22.04"
    assert profile.runtime.wsl_repo_root == "/mnt/d/FIN_Insight_Agent"
    assert runtime_env["API_KEY_ENV"] == "DEMO_API_KEY"
    assert runtime_env["BGE_MODEL"] == "/models/bge-reranker-v2-m3"
    assert "DEMO_API_KEY" not in runtime_env
    assert "redacted-do-not-copy" not in json.dumps(profile.model_dump(), ensure_ascii=False)


def test_source_readiness_passes_for_complete_full_source_fixture(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    market = tmp_path / "market.jsonl"
    bm25_dir = tmp_path / "bm25"
    object_dir = tmp_path / "object_bm25"
    bm25_dir.mkdir()
    object_dir.mkdir()
    _write_jsonl(
        manifest,
        [
            {
                "ticker": "NVDA",
                "fiscal_year": 2025,
                "form_type": "10-K",
                "source_tier": "primary_sec_filing",
                "period_role": "annual",
            },
            {
                "ticker": "NVDA",
                "fiscal_year": 2026,
                "form_type": "10-Q",
                "source_tier": "primary_sec_filing",
                "period_role": "QTD",
            },
            {
                "ticker": "NVDA",
                "fiscal_year": 2026,
                "form_type": "8-K",
                "source_tier": "company_authored_unaudited_sec_filing",
                "period_role": "current",
            },
        ],
    )
    _write_jsonl(
        market,
        [
            {
                "ticker": "NVDA",
                "snapshot_id": "snap_v1",
                "as_of_date": "2026-05-22",
                "provider": "fixture",
                "field_refs": [{"field_name": field, "value": 1.0} for field in _required_market_fields()],
            }
        ],
    )
    profile = WorkbenchProfile(
        profile_id="complete",
        display_name="complete",
        sources=SourceArtifactsProfile(
            source_policy="SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
            manifest_path=str(manifest),
            bm25_index_dir=str(bm25_dir),
            object_bm25_index_dir=str(object_dir),
            market_evidence_path=str(market),
        ),
    )

    report = validate_profile_sources(profile, repo_root=tmp_path, require_full_source=True)

    assert report.status == "pass"
    assert report.manifest.form_counts == {"10-K": 1, "10-Q": 1, "8-K": 1}
    assert report.manifest.period_counts["QTD"] == 1
    assert report.market_evidence.field_counts["pe_ttm"] == 1
    assert report.missing_required_forms == []
    assert report.missing_market_fields == []


def test_source_readiness_warns_for_missing_configured_artifacts(tmp_path: Path) -> None:
    profile = WorkbenchProfile(
        profile_id="missing",
        display_name="missing",
        sources=SourceArtifactsProfile(
            source_policy="SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
            manifest_path="missing/manifest.jsonl",
            bm25_index_dir="missing/bm25",
            object_bm25_index_dir="missing/object_bm25",
            market_evidence_path="missing/market.jsonl",
        ),
    )

    report = validate_profile_sources(profile, repo_root=tmp_path)
    path_statuses = {item.name: item.status for item in report.paths}

    assert report.status == "warn"
    assert path_statuses["manifest"] == "warn"
    assert path_statuses["bm25_index"] == "warn"
    assert path_statuses["object_bm25_index"] == "warn"
    assert path_statuses["market_evidence"] == "warn"
    assert report.errors == []


def test_source_readiness_fails_on_malformed_required_jsonl(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    bm25_dir = tmp_path / "bm25"
    object_dir = tmp_path / "object_bm25"
    bm25_dir.mkdir()
    object_dir.mkdir()
    manifest.write_text("{bad json\n", encoding="utf-8")
    profile = WorkbenchProfile(
        profile_id="bad",
        display_name="bad",
        sources=SourceArtifactsProfile(
            source_policy="SEC_PRIMARY_MIXED_RECENT",
            manifest_path=str(manifest),
            bm25_index_dir=str(bm25_dir),
            object_bm25_index_dir=str(object_dir),
        ),
    )

    report = validate_profile_sources(profile, repo_root=tmp_path)

    assert report.status == "fail"
    assert report.manifest.parse_errors
    assert "manifest:" in report.errors[0]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _required_market_fields() -> list[str]:
    return [
        "close_price",
        "market_cap",
        "return_3m",
        "relative_return_vs_benchmark_3m",
        "max_drawdown_3m",
        "volatility_3m",
        "pe_ttm",
        "ev_sales_ttm",
        "latest_10q_filing_return_5d",
    ]
