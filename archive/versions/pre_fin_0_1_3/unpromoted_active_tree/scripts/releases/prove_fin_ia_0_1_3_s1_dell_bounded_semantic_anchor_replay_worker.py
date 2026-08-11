from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys


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


def _raises_code(callable_object: object, expected_code: str) -> bool:
    try:
        callable_object()  # type: ignore[operator]
    except (BoundedSemanticAnchorError, DellBoundedSemanticAnchorReplayError) as exc:
        return exc.code == expected_code
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()
    policy = load_dell_bounded_semantic_anchor_replay_policy(
        POLICY_PATH, repo_root=ROOT
    )
    result = execute_dell_bounded_semantic_anchor_replay(
        policy=policy,
        repo_root=ROOT,
        runtime_root=args.runtime_root / "real_capture_replay",
        observed_at="2026-08-10T20:00:00Z",
        execution_commit=args.implementation_commit,
    )

    prefix = ("demand and supply navigation noise. " * 900) + "\n"
    cluster = (
        "In Q1, we booked $24.4 billion in AI orders and recognized revenue. "
        "We exited with $51.3 billion of AI backlog. Demand continues to exceed "
        "supply with memory as the primary constraint."
    )
    tail = ("supply and demand appendix noise. " * 900) + "$24.4 billion in AI orders"
    long_text = prefix + cluster + tail
    start, end, receipt = compile_bounded_semantic_anchor_window(
        long_text,
        required_anchor_groups=_groups(
            "$24.4 billion in AI orders",
            "$51.3 billion of AI backlog",
            "Demand continues to exceed supply",
        ),
        max_anchor_span=800,
    )

    unsafe = deepcopy(policy)
    unsafe["replay_routes"][0]["fragments"][0]["required_patterns"] = [
        "demand.*exceed.*supply"
    ]
    unsafe_path = args.runtime_root / "unsafe-policy.json"
    unsafe_path.parent.mkdir(parents=True, exist_ok=True)
    unsafe_path.write_text(json.dumps(unsafe), encoding="utf-8")

    mutations = {
        "legacy_unbounded_regex_surface_rejected_statically": _raises_code(
            lambda: load_dell_bounded_semantic_anchor_replay_policy(
                unsafe_path, repo_root=ROOT
            ),
            "pattern_occurrence_unbounded",
        ),
        "long_document_duplicate_and_tail_noise_selects_local_cluster": (
            receipt["anchor_window_chars"] < 300
            and long_text[start:end].startswith("$24.4 billion")
            and end < len(prefix) + len(cluster) + 10
        ),
        "missing_anchor_is_typed_separately": _raises_code(
            lambda: compile_bounded_semantic_anchor_window(
                "first anchor only",
                required_anchor_groups=_groups("first anchor", "second anchor"),
                max_anchor_span=300,
            ),
            "anchor_missing:group_2",
        ),
        "wide_business_window_is_typed_separately": _raises_code(
            lambda: compile_bounded_semantic_anchor_window(
                "first anchor " + ("x" * 1000) + " second anchor",
                required_anchor_groups=_groups("first anchor", "second anchor"),
                max_anchor_span=300,
            ),
            "multi_anchor_window_too_wide",
        ),
        "oversized_final_excerpt_is_typed_separately": _raises_code(
            lambda: extract_bounded_semantic_excerpt(
                "Sentence first anchor and second anchor. " + ("tail " * 100),
                required_anchor_groups=_groups("first anchor", "second anchor"),
                before=0,
                after=200,
                max_anchor_span=300,
                max_excerpt_chars=50,
            ),
            "final_excerpt_too_large",
        ),
        "historical_failed_result_preserved": (
            result["historical_failed_result_digest"]
            == "9be7ec13c20b97dd9a2d58a936078fb3135008110fc33bf413a15d2a9fe18920"
        ),
        "actual_long_captures_replayed_without_network": (
            result["observed_counts"]["immutable_response_captures_replayed"] == 2
            and result["observed_counts"]["network_calls"] == 0
            and all(
                row["capture_reused"] is True and row["new_network_call"] is False
                for row in result["route_results"]
            )
        ),
    }
    if not all(mutations.values()):
        raise RuntimeError("bounded_semantic_anchor_worker_mutation_failed")
    output = {
        "status": "pass",
        "result_digest": result["result_digest"],
        "corrected_pack_payload_digest": result["corrected_pack_payload_digest"],
        "observed_counts": result["observed_counts"],
        "gate_status": result["gate_status"],
        "stage_acceptance": result["stage_acceptance"],
        "route_results": result["route_results"],
        "mutations": mutations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
