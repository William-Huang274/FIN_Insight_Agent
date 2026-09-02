from __future__ import annotations

from argparse import Namespace
from contextlib import nullcontext
import json
import os
from pathlib import Path
import subprocess

import pytest
from langgraph.types import Command

import scripts.research.run_dell_reference_vertical as cli
from sec_agent.agent_runtime.dell_reference_vertical_graph import (
    GRAPH_CONTRACT_VERSION,
    build_dell_reference_vertical_graph,
)
from sec_agent.agent_runtime.runtime_foundation import (
    DellRuntimeFoundation,
    open_runtime_checkpointer,
)
from test_dell_reference_vertical_graph import (
    FakeRuntime,
    _planner_tool_capabilities,
    _start_input,
)


def test_help_exposes_only_start_and_resume(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])
    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert "{start,resume}" in output

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["start", "--help"])
    assert exit_info.value.code == 0
    assert "--preflight-only" in capsys.readouterr().out
    assert cli._graph_config("fixture-run")["max_concurrency"] == 3


def test_structured_preview_requires_explicit_candidate_runtime_opt_in(
    tmp_path: Path,
) -> None:
    nodes = tmp_path / "retrieval_nodes.jsonl"
    nodes.write_text("{}\n", encoding="utf-8")
    nodes_sha = cli._stream_sha256(nodes)
    result_path = tmp_path / "result.json"
    result = {
        "schema_version": "fin_ia_dell_structured_rag_qualification_result_v1_0",
        "status": "ENGINEERING_PREVIEW_MEASURED_REVIEW_REQUIRED",
        "attempt_mode": "engineering_preview",
        "formal_eligible": False,
        "manual_review_complete": False,
        "generation_model_calls": 0,
        "deepseek_calls": 0,
        "paid_calls": 0,
        "retrieval_promotion_authorized": False,
        "mcp_promotion_authorized": False,
        "artifacts": {
            "retrieval_nodes.jsonl": {
                "path": str(nodes),
                "sha256": nodes_sha,
            }
        },
        "metrics": {
            "bm25": {
                "hit_rate_at_10": 1.0,
                "critical_miss_count_at_5": 0,
                "critical_delivered_context_required_facet_miss_count_at_5": 0,
                "hard_negative_rank_1_count": 0,
                "critical_acceptable_precedence_failure_count": 0,
            }
        },
    }
    result_path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="structured_rag_engineering_preview_not_authorized",
    ):
        cli._validate_structured_rag_result(
            result_path=result_path,
            nodes_path=nodes,
            nodes_sha256=nodes_sha,
        )

    accepted = cli._validate_structured_rag_result(
        result_path=result_path,
        nodes_path=nodes,
        nodes_sha256=nodes_sha,
        allow_engineering_preview=True,
    )
    assert accepted["mcp_promotion_authorized"] is False
    assert accepted["formal_eligible"] is False


def test_structured_preview_opt_in_cannot_reverse_producer_authority(
    tmp_path: Path,
) -> None:
    nodes = tmp_path / "retrieval_nodes.jsonl"
    nodes.write_text("{}\n", encoding="utf-8")
    nodes_sha = cli._stream_sha256(nodes)
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "schema_version": "fin_ia_dell_structured_rag_qualification_result_v1_0",
                "status": "ENGINEERING_PREVIEW_MEASURED_REVIEW_REQUIRED",
                "attempt_mode": "engineering_preview",
                "formal_eligible": False,
                "manual_review_complete": False,
                "generation_model_calls": 0,
                "deepseek_calls": 0,
                "paid_calls": 0,
                "retrieval_promotion_authorized": False,
                "mcp_promotion_authorized": True,
                "artifacts": {
                    "retrieval_nodes.jsonl": {
                        "path": str(nodes),
                        "sha256": nodes_sha,
                    }
                },
                "metrics": {"bm25": {}},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="structured_rag_binding_invalid",
    ):
        cli._validate_structured_rag_result(
            result_path=result_path,
            nodes_path=nodes,
            nodes_sha256=nodes_sha,
            allow_engineering_preview=True,
        )


