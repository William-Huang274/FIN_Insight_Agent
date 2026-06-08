from __future__ import annotations

import importlib.util
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "eval_retrieval" / "eval_milvus_multi_query_batch_probe.py"
_SPEC = importlib.util.spec_from_file_location("eval_milvus_multi_query_batch_probe", _MODULE_PATH)
assert _SPEC and _SPEC.loader
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


def test_case_probes_add_ai_investment_lenses() -> None:
    case = {
        "case_id": "nvda_scope",
        "category": "scope_decision",
        "prompt": "Analyze NVIDIA fundamental performance and AI infrastructure durability.",
        "search_scope_tickers": ["NVDA", "MSFT", "DELL", "ANET", "VRT"],
        "metric_families": ["revenue", "gross_margin", "cash_flow"],
    }

    probes = probe._case_probes(case, max_probes=10, query_expansion=True)
    joined = " ".join(probes).lower()

    assert probes[0].startswith("Analyze NVIDIA")
    assert "cloud capex demand" in joined
    assert "memory hbm foundry" in joined
    assert "server networking power downstream" in joined
    assert "export control" in joined
    assert len(probes) <= 10


def test_merge_query_hit_lists_preserves_query_and_vector_support() -> None:
    hit_lists = [
        [
            {
                "distance": 0.9,
                "entity": {
                    "evidence_id": "NVDA_ITEM7",
                    "ticker": "NVDA",
                    "vector_kind": "paraphrase_context",
                    "preview": "AI infrastructure demand",
                },
            }
        ],
        [
            {
                "distance": 0.8,
                "entity": {
                    "evidence_id": "NVDA_ITEM7",
                    "ticker": "NVDA",
                    "vector_kind": "relationship_context",
                    "preview": "Demand transmission",
                },
            },
            {
                "distance": 0.7,
                "entity": {
                    "evidence_id": "DELL_ITEM7",
                    "ticker": "DELL",
                    "vector_kind": "narrative_chunk",
                    "preview": "Server demand",
                },
            },
        ],
    ]

    merged = probe._merge_query_hit_lists(hit_lists, top_k=3)

    by_id = {row["evidence_id"]: row for row in merged}
    assert by_id["NVDA_ITEM7"]["matched_query_indices"] == [0, 1]
    assert by_id["NVDA_ITEM7"]["vector_kinds"] == ["paraphrase_context", "relationship_context"]
    assert by_id["DELL_ITEM7"]["matched_query_indices"] == [1]


def test_summary_sets_gpu_index_room_signal_for_batchable_workload() -> None:
    results = [
        {
            "case_id": "case1",
            "probe_count": 6,
            "gate_status": "pass",
            "timings": {
                "sequential_search_ms": {"median": 900},
                "batch_search_ms": {"median": 400},
                "sequential_encode_ms": {"median": 600},
                "batch_encode_ms": {"median": 300},
            },
            "speedups": {"search_batch_vs_sequential": 2.25, "encode_batch_vs_sequential": 2.0},
            "batch": {"ticker_coverage_count": 3, "vector_kind_counts": {"relationship_context": 2}},
        }
    ]
    args = probe.parse_args(
        [
            "--milvus-uri",
            "milvus.db",
            "--collection-name",
            "collection",
            "--embedding-model",
            "model",
        ]
    )

    summary = probe._summarize(
        results,
        run_id="run",
        elapsed_ms=123,
        args=args,
        device="cuda",
        vector_kinds=["relationship_context"],
        resource_before={},
        resource_after={},
    )

    assert summary["gate_status"] == "pass"
    assert summary["aggregate"]["gpu_index_room_signal"] is True
