from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts" / "eval_multi_agent"
SRC_ROOT = REPO_ROOT / "src"
for root in (SCRIPT_DIR, SRC_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import eval_multi_agent_coverage_reflection_gate as s4  # noqa: E402
import eval_multi_agent_evidence_operator_gate as s3  # noqa: E402
import eval_multi_agent_judgment_memo_gate as s6  # noqa: E402
import eval_multi_agent_specialist_layer_gate as s5  # noqa: E402


def test_s3_summary_roundtrips_expanded_runtime_paths_to_s4_args(tmp_path: Path) -> None:
    args = argparse.Namespace(
        activation_summary=tmp_path / "activation.json",
        relationship_summary=tmp_path / "relationship.json",
        manifest_path=Path("data/expanded_manifest.jsonl"),
        bm25_index_dir=Path("indexes/bm25_expanded"),
        object_bm25_index_dir=Path("indexes/object_bm25_expanded"),
        ledger_store_path=Path("ledger/expanded.duckdb"),
        market_evidence_path=Path("market/evidence.jsonl"),
        market_catalog_path=Path("market/catalog.duckdb"),
        industry_evidence_path=Path("industry/evidence.jsonl"),
        industry_snapshot_db_path=Path("industry/snapshot.duckdb"),
        milvus_db_path=Path("milvus/milvus_lite.db"),
        milvus_collection_name="fin_ab_expanded",
        milvus_vector_kinds="relationship_context,paraphrase_context",
        milvus_top_k=32,
        embedding_model="BAAI/bge-m3",
        sector_depth_pack_path=Path("configs/sector_depth.yaml"),
        market_snapshot_id="market_v2",
        market_as_of_date="2026-06-06",
        bge_model=Path("models/bge-reranker"),
        bge_device="cuda",
        context_runner="in_process",
        reranker_candidate_limit=480,
        reranker_top_k=120,
    )

    summary = s3._aggregate(
        run_id="unit_s3",
        args=args,
        activation_summary={"run_id": "unit_s1"},
        relationship_summary={"run_id": "unit_s2"},
        cases=[],
        scores=[],
        elapsed_sec=0.0,
        output_dir=tmp_path,
    )

    restored = s4._s3_args_from_summary(summary)

    assert restored.market_catalog_path == Path("market/catalog.duckdb")
    assert restored.industry_snapshot_db_path == Path("industry/snapshot.duckdb")
    assert restored.milvus_db_path == Path("milvus/milvus_lite.db")
    assert restored.milvus_collection_name == "fin_ab_expanded"
    assert restored.milvus_vector_kinds == "relationship_context,paraphrase_context"
    assert restored.milvus_top_k == 32
    assert restored.embedding_model == "BAAI/bge-m3"
    assert restored.market_snapshot_id == "market_v2"
    assert restored.market_as_of_date == "2026-06-06"


def test_s3_relationship_artifact_root_falls_back_when_summary_output_dir_is_stale(tmp_path: Path) -> None:
    summary_path = tmp_path / "relationship_diagnostic.json"
    summary_path.write_text("{}", encoding="utf-8")

    root = s3._summary_artifact_root(
        {"output_dir": r"D:\FIN_Insight_Agent\eval\sec_cases\outputs\stale_run"},
        summary_path,
    )

    assert root == tmp_path


def test_s5_artifact_roots_fall_back_when_summary_output_dirs_are_stale(tmp_path: Path) -> None:
    relationship_path = tmp_path / "s2" / "universe_relationship_diagnostic.json"
    evidence_path = tmp_path / "s3" / "evidence_operator_diagnostic.json"
    coverage_path = tmp_path / "s4" / "coverage_reflection_diagnostic.json"
    for path in (relationship_path, evidence_path, coverage_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    args = argparse.Namespace(
        relationship_summary=relationship_path,
        evidence_summary=evidence_path,
        coverage_summary=coverage_path,
    )

    roots = s5._input_artifact_roots(
        args,
        relationship_summary={"output_dir": str(tmp_path / "missing_s2")},
        evidence_summary={"output_dir": str(tmp_path / "missing_s3")},
        coverage_summary={"output_dir": str(tmp_path / "missing_s4")},
    )

    assert roots == {
        "relationship": relationship_path.parent,
        "evidence": evidence_path.parent,
        "coverage": coverage_path.parent,
    }


def test_s6_artifact_roots_fall_back_when_summary_output_dirs_are_stale(tmp_path: Path) -> None:
    specialist_path = tmp_path / "s5" / "specialist_layer_diagnostic.json"
    relationship_path = tmp_path / "s2" / "universe_relationship_diagnostic.json"
    evidence_path = tmp_path / "s3" / "evidence_operator_diagnostic.json"
    coverage_path = tmp_path / "s4" / "coverage_reflection_diagnostic.json"
    for path in (specialist_path, relationship_path, evidence_path, coverage_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    specialist_summary = {
        "output_dir": str(tmp_path / "missing_s5"),
        "relationship_summary": str(relationship_path),
        "evidence_summary": str(evidence_path),
        "coverage_summary": str(coverage_path),
    }
    summary_paths = s6._summary_paths_from_specialist_summary(specialist_summary)
    args = argparse.Namespace(specialist_summary=specialist_path)

    roots = s6._input_artifact_roots(
        args,
        specialist_summary=specialist_summary,
        relationship_summary={"output_dir": str(tmp_path / "missing_s2")},
        evidence_summary={"output_dir": str(tmp_path / "missing_s3")},
        coverage_summary={"output_dir": str(tmp_path / "missing_s4")},
        summary_paths=summary_paths,
    )

    assert roots == {
        "specialist": specialist_path.parent,
        "relationship": relationship_path.parent,
        "evidence": evidence_path.parent,
        "coverage": coverage_path.parent,
    }