def test_structured_a01_run_authority_freezes_complete_secret_free_start_inputs() -> None:
    authority_path = (
        cli.SCRIPT_REPOSITORY_ROOT
        / "scripts/research/run_dell_reference_vertical_structured_a01.ps1"
    )
    text = authority_path.read_text(encoding="utf-8")

    for value in (
        "D:\\FIN_Insight_Agent",
        "20260902-dell-reference-vertical-structured-a01",
        "dell-reference-vertical-structured-run-a01",
        "20260902-dell-structured-rag-s2-successor-candidate",
        "bf214a085916c296428f51e77c8518f2905b5d451290535fea54040fb2d96d47",
        "03115289a715fb65aa72e9d2c9b5463cc459c4c927a0e81fd54d6da9b1216fc8",
        "5d2014ebf6a0561e3f3ea0b6e76e4b5d838b5db7bb097ff086a452ececba9bf2",
        "47d518b937390a446444dd27893a297b97d2aa297a06ac382e13fba9fd26bef9",
        "2ad27d586a64ad7018e460ca836ca689f84615772a561f6b5ebaba196a28191c",
        "f7fbf9f43a68933bad52146c3a8aa3c9a1b52bba81e4e804c2b05a0aff9d0817",
        "dd2c92400de777867545de2c41b975d1f07ca6060f4ed431075b7081ab16ed82",
        "363780c076d0f8766c0ceaafdb8b93d308d339636504b2a263127bb6ca365ac4",
        "2d4e3d572494e6fc7b7537b567a644a894cdf1e82143d325812860c4cc84eccd",
        "1479e49f0cde7166fe6474a74b666dfb646b31a5291f1317689aaa6bc8391eb9",
        "e846fc5d85defa9909779d0ef12f6a1e0c5b00a99ef1eb2d1fffa6ed16492d70",
        "DEEPSEEK_API_KEY",
    ):
        assert value in text
    assert ".venv\\Scripts\\python.exe" in text
    assert "--allow-engineering-preview-candidate-runtime" in text
    assert "--structured-rag-node-count', '1025'" in text
    assert "$runArguments += '--preflight-only'" in text
    assert "[switch]$PreflightOnly" in text
    assert "$env:DEEPSEEK_API_KEY" not in text


def test_zero_call_preflight_builds_without_invoking_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runtime = FakeRuntime()
    checkpoint = tmp_path / "preflight.sqlite3"
    manifest = {
        "composition_digest": "a" * 64,
        "knowledge_record_count": 597,
        "reviewed_evidence_count": 61,
        "implementation_binding": {"binding_digest": "f" * 64},
        "input_bindings": {"repository_root": str(tmp_path.resolve())},
    }
    monkeypatch.setattr(
        cli,
        "_repository_implementation_binding",
        lambda _root: {"binding_digest": "f" * 64},
    )
    monkeypatch.setattr(
        cli,
        "_compose_start",
        lambda _args: {
            "api_key_value": "fixture-secret-never-persisted",
            "checkpoint_path": checkpoint,
            "attempt_dir": tmp_path / "unused-attempt",
            "state_root": tmp_path,
            "run_id": "preflight-run",
            "attempt_id": "preflight-attempt",
            "tool_adapter": nullcontext(),
            "dependencies": runtime.dependencies(),
            "manifest": manifest,
        },
    )

    assert cli._start(Namespace(preflight_only=True)) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "zero_call_preflight_pass"
    assert result["model_calls"] == result["external_discovery_calls"] == 0
    assert result["external_capture_calls"] == 0
    assert result["graph_invoked"] is False
    assert result["knowledge_record_count"] == 597
    assert result["reviewed_evidence_count"] == 61
    assert runtime.calls == []
    assert runtime.specialist_inputs == []
    assert not checkpoint.exists()
    assert result["sqlite_checkpoint_probe_cleaned"] is True


@pytest.mark.skipif(os.name != "nt", reason="Z-drive policy is Windows-specific")
def test_windows_state_root_rejects_non_z_drive(tmp_path: Path) -> None:
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="state_root_must_be_on_z_drive",
    ):
        cli._state_root(tmp_path)


def _persist_interrupted_fixture(
    root: Path,
    *,
    attempt_id: str,
    run_id: str,
) -> tuple[FakeRuntime, Path]:
    attempt_dir = cli._attempt_dir(root, attempt_id)
    checkpoint = cli._checkpoint_path(root, run_id)
    attempt_dir.mkdir(parents=True)
    runtime = FakeRuntime()
    foundation = DellRuntimeFoundation(
        profile="sqlite_qualification",
        sqlite_path=checkpoint,
    )
    with open_runtime_checkpointer(foundation) as saver:
        graph = build_dell_reference_vertical_graph(
            dependencies=runtime.dependencies(),
            checkpointer=saver,
        )
        state = graph.invoke(
            {**_start_input(), "run_id": run_id},
            cli._graph_config(run_id),
        )
    assert state["phase"] == "awaiting_review"
    manifest = {
        "schema_version": cli.SCHEMA_VERSION,
        "attempt_id": attempt_id,
        "run_id": run_id,
        "case_id": state["case_id"],
        "research_question": state["research_question"],
        "snapshot_id": state["snapshot_id"],
        "research_as_of": state["research_as_of"],
        "foundation_canonical_digest": state["foundation_digest"],
        "foundation_binding": state["foundation_binding"],
        "checkpoint_path": str(checkpoint),
        "graph_contract_version": GRAPH_CONTRACT_VERSION,
        "implementation_binding": {
            "binding_digest": "f" * 64,
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "fixture": True,
        },
        "input_bindings": {"repository_root": str(root.resolve())},
        "planner_tool_capabilities": _planner_tool_capabilities(),
    }
    manifest["composition_digest"] = cli._canonical_digest(manifest)
    cli._write_new_json(attempt_dir / "composition.json", manifest)
    return runtime, attempt_dir


