from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import subprocess
from types import ModuleType
from typing import Any
from uuid import UUID

import pytest
from langgraph_sdk.schema import StreamPart


ROOT = Path(__file__).resolve().parents[1]
R8_DIRECTORY = ROOT / "scripts/qualification/agent_server_r8"


def _load(name: str, path: Path) -> ModuleType:
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def live_phase() -> ModuleType:
    return _load("fin_test_r8_live_phase", R8_DIRECTORY / "live_phase.py")


@pytest.fixture(scope="module")
def host_runner() -> ModuleType:
    return _load("fin_test_r8_host_runner", R8_DIRECTORY / "qualify_live_r8.py")


def test_r8_manifest_round_trips_all_canonical_identities(
    host_runner: ModuleType,
    live_phase: ModuleType,
) -> None:
    manifest = host_runner._manifest(
        "20260904T030000+0800-zero-model-r8-test",
        "a" * 40,
    )

    loaded = live_phase._load_manifest
    # Exercise the validator without changing production stdin handling.
    assert manifest["schema_version"] == live_phase.MANIFEST_SCHEMA_VERSION
    session, research_run, start, resume = live_phase._manifest_contracts(manifest)

    assert session.session_id == research_run.session_id
    assert start.run_id == resume.run_id == research_run.run_id
    assert (start.ordinal, start.invocation_kind) == (1, "START")
    assert (resume.ordinal, resume.invocation_kind) == (2, "RESUME")
    assert manifest["graph_input"]["run_id"] == research_run.run_id
    assert session.as_of_date.isoformat() == manifest["graph_input"][
        "research_as_of"
    ][:10]
    assert session.data_snapshot_ref.endswith(
        manifest["graph_input"]["snapshot_id"]
    )
    assert session.data_snapshot_digest == (
        host_runner.DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST
    )
    assert manifest["resume_payload"]["action"] == (
        "complete_zero_model_qualification"
    )
    assert loaded is not None


