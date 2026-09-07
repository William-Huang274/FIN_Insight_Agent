from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from scripts.qualification.agent_server_wave0b.fin_wave0b_probe.graphs import (
    approval_builder,
    counter_builder,
    parallel_graph,
)
from scripts.qualification.agent_server_wave0b.probe_agent_server import (
    execution_windows_overlap,
    require_qualification_root,
    summarize_sse,
)


def test_counter_fixture_preserves_state_across_runs_on_one_thread() -> None:
    graph = counter_builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "wave0b-counter"}}

    first = graph.invoke({"case_id": "DELL", "delta": 2, "total": 0}, config)
    second = graph.invoke({"delta": 3}, config)

    assert first["total"] == 2
    assert second["total"] == 5


def test_approval_fixture_interrupts_and_resumes_on_same_thread() -> None:
    graph = approval_builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "wave0b-approval"}}

    interrupted = graph.invoke(
        {
            "case_id": "DELL",
            "proposed_action": {
                "action": "publish_candidate",
                "digest": "sha256:wave0b-fixture",
            },
        },
        config,
    )
    resumed = graph.invoke(
        Command(resume={"approved": True, "reviewer": "fixture"}), config
    )

    assert interrupted["__interrupt__"][0].value["kind"] == "fin_exact_action_approval"
    assert resumed["result"] == {
        "approved": True,
        "disposition": "execute_allowed",
    }


def test_parallel_fixture_branches_really_overlap() -> None:
    result = asyncio.run(
        parallel_graph.ainvoke(
            {"case_id": "DELL", "branch_duration_seconds": 0.5}
        )
    )

    assert result["completed"] is True
    assert len(result["branch_windows"]) == 2
    assert execution_windows_overlap(
        result["branch_windows"][0], result["branch_windows"][1]
    )


def test_sse_summary_keeps_ids_and_digests_but_not_payload() -> None:
    payload = (
        "event: metadata\n"
        'data: {"run_id":"safe-fixture"}\n'
        "id: 10-0\n\n"
        "event: values\n"
        'data: {"answer":"fixture"}\n'
        "id: 11-0\n\n"
    )

    summary = summarize_sse(payload)

    assert [event["id"] for event in summary] == ["10-0", "11-0"]
    assert [event["event"] for event in summary] == ["metadata", "values"]
    assert all("answer" not in str(event) for event in summary)
    assert all(len(event["data_sha256"]) == 64 for event in summary)


def test_qualification_output_rejects_paths_outside_frozen_z_root(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="output path must stay below"):
        require_qualification_root(tmp_path)