@pytest.mark.parametrize(
    ("action", "expected_phase", "report_expected"),
    [("approve", "completed", True), ("reject", "rejected", False)],
)
def test_resume_does_not_reexecute_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    expected_phase: str,
    report_expected: bool,
) -> None:
    monkeypatch.setattr(cli, "_state_root", lambda path: Path(path).resolve())
    attempt_id = f"resume-{action}-attempt"
    run_id = f"resume-{action}-run"
    runtime, attempt_dir = _persist_interrupted_fixture(
        tmp_path,
        attempt_id=attempt_id,
        run_id=run_id,
    )
    monkeypatch.setattr(
        cli,
        "_repository_implementation_binding",
        lambda _root: {
            "binding_digest": "f" * 64,
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "fixture": True,
        },
    )
    calls_before = list(runtime.calls)
    specialists_before = list(runtime.specialist_inputs)
    counter_before = runtime.counter_calls
    lead_before = runtime.lead_calls

    result = cli._resume(
        Namespace(
            state_root=tmp_path,
            attempt_id=attempt_id,
            run_id=run_id,
            action=action,
            reason="deterministic CLI resume test",
        )
    )

    assert result == 0
    suffix = "approved" if action == "approve" else "rejected"
    state = json.loads((attempt_dir / f"state.{suffix}.json").read_text())
    assert state["phase"] == expected_phase
    assert (attempt_dir / "final-report.json").exists() is report_expected
    assert runtime.calls == calls_before
    assert runtime.specialist_inputs == specialists_before
    assert runtime.counter_calls == counter_before
    assert runtime.lead_calls == lead_before


def test_resume_repairs_terminal_checkpoint_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "_state_root", lambda path: Path(path).resolve())
    monkeypatch.setattr(
        cli,
        "_repository_implementation_binding",
        lambda _root: {
            "binding_digest": "f" * 64,
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "fixture": True,
        },
    )
    attempt_id = "resume-repair-attempt"
    run_id = "resume-repair-run"
    _runtime, attempt_dir = _persist_interrupted_fixture(
        tmp_path,
        attempt_id=attempt_id,
        run_id=run_id,
    )
    args = Namespace(
        state_root=tmp_path,
        attempt_id=attempt_id,
        run_id=run_id,
        action="approve",
        reason="simulate an interrupted terminal export",
    )
    original_write = cli._write_or_validate_json
    failure_injected = False

    def fail_after_checkpoint(path: Path, value: object, **kwargs: object) -> bool:
        nonlocal failure_injected
        if path.name == "state.approved.json" and not failure_injected:
            failure_injected = True
            raise cli.DellReferenceVerticalCLIError(
                "simulated_terminal_artifact_failure"
            )
        return original_write(path, value, **kwargs)

    monkeypatch.setattr(cli, "_write_or_validate_json", fail_after_checkpoint)
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="simulated_terminal_artifact_failure",
    ):
        cli._resume(args)
    assert not (attempt_dir / "state.approved.json").exists()

    monkeypatch.setattr(cli, "_write_or_validate_json", original_write)
    assert cli._resume(args) == 0
    summary_path = attempt_dir / "summary.approved.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["artifact_materialization_mode"] == (
        "terminal_checkpoint_repair"
    )
    frozen_artifacts = {
        path.name: path.read_bytes()
        for path in (
            attempt_dir / "state.approved.json",
            attempt_dir / "final-report.json",
            summary_path,
        )
    }

    assert cli._resume(args) == 0
    assert {
        path.name: path.read_bytes()
        for path in (
            attempt_dir / "state.approved.json",
            attempt_dir / "final-report.json",
            summary_path,
        )
    } == frozen_artifacts