def test_r8_preflight_normalizes_windows_git_path_style(
    host_runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "b" * 40

    def fake_git(args: list[str]) -> str:
        if args == ["rev-parse", "--show-toplevel"]:
            return str(host_runner.ROOT).replace("\\", "/")
        if args == ["branch", "--show-current"]:
            return host_runner.EXPECTED_BRANCH
        if args == ["status", "--porcelain"]:
            return ""
        if args == ["rev-parse", "HEAD"]:
            return commit
        raise AssertionError(args)

    monkeypatch.setattr(host_runner, "_git", fake_git)
    monkeypatch.setattr(host_runner, "_project_container_ids", lambda _env: [])
    monkeypatch.setattr(host_runner, "_volume_exists", lambda _env: False)
    monkeypatch.setattr(host_runner, "_port_is_available", lambda: True)

    assert host_runner._preflight({}) == commit


def test_r8_safe_output_rejects_content_and_secret_surfaces(
    live_phase: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_phase._require_safe_output({"phase": "safe", "digest": "a" * 64})

    with pytest.raises(live_phase.LivePhaseError) as path_failure:
        live_phase._require_safe_output({"path": "Z:/private/source.json"})
    assert path_failure.value.code == "r8_safe_output_contains_forbidden_content"

    monkeypatch.setenv("LANGSMITH_API_KEY", "test-secret-value-never-persist")
    with pytest.raises(live_phase.LivePhaseError) as secret_failure:
        live_phase._require_safe_output(
            {"value": "test-secret-value-never-persist"}
        )
    assert secret_failure.value.code == "r8_safe_output_contains_secret"


def test_r8_safe_state_accepts_only_the_bounded_zero_model_projection(
    live_phase: ModuleType,
) -> None:
    summary: dict[str, Any] = {
        "schema_version": "fin_ia_dell_zero_model_graph_qualification_v1_0",
        "branch_id": "Q1_ISSUER_TRUTH",
        "route_id": "route:Q1_ISSUER_TRUTH:required-reviewed",
        "task_id": "task:q1",
        "plan_digest": "a" * 64,
        "evidence_status": "success",
        "evidence_result_states": ["reviewed_evidence"],
        "evidence_item_count": 1,
        "evidence_result_digest": "b" * 64,
        "evidence_lane_receipt_id": "receipt:evidence",
        "finance_status": "success",
        "finance_result_states": ["numeric_fact"],
        "finance_item_count": 1,
        "finance_result_digest": "c" * 64,
        "finance_lane_receipt_id": "receipt:finance",
        "tool_lane_execution_count": 2,
        "mcp_call_count": 2,
        "mcp_error_call_count": 0,
        "mcp_tool_call_counts": {"evidence.search": 1, "finance.lookup": 1},
        "model_call_count": 0,
        "live_external_research_call_count": 0,
        "paid_call_count": 0,
    }
    raw = {
        "values": {
            "execution_profile": "zero_model_control_plane_v1",
            "phase": "zero_model_mcp_qualified",
            "final_report": None,
            "zero_model_qualification_summary": summary,
            "zero_model_qualification_decision": None,
        },
        "interrupts": [
            {
                "value": {
                    "kind": "dell_zero_model_control_plane_qualification",
                    "schema_version": "v1",
                }
            }
        ],
        "next": ["qualification_interrupt"],
        "metadata": {},
        "tasks": [],
    }

    safe = live_phase._safe_state(
        raw,
        expected_phase="zero_model_mcp_qualified",
    )

    assert safe["phase"] == "zero_model_mcp_qualified"
    assert safe["qualification_summary"]["mcp_call_count"] == 2
    serialized = json.dumps(safe, ensure_ascii=False)
    assert "source_url" not in serialized
    assert "value_decimal" not in serialized


def test_r8_stream_projection_accepts_normal_eof_and_rejects_internal_end(
    live_phase: ModuleType,
) -> None:
    projected = live_phase._stream_projection(
        [
            StreamPart(event="metadata", data={"safe": True}, id="1-0"),
            StreamPart(event="updates", data={"safe": True}, id="2-0"),
        ]
    )
    assert [row["event"] for row in projected] == ["metadata", "updates"]

    with pytest.raises(live_phase.LivePhaseError) as exc_info:
        live_phase._stream_projection(
            [
                StreamPart(event="end", data={}),
                StreamPart(event="updates", data={"safe": True}, id="2-0"),
            ]
        )
    assert exc_info.value.code == "r8_stream_end_not_terminal"


def test_r8_orchestrator_has_no_cleanup_or_model_execution_path() -> None:
    source = (R8_DIRECTORY / "qualify_live_r8.py").read_text(encoding="utf-8")
    phase_source = (R8_DIRECTORY / "live_phase.py").read_text(encoding="utf-8")

    assert '"down"' not in source
    assert "down -v" not in source
    assert "docker volume rm" not in source
    assert 'child["DEEPSEEK_API_KEY"]' not in source
    assert '"DEEPSEEK_API_KEY":' not in source
    assert "planner_agent(" not in phase_source
    assert "specialist_agent(" not in phase_source
    assert "lead_agent(" not in phase_source
    assert '"canonical_sha256": _digest(manifest)' in source
    assert '"file_sha256": _file_sha256(manifest_path)' in source
    assert '"receipt_file_sha256": _file_sha256(receipt_path)' in source


def test_r8_failed_child_preserves_content_minimised_observation(
    host_runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = subprocess.CompletedProcess(
        ["safe-probe"],
        2,
        stdout=b'{"failure_code":"r8_test_typed_failure"}\n',
        stderr=b"diagnostic body is hashed, not persisted",
    )
    monkeypatch.setattr(
        host_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: completed,
    )

    with pytest.raises(host_runner.QualificationSubprocessError) as exc_info:
        host_runner._run(
            ["safe-probe"],
            environment={},
            phase_json=True,
        )

    assert exc_info.value.code == "r8_test_typed_failure"
    assert exc_info.value.parsed == {"failure_code": "r8_test_typed_failure"}
    assert exc_info.value.observation["returncode"] == 2
    assert "diagnostic body" not in json.dumps(exc_info.value.observation)


def test_r8_host_requires_exact_restart_replay_and_trace_identity(
    host_runner: ModuleType,
) -> None:
    start_binding = {
        "run_invocation_id": "invocation-start",
        "server_run_id": str(UUID(int=401)),
    }
    resume_binding = {
        "run_invocation_id": "invocation-resume",
        "server_run_id": str(UUID(int=402)),
    }
    interrupted = {
        "assistant_uuid": str(UUID(int=403)),
        "manifest_sha256": "a" * 64,
        "session": {"server_thread_id": str(UUID(int=404))},
        "bindings": {"start": start_binding},
        "identity": {"invocation_count": 1},
        "remote": {"runs": [{"status": "interrupted"}]},
        "stream": {"full_digest": "b" * 64, "suffix_digest": "c" * 64},
        "state": {
            "raw_state_sha256": "d" * 64,
            "qualification_summary_sha256": "e" * 64,
        },
        "observed_calls": {"model_provider_calls": 0},
    }
    completed = deepcopy(interrupted)
    completed["bindings"] = {
        "start": start_binding,
        "resume": resume_binding,
    }
    completed["identity"] = {"invocation_count": 2}
    completed["remote"] = {
        "runs": [{"status": "interrupted"}, {"status": "success"}]
    }
    completed["stream"] = {
        "full_digest": "f" * 64,
        "suffix_digest": "0" * 64,
    }
    completed["state"] = {
        "raw_state_sha256": "1" * 64,
        "qualification_summary_sha256": "e" * 64,
    }
    phases = {
        "start": deepcopy(interrupted),
        "api_readback": deepcopy(interrupted),
        "redis_readback": deepcopy(interrupted),
        "full_stack_readback": deepcopy(interrupted),
        "resume": deepcopy(completed),
        "final": deepcopy(completed),
        "langsmith": {
            "manifest_sha256": "a" * 64,
            "traces": [
                {
                    "run_invocation_id": "invocation-start",
                    "trace_id": str(UUID(int=401)),
                    "root_run_id": str(UUID(int=401)),
                },
                {
                    "run_invocation_id": "invocation-resume",
                    "trace_id": str(UUID(int=402)),
                    "root_run_id": str(UUID(int=402)),
                },
            ],
        },
    }

    host_runner._assert_cross_phase_continuity(phases)

    drifted = deepcopy(phases)
    drifted["redis_readback"]["stream"]["suffix_digest"] = "9" * 64
    with pytest.raises(host_runner.QualificationError) as exc_info:
        host_runner._assert_cross_phase_continuity(drifted)
    assert exc_info.value.code == "r8_interrupted_restart_continuity_mismatch"


def test_r8_langsmith_waits_for_complete_stable_trace_span_sets(
    host_runner: ModuleType,
    live_phase: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = host_runner._manifest(
        "20260904T030000+0800-zero-model-r8-langsmith",
        "a" * 40,
    )
    session, research_run, start, resume = live_phase._manifest_contracts(manifest)
    observed_at = datetime(2026, 9, 4, tzinfo=timezone.utc)

    class FakeRun:
        def __init__(
            self,
            *,
            run_id: int,
            trace_id: int,
            parent_run_id: int | None,
            dotted_order: str,
            name: str,
            run_type: str,
            invocation_id: str | None = None,
        ) -> None:
            self.id = UUID(int=run_id)
            self.trace_id = UUID(int=trace_id)
            self.parent_run_id = (
                None if parent_run_id is None else UUID(int=parent_run_id)
            )
            self.dotted_order = dotted_order
            self.name = name
            self.run_type = run_type
            self.start_time = observed_at
            self.end_time = observed_at
            self.error = None
            self.inputs = {}
            self.outputs = {}
            self.extra = {
                "metadata": {"run_invocation_id": invocation_id}
                if invocation_id is not None
                else {}
            }
            self.tags = []
            self.events = []
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.total_tokens = 0
            self.total_cost = 0

        def model_dump(self, *, mode: str) -> dict[str, Any]:
            assert mode == "json"
            return {
                "id": str(self.id),
                "trace_id": str(self.trace_id),
                "parent_run_id": (
                    None
                    if self.parent_run_id is None
                    else str(self.parent_run_id)
                ),
                "dotted_order": self.dotted_order,
                "name": self.name,
                "run_type": self.run_type,
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "error": self.error,
                "inputs": self.inputs,
                "outputs": self.outputs,
                "extra": self.extra,
                "tags": self.tags,
                "events": self.events,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
                "total_cost": self.total_cost,
            }

    start_root = FakeRun(
        run_id=201,
        trace_id=201,
        parent_run_id=None,
        dotted_order="1",
        name="qualification_start",
        run_type="chain",
        invocation_id=start.invocation_id,
    )
    start_child = FakeRun(
        run_id=202,
        trace_id=201,
        parent_run_id=201,
        dotted_order="1.1",
        name="evidence_tool",
        run_type="tool",
    )
    resume_root = FakeRun(
        run_id=203,
        trace_id=203,
        parent_run_id=None,
        dotted_order="2",
        name="qualification_resume",
        run_type="chain",
        invocation_id=resume.invocation_id,
    )
    resume_child = FakeRun(
        run_id=204,
        trace_id=203,
        parent_run_id=203,
        dotted_order="2.1",
        name="checkpoint_resume",
        run_type="chain",
    )
    for root, invocation in ((start_root, start), (resume_root, resume)):
        root.extra["metadata"].update(
            {
                "fin_client_schema_version": (
                    live_phase.DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION
                ),
                "execution_profile": live_phase.ZERO_MODEL_EXECUTION_PROFILE,
                "agent_session_id": session.session_id,
                "research_run_id": research_run.run_id,
                "session_identity_digest": live_phase.agent_session_identity_digest(
                    session
                ),
                "research_run_identity_digest": (
                    live_phase.research_run_identity_digest(research_run)
                ),
                "run_invocation_identity_digest": (
                    live_phase.run_invocation_identity_digest(invocation)
                ),
            }
        )
    by_trace = {
        str(start_root.trace_id): [start_root, start_child],
        str(resume_root.trace_id): [resume_root, resume_child],
    }

    class FakeLangSmithClient:
        def __init__(self, *, auto_batch_tracing: bool) -> None:
            assert auto_batch_tracing is False
            self.span_calls = {trace_id: 0 for trace_id in by_trace}

        def list_runs(self, **kwargs: Any) -> Any:
            assert tuple(kwargs["select"]) == live_phase._LANGSMITH_RUN_SELECT
            if kwargs.get("is_root") is True:
                assert set(map(str, kwargs["run_ids"])) == set(by_trace)
                return iter([start_root, resume_root])
            trace_id = str(kwargs["trace_id"])
            self.span_calls[trace_id] += 1
            rows = by_trace[trace_id]
            # The first query deliberately sees only the root.  The audit must
            # wait for the child and then observe the same complete set twice.
            return iter(rows[:1] if self.span_calls[trace_id] == 1 else rows)

    fake_client = FakeLangSmithClient(auto_batch_tracing=False)
    monkeypatch.setattr(live_phase, "_require_container_environment", lambda: "x")
    monkeypatch.setattr(
        live_phase,
        "_durable_server_run_ids",
        lambda _uri, _run, _ids: {
            start.invocation_id: str(start_root.id),
            resume.invocation_id: str(resume_root.id),
        },
    )
    monkeypatch.setattr(live_phase, "LangSmithClient", lambda **_kwargs: fake_client)
    monkeypatch.setattr(live_phase.time, "sleep", lambda _delay: None)

    result = live_phase._langsmith_result(manifest)

    assert result["trace_count"] == 2
    assert result["queried_root_count"] == 2
    assert result["queried_trace_span_count"] == 4
    assert all(count == 3 for count in fake_client.span_calls.values())
    assert all(trace["span_count"] == 2 for trace in result["traces"])


def test_r8_phase_sequence_treats_final_as_completed_exact_replay(
    host_runner: ModuleType,
    live_phase: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = host_runner._manifest(
        "20260904T030000+0800-zero-model-r8-sequence",
        "a" * 40,
    )
    summary = {
        "schema_version": "fin_ia_dell_zero_model_graph_qualification_v1_0",
        "branch_id": "Q1_ISSUER_TRUTH",
        "route_id": "route:Q1_ISSUER_TRUTH:required-reviewed",
        "task_id": "task:q1",
        "plan_digest": "a" * 64,
        "evidence_status": "success",
        "evidence_result_states": ["reviewed_evidence"],
        "evidence_item_count": 1,
        "evidence_result_digest": "b" * 64,
        "evidence_lane_receipt_id": "receipt:evidence",
        "finance_status": "success",
        "finance_result_states": ["numeric_fact"],
        "finance_item_count": 1,
        "finance_result_digest": "c" * 64,
        "finance_lane_receipt_id": "receipt:finance",
        "tool_lane_execution_count": 2,
        "mcp_call_count": 2,
        "mcp_error_call_count": 0,
        "mcp_tool_call_counts": {"evidence.search": 1, "finance.lookup": 1},
        "model_call_count": 0,
        "live_external_research_call_count": 0,
        "paid_call_count": 0,
    }
    runtime = {"phase": "zero_model_mcp_qualified", "resume_calls": 0}
    server_thread_id = str(UUID(int=101))
    start_run_id = str(UUID(int=102))
    resume_run_id = str(UUID(int=103))

    class FakePool:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> "FakePool":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def wait(self, *, timeout: int) -> None:
            assert timeout == 10

    class FakeRepository:
        def __init__(self, _pool: Any) -> None:
            pass

    class FakeClient:
        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def create_agent_session(self, *, agent_session: Any) -> Any:
            return live_phase.DellAgentServerSessionBinding(
                agent_session_id=agent_session.session_id,
                server_thread_id=server_thread_id,
            )

        def start_run(self, **kwargs: Any) -> Any:
            return live_phase.DellAgentServerRunBinding(
                agent_session_id=kwargs["session"].agent_session_id,
                research_run_id=kwargs["research_run"].run_id,
                run_invocation_id=kwargs["run_invocation"].invocation_id,
                server_thread_id=server_thread_id,
                server_run_id=start_run_id,
                invocation_kind="start",
                server_status="interrupted",
                execution_profile="zero_model_control_plane_v1",
            )

        def resume_run(self, **kwargs: Any) -> Any:
            runtime["resume_calls"] += 1
            runtime["phase"] = "zero_model_control_plane_completed"
            return live_phase.DellAgentServerRunBinding(
                agent_session_id=kwargs["prior_run"].agent_session_id,
                research_run_id=kwargs["research_run"].run_id,
                run_invocation_id=kwargs["run_invocation"].invocation_id,
                server_thread_id=server_thread_id,
                server_run_id=resume_run_id,
                invocation_kind="resume",
                server_status="success",
                execution_profile="zero_model_control_plane_v1",
            )

        def join_updates(self, _run: Any, *, last_event_id: str) -> Any:
            if last_event_id == "-1":
                return iter(
                    [
                        StreamPart(event="metadata", data={"safe": True}, id="1-0"),
                        StreamPart(event="updates", data={"safe": True}, id="2-0"),
                    ]
                )
            assert last_event_id == "1-0"
            return iter(
                [StreamPart(event="updates", data={"safe": True}, id="2-0")]
            )

        def get_state(self, _session: Any) -> dict[str, Any]:
            completed = runtime["phase"] == "zero_model_control_plane_completed"
            return {
                "values": {
                    "execution_profile": "zero_model_control_plane_v1",
                    "phase": runtime["phase"],
                    "final_report": None,
                    "zero_model_qualification_summary": summary,
                    "zero_model_qualification_decision": (
                        {
                            "action": "complete_zero_model_qualification",
                            "reason_provided": True,
                            "reason_digest": "d" * 64,
                        }
                        if completed
                        else None
                    ),
                },
                "interrupts": (
                    []
                    if completed
                    else [
                        {
                            "value": {
                                "kind": (
                                    "dell_zero_model_control_plane_qualification"
                                )
                            }
                        }
                    ]
                ),
                "next": [],
                "metadata": {},
                "tasks": [],
            }

    class FakeClientFactory:
        @classmethod
        def connect(cls, **_kwargs: Any) -> FakeClient:
            return FakeClient()

    monkeypatch.setattr(live_phase, "_require_container_environment", lambda: "x")
    monkeypatch.setattr(live_phase, "_assistant_uuid", lambda: str(UUID(int=104)))
    monkeypatch.setattr(live_phase, "ConnectionPool", FakePool)
    monkeypatch.setattr(
        live_phase, "PostgresDellAgentServerIdentityRepository", FakeRepository
    )
    monkeypatch.setattr(live_phase, "DellAgentServerClient", FakeClientFactory)
    monkeypatch.setattr(
        live_phase,
        "_identity_snapshot",
        lambda _repository, _research_run, expected: {
            "invocation_count": len(expected)
        },
    )
    def fake_remote_snapshot(**kwargs: Any) -> dict[str, Any]:
        expected = kwargs["expected_invocation_ids"]
        return {
            "selected_run_count": len(expected),
            "runs": [
                {
                    "run_invocation_id": invocation_id,
                    "status": (
                        "interrupted"
                        if invocation_id == manifest["start_invocation"]["invocation_id"]
                        else "success"
                    ),
                }
                for invocation_id in sorted(expected)
            ],
        }

    monkeypatch.setattr(live_phase, "_remote_snapshot", fake_remote_snapshot)

    start = live_phase._phase_runtime(manifest, "start")
    readback = live_phase._phase_runtime(manifest, "readback")
    resume = live_phase._phase_runtime(manifest, "resume")
    final = live_phase._phase_runtime(manifest, "final")

    assert start["state"]["phase"] == "zero_model_mcp_qualified"
    assert readback["state"]["phase"] == "zero_model_mcp_qualified"
    assert resume["state"]["phase"] == "zero_model_control_plane_completed"
    assert final["state"]["phase"] == "zero_model_control_plane_completed"
    assert runtime["resume_calls"] == 2
