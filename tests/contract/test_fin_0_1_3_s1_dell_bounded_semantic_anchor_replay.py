from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.bounded_semantic_anchor import (  # noqa: E402
    BoundedSemanticAnchorError,
    compile_bounded_semantic_anchor_window,
    extract_bounded_semantic_excerpt,
)
from sec_agent.s1_dell_bounded_semantic_anchor_replay import (  # noqa: E402
    DellBoundedSemanticAnchorReplayError,
    execute_dell_bounded_semantic_anchor_replay,
    load_dell_bounded_semantic_anchor_replay_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_dell_bounded_semantic_anchor_replay_policy_v1_0.json"
)


def _groups(*values: str) -> list[dict[str, object]]:
    return [
        {"group_id": f"group_{index}", "literal_phrases": [value]}
        for index, value in enumerate(values, start=1)
    ]


def test_real_immutable_captures_materialize_all_five_fragments(
    tmp_path: Path,
) -> None:
    policy = load_dell_bounded_semantic_anchor_replay_policy(
        POLICY_PATH, repo_root=ROOT
    )
    result = execute_dell_bounded_semantic_anchor_replay(
        policy=policy,
        repo_root=ROOT,
        runtime_root=tmp_path / "runtime",
        observed_at="2026-08-10T20:00:00Z",
        execution_commit="0" * 40,
    )
    assert result["gate_status"] == {
        "core_research_ready": True,
        "supplier_context_ready": True,
        "valuation_input_ready": True,
        "valuation_ready": True,
        "successor_pack_ready_for_model_input": True,
    }
    assert result["observed_counts"] == {
        "network_calls": 0,
        "model_calls": 0,
        "retries": 0,
        "immutable_response_captures_replayed": 2,
        "new_source_materials": 5,
        "new_evidence_items": 5,
        "evidence_items_before": 22,
        "evidence_items_after": 27,
        "residual_gaps_before": 15,
        "residual_gaps_after": 14,
        "reused_numeric_facts": 1,
    }
    assert all(
        route["status"] == "capture_replayed_and_all_fragments_adjudicated"
        and route["capture_reused"] is True
        and route["new_network_call"] is False
        for route in result["route_results"]
    )


def test_long_document_duplicate_and_tail_noise_choose_local_business_cluster() -> None:
    prefix = ("demand and supply navigation noise. " * 900) + "\n"
    cluster = (
        "In Q1, we booked $24.4 billion in AI orders and recognized revenue. "
        "We exited with $51.3 billion of AI backlog. Demand continues to exceed "
        "supply with memory as the primary constraint."
    )
    tail = ("supply and demand appendix noise. " * 900) + "$24.4 billion in AI orders"
    text = prefix + cluster + tail
    start, end, receipt = compile_bounded_semantic_anchor_window(
        text,
        required_anchor_groups=_groups(
            "$24.4 billion in AI orders",
            "$51.3 billion of AI backlog",
            "Demand continues to exceed supply",
        ),
        max_anchor_span=800,
    )
    assert text[start:end].startswith("$24.4 billion")
    assert "$51.3 billion" in text[start:end]
    assert receipt["anchor_window_chars"] < 300
    assert end < len(prefix) + len(cluster) + 10


def test_reordered_noise_does_not_join_unrelated_anchors() -> None:
    text = (
        "Demand continues to exceed supply. "
        + ("unrelated appendix " * 400)
        + "$24.4 billion in AI orders. "
        + ("other company backlog " * 400)
        + "$51.3 billion of AI backlog."
    )
    with pytest.raises(
        BoundedSemanticAnchorError, match="multi_anchor_window_too_wide"
    ):
        compile_bounded_semantic_anchor_window(
            text,
            required_anchor_groups=_groups(
                "$24.4 billion in AI orders",
                "$51.3 billion of AI backlog",
                "Demand continues to exceed supply",
            ),
            max_anchor_span=800,
        )


def test_failure_codes_separate_missing_wide_and_final_excerpt() -> None:
    with pytest.raises(BoundedSemanticAnchorError, match="anchor_missing:group_2"):
        compile_bounded_semantic_anchor_window(
            "first anchor only",
            required_anchor_groups=_groups("first anchor", "second anchor"),
            max_anchor_span=300,
        )
    with pytest.raises(
        BoundedSemanticAnchorError, match="multi_anchor_window_too_wide"
    ):
        compile_bounded_semantic_anchor_window(
            "first anchor " + ("x" * 1000) + " second anchor",
            required_anchor_groups=_groups("first anchor", "second anchor"),
            max_anchor_span=300,
        )
    with pytest.raises(
        BoundedSemanticAnchorError, match="final_excerpt_too_large"
    ):
        extract_bounded_semantic_excerpt(
            "Sentence start first anchor and second anchor. " + ("tail " * 100),
            required_anchor_groups=_groups("first anchor", "second anchor"),
            before=0,
            after=200,
            max_anchor_span=300,
            max_excerpt_chars=50,
        )


def test_successor_policy_statically_rejects_legacy_regex_surface(
    tmp_path: Path,
) -> None:
    policy = deepcopy(json.loads(POLICY_PATH.read_text(encoding="utf-8")))
    policy["replay_routes"][0]["fragments"][0]["required_patterns"] = [
        "demand.*exceed.*supply"
    ]
    path = tmp_path / "unsafe-policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(
        DellBoundedSemanticAnchorReplayError,
        match="pattern_occurrence_unbounded",
    ):
        load_dell_bounded_semantic_anchor_replay_policy(path, repo_root=ROOT)


def test_capture_digest_mutation_fails_before_replay(tmp_path: Path) -> None:
    policy = deepcopy(json.loads(POLICY_PATH.read_text(encoding="utf-8")))
    policy["immutable_bindings"]["response_captures"][0]["sha256"] = "0" * 64
    path = tmp_path / "mutated-policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(
        DellBoundedSemanticAnchorReplayError,
        match="bounded_anchor_binding_invalid:response_capture",
    ):
        load_dell_bounded_semantic_anchor_replay_policy(path, repo_root=ROOT)