def test_resume_repairs_rejected_terminal_checkpoint_without_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "_state_root", lambda path: Path(path).resolve())
    monkeypatch.setattr(
        cli,
        "_repository_implementation_binding",
        lambda _root: {
            "binding_digest": "f" * 64,
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "fixture": True,
        },
    )
    attempt_id = "resume-reject-repair-attempt"
    run_id = "resume-reject-repair-run"
    _runtime, attempt_dir = _persist_interrupted_fixture(
        tmp_path,
        attempt_id=attempt_id,
        run_id=run_id,
    )
    args = Namespace(
        state_root=tmp_path,
        attempt_id=attempt_id,
        run_id=run_id,
        action="reject",
        reason="reject after manual qualification review",
    )
    original_write = cli._write_or_validate_json

    def fail_first_state(path: Path, value: object, **kwargs: object) -> bool:
        if path.name == "state.rejected.json":
            raise cli.DellReferenceVerticalCLIError(
                "simulated_rejected_artifact_failure"
            )
        return original_write(path, value, **kwargs)

    monkeypatch.setattr(cli, "_write_or_validate_json", fail_first_state)
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="simulated_rejected_artifact_failure",
    ):
        cli._resume(args)

    monkeypatch.setattr(cli, "_write_or_validate_json", original_write)
    assert cli._resume(args) == 0
    summary = json.loads(
        (attempt_dir / "summary.rejected.json").read_text(encoding="utf-8")
    )
    assert summary["artifact_materialization_mode"] == (
        "terminal_checkpoint_repair"
    )
    assert (attempt_dir / "state.rejected.json").is_file()
    assert not (attempt_dir / "final-report.json").exists()


def test_resume_rejects_terminal_decision_reason_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "_state_root", lambda path: Path(path).resolve())
    monkeypatch.setattr(
        cli,
        "_repository_implementation_binding",
        lambda _root: {
            "binding_digest": "f" * 64,
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "fixture": True,
        },
    )
    attempt_id = "resume-decision-mismatch-attempt"
    run_id = "resume-decision-mismatch-run"
    _runtime, _attempt_dir = _persist_interrupted_fixture(
        tmp_path,
        attempt_id=attempt_id,
        run_id=run_id,
    )
    original_write = cli._write_or_validate_json

    def fail_after_checkpoint(path: Path, value: object, **kwargs: object) -> bool:
        if path.name == "state.approved.json":
            raise cli.DellReferenceVerticalCLIError("simulated_export_failure")
        return original_write(path, value, **kwargs)

    first = Namespace(
        state_root=tmp_path,
        attempt_id=attempt_id,
        run_id=run_id,
        action="approve",
        reason="original review reason",
    )
    monkeypatch.setattr(cli, "_write_or_validate_json", fail_after_checkpoint)
    with pytest.raises(cli.DellReferenceVerticalCLIError):
        cli._resume(first)
    monkeypatch.setattr(cli, "_write_or_validate_json", original_write)

    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="terminal_review_decision_binding_mismatch",
    ):
        cli._resume(
            Namespace(
                **{
                    **vars(first),
                    "reason": "different review reason",
                }
            )
        )


@pytest.mark.parametrize(
    "failure_target",
    ("final-report.json", "summary.approved.json"),
)
def test_resume_repairs_partial_terminal_exports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_target: str,
) -> None:
    monkeypatch.setattr(cli, "_state_root", lambda path: Path(path).resolve())
    monkeypatch.setattr(
        cli,
        "_repository_implementation_binding",
        lambda _root: {
            "binding_digest": "f" * 64,
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "fixture": True,
        },
    )
    attempt_id = f"partial-{failure_target.replace('.', '-')}-attempt"
    run_id = f"partial-{failure_target.replace('.', '-')}-run"
    _runtime, attempt_dir = _persist_interrupted_fixture(
        tmp_path,
        attempt_id=attempt_id,
        run_id=run_id,
    )
    args = Namespace(
        state_root=tmp_path,
        attempt_id=attempt_id,
        run_id=run_id,
        action="approve",
        reason=f"failure boundary {failure_target}",
    )
    original_or_validate = cli._write_or_validate_json
    original_new = cli._write_new_json

    def maybe_fail_or_validate(
        path: Path, value: object, **kwargs: object
    ) -> bool:
        if path.name == failure_target:
            raise cli.DellReferenceVerticalCLIError(
                "simulated_partial_export_failure"
            )
        return original_or_validate(path, value, **kwargs)

    def maybe_fail_new(path: Path, value: object, **kwargs: object) -> None:
        if path.name == failure_target:
            raise cli.DellReferenceVerticalCLIError(
                "simulated_partial_export_failure"
            )
        original_new(path, value, **kwargs)

    monkeypatch.setattr(cli, "_write_or_validate_json", maybe_fail_or_validate)
    monkeypatch.setattr(cli, "_write_new_json", maybe_fail_new)
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="simulated_partial_export_failure",
    ):
        cli._resume(args)

    monkeypatch.setattr(cli, "_write_or_validate_json", original_or_validate)
    monkeypatch.setattr(cli, "_write_new_json", original_new)
    assert cli._resume(args) == 0
    assert (attempt_dir / "state.approved.json").is_file()
    assert (attempt_dir / "final-report.json").is_file()
    assert (attempt_dir / "summary.approved.json").is_file()


