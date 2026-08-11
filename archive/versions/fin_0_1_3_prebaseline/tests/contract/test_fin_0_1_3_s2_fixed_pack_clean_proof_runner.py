from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / (
    "scripts/releases/prove_fin_ia_0_1_3_s2_fixed_pack_successor_clean.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("fixed_pack_clean_proof", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_proves_all_six_fixture_chains_without_network_or_model() -> None:
    result = _module().run_worker(execution_git_commit="3" * 40)
    assert [row["case_key"] for row in result["case_results"]] == [
        "DELL",
        "MU",
        "NVDA",
        "ORCL",
        "ASML",
        "ANET",
    ]
    assert result["observed_counts"] == {
        "cases": 6,
        "fixture_provider_calls": 78,
        "request_captures": 78,
        "response_captures": 78,
        "real_provider_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    assert all(
        row["status"] == "completed"
        and row["request_captures"] == 13
        and row["response_captures"] == 13
        and row["same_input_pair_proven"] is True
        and row["business_artifact_promoted"] is False
        for row in result["case_results"]
    )
