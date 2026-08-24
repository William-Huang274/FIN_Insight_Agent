from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from retrieval.quantized_shadow import (
    QUANTIZED_MANIFEST_NAME,
    QUANTIZED_MANIFEST_SCHEMA,
    TOOL_MANIFEST_NAME,
    TOOL_MANIFEST_SCHEMA,
    compile_controlled_ranking_metrics,
    compile_quantized_shadow_decision,
    llama_cpp_tool_identity,
    quantized_gguf_identity,
)
from scripts.data_retrieval.acquire_s1_quantized_4b_shadow_assets import (
    _safe_extract_zip,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(root: Path) -> None:
    model = root / "model.Q4_K_M.gguf"
    readme = root / "README.md"
    model.write_bytes(b"quantized-weights")
    readme.write_text("bounded shadow", encoding="utf-8")
    manifest = {
        "schema_version": QUANTIZED_MANIFEST_SCHEMA,
        "repo_id": "Qwen/example-GGUF",
        "resolved_revision": "a" * 40,
        "source_model_id": "Qwen/example",
        "quantization": "Q4_K_M",
        "acquisition_tool": "huggingface_hub.snapshot_download",
        "selected_model_file": model.name,
        "files": [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": _sha(path)}
            for path in (readme, model)
        ],
    }
    (root / QUANTIZED_MANIFEST_NAME).write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def test_quantized_identity_binds_exact_recursive_closure(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    _write_manifest(root)

    identity = quantized_gguf_identity(
        root,
        expected_repo_id="Qwen/example-GGUF",
        expected_revision="a" * 40,
        expected_source_model_id="Qwen/example",
        expected_quantization="Q4_K_M",
    )

    assert identity["selected_model_file"]["path"] == "model.Q4_K_M.gguf"
    assert len(identity["model_digest"]) == 64


def test_quantized_identity_rejects_unmanifested_file(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    _write_manifest(root)
    (root / "remote_code.py").write_text("pass", encoding="utf-8")

    with pytest.raises(
        ValueError, match="quantized_shadow_acquisition_manifest_file_set_mismatch"
    ):
        quantized_gguf_identity(
            root,
            expected_repo_id="Qwen/example-GGUF",
            expected_revision="a" * 40,
            expected_source_model_id="Qwen/example",
            expected_quantization="Q4_K_M",
        )


def test_llama_tool_identity_binds_server_and_full_closure(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    server = root / "llama-server.exe"
    runtime = root / "cudart64_12.dll"
    server.write_bytes(b"server")
    runtime.write_bytes(b"runtime")
    manifest = {
        "schema_version": TOOL_MANIFEST_SCHEMA,
        "tool_id": "ggml-org/llama.cpp",
        "release_tag": "b10516",
        "server_relative_path": server.name,
        "files": [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": _sha(path)}
            for path in (runtime, server)
        ],
    }
    (root / TOOL_MANIFEST_NAME).write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    identity = llama_cpp_tool_identity(
        root,
        expected_release_tag="b10516",
        expected_server_relative_path="llama-server.exe",
    )

    assert identity["server_relative_path"] == "llama-server.exe"
    assert len(identity["tool_digest"]) == 64


def test_safe_zip_extraction_rejects_parent_escape(tmp_path: Path) -> None:
    archive = tmp_path / "hostile.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../outside.dll", b"hostile")

    with pytest.raises(ValueError, match="quantized_acquisition_unsafe_zip_member"):
        _safe_extract_zip(archive, tmp_path / "destination")

    assert not (tmp_path / "outside.dll").exists()


def _metrics(scores: tuple[float, float, float]) -> dict:
    return compile_controlled_ranking_metrics(
        [
            {
                "query_id": "q1",
                "case_key": "DELL",
                "candidates": [
                    {"candidate_id": "p", "label": "positive", "score": scores[0]},
                    {
                        "candidate_id": "n1",
                        "label": "hard_negative",
                        "score": scores[1],
                    },
                    {
                        "candidate_id": "n2",
                        "label": "hard_negative",
                        "score": scores[2],
                    },
                ],
            },
            {
                "query_id": "q2",
                "case_key": "MU",
                "candidates": [
                    {"candidate_id": "p2", "label": "positive", "score": 0.9},
                    {
                        "candidate_id": "n3",
                        "label": "hard_negative",
                        "score": 0.1,
                    },
                ],
            },
            {
                "query_id": "q3",
                "case_key": "NVDA",
                "candidates": [
                    {"candidate_id": "p3", "label": "positive", "score": 0.8},
                    {
                        "candidate_id": "n4",
                        "label": "hard_negative",
                        "score": 0.2,
                    },
                ],
            },
        ]
    )


def test_controlled_metrics_compute_all_positive_negative_pairs() -> None:
    metrics = _metrics((0.5, 0.6, 0.4))

    assert metrics["overall"]["pairwise_comparisons"] == 4
    assert metrics["overall"]["pairwise_accuracy"] == 0.75
    assert metrics["overall"]["top1_positive_rate"] == pytest.approx(2 / 3, 1e-6)
    assert metrics["overall"]["critical_error_query_ids"] == ["q1"]


@pytest.mark.parametrize("bad_score", [float("nan"), float("inf")])
def test_controlled_metrics_reject_non_finite_scores(bad_score: float) -> None:
    with pytest.raises(ValueError, match="quantized_shadow_metric_candidate_invalid"):
        compile_controlled_ranking_metrics(
            [
                {
                    "query_id": "q1",
                    "case_key": "DELL",
                    "candidates": [
                        {"candidate_id": "p", "label": "positive", "score": bad_score}
                    ],
                }
            ]
        )


def test_shadow_decision_never_authorizes_runtime_or_s1() -> None:
    baseline = _metrics((0.5, 0.6, 0.4))
    challenger = _metrics((0.9, 0.6, 0.4))

    decision = compile_quantized_shadow_decision(
        baseline_embedding=baseline,
        challenger_embedding=challenger,
        baseline_reranker=baseline,
        challenger_reranker=challenger,
        gates={
            "embedding_pairwise_accuracy_minimum": 0.8,
            "reranker_pairwise_accuracy_minimum": 0.8,
            "reranker_pairwise_improvement_minimum": 0.05,
        },
    )

    assert decision["runtime_promotion_authorized"] is False
    assert decision["S1_qualification_authorized"] is False
    assert decision["natural_candidate_recall_proved"] is False