def test_resume_rejects_existing_terminal_artifact_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "_state_root", lambda path: Path(path).resolve())
    monkeypatch.setattr(
        cli,
        "_repository_implementation_binding",
        lambda _root: {
            "binding_digest": "f" * 64,
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "fixture": True,
        },
    )
    attempt_id = "resume-artifact-drift-attempt"
    run_id = "resume-artifact-drift-run"
    _runtime, attempt_dir = _persist_interrupted_fixture(
        tmp_path,
        attempt_id=attempt_id,
        run_id=run_id,
    )
    args = Namespace(
        state_root=tmp_path,
        attempt_id=attempt_id,
        run_id=run_id,
        action="approve",
        reason="artifact drift fixture",
    )
    assert cli._resume(args) == 0
    report_path = attempt_dir / "final-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["case_id"] = "TAMPERED"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="existing_artifact_identity_mismatch:final-report.json",
    ):
        cli._resume(args)


def test_resume_continues_only_render_from_approved_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "_state_root", lambda path: Path(path).resolve())
    monkeypatch.setattr(
        cli,
        "_repository_implementation_binding",
        lambda _root: {
            "binding_digest": "f" * 64,
            "graph_contract_version": GRAPH_CONTRACT_VERSION,
            "fixture": True,
        },
    )
    attempt_id = "resume-approved-render-attempt"
    run_id = "resume-approved-render-run"
    runtime, attempt_dir = _persist_interrupted_fixture(
        tmp_path,
        attempt_id=attempt_id,
        run_id=run_id,
    )
    reason = "persist approval but interrupt before deterministic render"
    foundation = DellRuntimeFoundation(
        profile="sqlite_qualification",
        sqlite_path=cli._checkpoint_path(tmp_path, run_id),
    )
    config = cli._graph_config(run_id)
    with open_runtime_checkpointer(foundation) as saver:
        graph = build_dell_reference_vertical_graph(
            dependencies=runtime.dependencies(),
            checkpointer=saver,
        )
        approved = graph.invoke(
            Command(resume={"action": "approve", "reason": reason}),
            config,
            interrupt_before=["render"],
        )
        snapshot = graph.get_state(config)
    assert approved["phase"] == "approved"
    assert tuple(snapshot.next) == ("render",)
    calls_before = (
        list(runtime.calls),
        list(runtime.specialist_inputs),
        runtime.counter_calls,
        runtime.lead_calls,
    )

    assert (
        cli._resume(
            Namespace(
                state_root=tmp_path,
                attempt_id=attempt_id,
                run_id=run_id,
                action="approve",
                reason=reason,
            )
        )
        == 0
    )
    summary = json.loads(
        (attempt_dir / "summary.approved.json").read_text(encoding="utf-8")
    )
    assert summary["artifact_materialization_mode"] == (
        "approved_checkpoint_render_recovery"
    )
    assert json.loads(
        (attempt_dir / "state.approved.json").read_text(encoding="utf-8")
    )["phase"] == "completed"
    assert (
        list(runtime.calls),
        list(runtime.specialist_inputs),
        runtime.counter_calls,
        runtime.lead_calls,
    ) == calls_before


def test_artifact_secret_scan_and_attempt_collision_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "secret.json"
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="credential_projection_forbidden",
    ):
        cli._write_new_json(
            artifact,
            {"value": "fixture-secret-never-persisted"},
            secrets=("fixture-secret-never-persisted",),
        )
    assert not artifact.exists()

    attempt_dir = tmp_path / "existing-attempt"
    attempt_dir.mkdir()
    checkpoint = tmp_path / "new-run.sqlite3"
    monkeypatch.setattr(
        cli,
        "_compose_start",
        lambda _args: {
            "api_key_value": "fixture-secret-never-persisted",
            "checkpoint_path": checkpoint,
            "attempt_dir": attempt_dir,
        },
    )
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="attempt_directory_already_exists",
    ):
        cli._start(Namespace(preflight_only=False))
    assert not checkpoint.exists()


