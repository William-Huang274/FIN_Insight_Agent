from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m2_6_evidence_slot_policy_fixture.py"
SPEC = importlib.util.spec_from_file_location("point01_m2_6_fixture", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_four_sector_issuer_slots_compile_to_ready_policy() -> None:
    compiler = RUNNER._compiler()
    for sector in ("ai_semis", "saas", "healthcare", "banks"):
        result = compiler.compile(
            sector=sector,
            slots=(RUNNER._slot("issuer", "issuer_metric", "issuer_first", "primary", ("relationship_graph_only",)),),
            available_parser_source_policy_refs=("issuer_first",),
        )
        assert result.status == "pass"
        assert result.compiled_slots[0].resolution_status == "ready"


def test_parser_and_commercial_gaps_are_typed_not_silent_substitutions() -> None:
    compiler = RUNNER._compiler()
    parser_gap = compiler.compile(
        sector="ai_semis",
        slots=(RUNNER._slot("parser", "issuer_metric", "filing_first", "primary", ("relationship_graph_only",)),),
        available_parser_source_policy_refs=(),
    )
    assert parser_gap.status == "pass_with_typed_gaps"
    assert parser_gap.gaps[0].gap_type == "parser_gap"
    commercial_gap = compiler.compile(
        sector="banks",
        slots=(RUNNER._slot("commercial", "commercial_tracker_metric", "commercial_gap", "primary_or_bounded_context", ("public_proxy_as_exact",)),),
        available_parser_source_policy_refs=(),
    )
    assert commercial_gap.status == "pass_with_typed_gaps"
    assert commercial_gap.gaps[0].gap_type == "commercial_data_gap"


def test_relationship_overreach_fails_closed() -> None:
    result = RUNNER._compiler().compile(
        sector="saas",
        slots=(RUNNER._slot("relationship", "relationship_signal", "relationship_graph_only", "primary", ("issuer_metric_substitute",)),),
        available_parser_source_policy_refs=(),
    )
    assert result.status == "fail"
    assert "relationship_scope_overreach:relationship" in result.errors


def test_m2_6_machine_fixture_is_replayable_and_model_free(tmp_path) -> None:
    output = tmp_path / "m2_6_policy.json"
    completed = subprocess.run([sys.executable, str(RUNNER_PATH), "--output", str(output)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["checks"]["relationship_overreach_rejected"] is True