def test_repository_implementation_binding_requires_exact_clean_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(
        ["git", "init", "-b", cli.EXPECTED_GIT_BRANCH],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    source = repository / "runtime.py"
    source.write_text("BOUND = True\n", encoding="utf-8")
    subprocess.run(["git", "add", "runtime.py"], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Codex Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "fixture",
        ],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    monkeypatch.setattr(
        cli,
        "_implementation_source_paths",
        lambda _root: (source.resolve(),),
    )
    monkeypatch.setattr(
        cli,
        "_implementation_module_origins",
        lambda _root: [],
    )

    binding = cli._repository_implementation_binding(repository)

    assert binding["git_branch"] == cli.EXPECTED_GIT_BRANCH
    assert binding["worktree_clean"] is True
    assert binding["source_files"] == [
        {"path": "runtime.py", "sha256": cli._stream_sha256(source)}
    ]
    assert binding["runtime_module_origins"] == []
    assert binding["runtime_module_origin_digest"] == cli._canonical_digest([])
    assert len(binding["binding_digest"]) == 64

    source.write_text("BOUND = False\n", encoding="utf-8")
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="repository_worktree_must_be_clean_for_bound_run",
    ):
        cli._repository_implementation_binding(repository)


def test_project_os_decision_source_is_bound_and_rechecked_on_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = tmp_path / "decision.json"
    decision.write_text('{"scope":"A02"}\n', encoding="utf-8")
    decision_sha = cli._stream_sha256(decision)
    bound_path, binding = cli._bound_project_os_decision_source(
        repository_root=tmp_path.resolve(),
        path=decision,
        sha256=decision_sha,
    )

    assert bound_path == decision.resolve()
    assert binding == {"path": "decision.json", "sha256": decision_sha}

    expected = {"binding_digest": "a" * 64}
    observed: list[Path | None] = []

    def _binding(
        _root: Path,
        *,
        project_os_decision_path: Path | None = None,
    ) -> dict[str, str]:
        observed.append(project_os_decision_path)
        return expected

    monkeypatch.setattr(cli, "_repository_implementation_binding", _binding)
    manifest = {
        "implementation_binding": expected,
        "input_bindings": {
            "repository_root": str(tmp_path.resolve()),
            "project_os_decision_source": binding,
        },
    }

    cli._assert_current_implementation_matches(manifest)
    assert observed == [decision.resolve()]

    decision.write_text('{"scope":"drifted"}\n', encoding="utf-8")
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="project_os_decision_source_sha256_mismatch",
    ):
        cli._assert_current_implementation_matches(manifest)


def test_runtime_module_origins_are_exactly_contained_in_bound_checkout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    origins = cli._implementation_module_origins(cli.SCRIPT_REPOSITORY_ROOT)

    assert {row["module"] for row in origins} == set(
        cli._IMPLEMENTATION_MODULE_PATHS
    )
    assert all(len(row["sha256"]) == 64 for row in origins)
    assert all(
        (cli.SCRIPT_REPOSITORY_ROOT / row["path"])
        .resolve()
        .is_relative_to(cli.SCRIPT_REPOSITORY_ROOT)
        for row in origins
    )

    foreign = tmp_path / "foreign.py"
    foreign.write_text("FOREIGN = True\n", encoding="utf-8")

    class ForeignModule:
        __file__ = str(foreign)

    monkeypatch.setattr(
        cli.importlib,
        "import_module",
        lambda _name: ForeignModule(),
    )
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="implementation_module_origin_mismatch",
    ):
        cli._implementation_module_origins(cli.SCRIPT_REPOSITORY_ROOT)


def test_case_only_evidence_overlay_is_receipt_bound_and_composed(
    tmp_path: Path,
) -> None:
    base_body = {
        "schema_version": "fixture_base_projection",
        "case_key": "DELL",
        "evidence_items": [],
    }
    base = {**base_body, "projection_digest": cli._canonical_digest(base_body)}
    overlay_body = {
        "schema_version": (
            "fin_ia_dell_case_only_reviewed_evidence_projection_v1_0"
        ),
        "status": "case_only_reviewed_evidence_projection_ready",
        "case_key": "DELL",
        "pack_payload_digest": "a" * 64,
        "evidence_items": [
            {
                "target_id": "DELL_Q2_FIXTURE",
                "evidence_item_digest": "b" * 64,
            }
        ],
        "authority": {
            "reviewed_evidence": True,
            "automatic_evidence_promotion": False,
            "qualified_human_review": False,
            "s2_numeric_fact_authority": False,
            "derived_current_q2_arithmetic_authorized": False,
            "product_pack_mutation_authorized": False,
        },
    }
    overlay = {
        **overlay_body,
        "projection_digest": cli._canonical_digest(overlay_body),
    }
    projection_path = tmp_path / "overlay-projection.json"
    projection_path.write_text(json.dumps(overlay), encoding="utf-8")
    projection_sha = cli._stream_sha256(projection_path)
    receipt_body = {
        "schema_version": (
            "fin_ia_dell_fy27_q2_reviewed_evidence_overlay_receipt_v1_0"
        ),
        "status": "case_only_reviewed_evidence_overlay_materialized",
        "case_key": "DELL",
        "artifacts": {
            "case_projection": {
                "path": str(projection_path.resolve()),
                "sha256": projection_sha,
            }
        },
        "authority": {
            "case_only_reviewed_evidence": True,
            "writer_citable_within_case": True,
            "automatic_evidence_promotion": False,
            "qualified_human_review": False,
            "s2_numeric_fact_authority": False,
            "derived_current_q2_arithmetic_authorized": False,
            "product_pack_mutation_authorized": False,
        },
        "review": {
            "item_count": 1,
            "pack_validator": "PASS",
            "mcp_reviewed_evidence_reader": {"status": "PASS"},
        },
    }
    receipt = {
        **receipt_body,
        "receipt_payload_digest": cli._canonical_digest(receipt_body),
    }
    receipt_path = tmp_path / "overlay-receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    receipt_sha = cli._stream_sha256(receipt_path)

    composite, binding = cli._compose_case_only_evidence_overlay(
        base,
        projection_path=projection_path,
        projection_sha256=projection_sha,
        receipt_path=receipt_path,
        receipt_sha256=receipt_sha,
    )

    assert len(composite["evidence_items"]) == 1
    assert binding["overlay_evidence_count"] == 1
    assert binding["composite_projection_digest"] == composite["projection_digest"]
    assert binding["current_q2_s2_numeric_fact_authority"] is False

    receipt["review"]["pack_validator"] = "FAIL"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="reviewed_evidence_overlay_receipt_binding_invalid",
    ):
        cli._compose_case_only_evidence_overlay(
            base,
            projection_path=projection_path,
            projection_sha256=projection_sha,
            receipt_path=receipt_path,
            receipt_sha256=cli._stream_sha256(receipt_path),
        )


def test_model_call_artifact_journal_is_append_only_and_secret_scanned(
    tmp_path: Path,
) -> None:
    journal = cli._ModelCallArtifactJournal(
        tmp_path / "attempt",
        secrets=("fixture-secret-never-persisted",),
    )
    call_id = "planner-aaaaaaaaaaaa-bbbbbbbbbbbbbbbbbbbb"
    journal(
        {
            "event": "started",
            "call_id": call_id,
            "semantic_input": {"question": "fixture"},
        }
    )
    journal(
        {
            "event": "outcome",
            "call_id": call_id,
            "status": "success",
            "total_tokens": 42,
        }
    )
    summary = cli._model_call_audit_summary(tmp_path / "attempt")
    assert summary["started_call_count"] == 1
    assert summary["outcome_call_count"] == 1
    assert summary["unfinished_call_count"] == 0
    assert summary["provider_reported_total_tokens"] == 42
    assert summary["successful_call_tokens"] == 42
    assert summary["failed_post_response_call_tokens"] == 0
    assert summary["successful_total_tokens"] == 42

    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="artifact_already_exists",
    ):
        journal(
            {
                "event": "started",
                "call_id": call_id,
                "semantic_input": {"question": "duplicate"},
            }
        )

    secret_call_id = "lead-cccccccccccc-dddddddddddddddddddd"
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="credential_projection_forbidden",
    ):
        journal(
            {
                "event": "started",
                "call_id": secret_call_id,
                "semantic_input": {"value": "fixture-secret-never-persisted"},
            }
        )
    assert not (
        tmp_path
        / "attempt"
        / "model-calls"
        / f"{secret_call_id}.started.json"
    ).exists()


def test_model_call_summary_counts_paid_post_response_failure_tokens(
    tmp_path: Path,
) -> None:
    journal = cli._ModelCallArtifactJournal(tmp_path / "attempt", secrets=())
    call_id = "planner-eeeeeeeeeeee-ffffffffffffffffffff"
    journal(
        {
            "event": "started",
            "call_id": call_id,
            "semantic_input": {"question": "fixture"},
        }
    )
    journal(
        {
            "event": "outcome",
            "call_id": call_id,
            "status": "structured_parse_failed",
            "raw_response": {
                "usage_metadata": {
                    "input_tokens": 21_465,
                    "output_tokens": 2_076,
                    "total_tokens": 23_541,
                }
            },
        }
    )

    summary = cli._model_call_audit_summary(tmp_path / "attempt")

    assert summary["provider_reported_total_tokens"] == 23_541
    assert summary["successful_call_tokens"] == 0
    assert summary["failed_post_response_call_tokens"] == 23_541
    assert summary["successful_total_tokens"] == 0


def test_validate_knowledge_bridge_accepts_provenance_v1_2(
    tmp_path: Path,
) -> None:
    records_path = tmp_path / "records.jsonl"
    records_path.write_text('{"candidate_is_not_evidence":true}\n', encoding="utf-8")
    records_sha256 = cli._stream_sha256(records_path)
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "schema_version": (
                    "fin_ia_dell_knowledge_reader_bridge_result_v1_2"
                ),
                "status": "qualification_candidate_bridge_materialized",
                "authority_state": "retrieval_candidate_set",
                "output": {
                    "records_path": records_path.as_posix(),
                    "sha256": records_sha256,
                    "record_count": 1,
                },
                "provenance_fields_preserved": True,
                "text_sha256_recomputed": True,
                "parent_content_materialized": False,
                "parent_child_retrieval_performed": False,
                "candidate_is_not_evidence": True,
                "citation_eligible": False,
                "evidence_admission_performed": False,
            }
        ),
        encoding="utf-8",
    )

    value = cli._validate_knowledge_bridge(
        result_path=result_path,
        records_path=records_path,
        records_sha256=records_sha256,
        record_count=1,
    )

    assert value["schema_version"].endswith("_v1_2")


def test_validate_knowledge_bridge_rejects_incomplete_provenance_v1_2(
    tmp_path: Path,
) -> None:
    records_path = tmp_path / "records.jsonl"
    records_path.write_text('{"candidate_is_not_evidence":true}\n', encoding="utf-8")
    records_sha256 = cli._stream_sha256(records_path)
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "schema_version": (
                    "fin_ia_dell_knowledge_reader_bridge_result_v1_2"
                ),
                "status": "qualification_candidate_bridge_materialized",
                "authority_state": "retrieval_candidate_set",
                "output": {
                    "records_path": records_path.as_posix(),
                    "sha256": records_sha256,
                    "record_count": 1,
                },
                "provenance_fields_preserved": False,
                "text_sha256_recomputed": True,
                "parent_content_materialized": False,
                "parent_child_retrieval_performed": False,
                "candidate_is_not_evidence": True,
                "citation_eligible": False,
                "evidence_admission_performed": False,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="knowledge_bridge_binding_invalid",
    ):
        cli._validate_knowledge_bridge(
            result_path=result_path,
            records_path=records_path,
            records_sha256=records_sha256,
            record_count=1,
        )


def test_validate_s2_result_recomputes_canonical_result_digest(
    tmp_path: Path,
) -> None:
    mart_path = tmp_path / "company_financial_facts.sqlite"
    mart_path.write_bytes(b"sqlite-fixture")
    mart_sha256 = "a" * 64
    unsigned = {
        "schema_version": (
            "fin_ia_s2_company_financial_fact_mart_build_result_v1_0"
        ),
        "status": "s2_company_financial_fact_mart_engineering_pass",
        "storage": {
            "sqlite_ref": str(mart_path),
            "sqlite_sha256": mart_sha256,
        },
        "acceptance": {
            "candidate_or_metric_row_grants_numeric_authority": False,
        },
    }
    result_path = tmp_path / "s2_result.json"
    result_path.write_text(
        json.dumps(
            {**unsigned, "result_digest": cli._canonical_digest(unsigned)},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    validated = cli._validate_s2_result(
        result_path=result_path,
        mart_path=mart_path,
        mart_sha256=mart_sha256,
    )
    assert validated["result_digest"] == cli._canonical_digest(unsigned)

    result_path.write_text(
        json.dumps({**unsigned, "result_digest": "f" * 64}, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(
        cli.DellReferenceVerticalCLIError,
        match="s2_result_binding_invalid",
    ):
        cli._validate_s2_result(
            result_path=result_path,
            mart_path=mart_path,
            mart_sha256=mart_sha256,
        )


def test_write_or_validate_json_recovers_matching_orphan_temporary_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "terminal.json"
    temporary = target.with_name(target.name + ".tmp")
    value = {"phase": "completed", "digest": "a" * 64}
    temporary.write_text(json.dumps(value), encoding="utf-8")

    assert cli._write_or_validate_json(target, value) is True
    assert json.loads(target.read_text(encoding="utf-8")) == value
    assert not temporary.exists()
    assert cli._write_or_validate_json(target, value) is False
