from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

import scripts.research.run_dell_reference_vertical as cli
import sec_agent.agent_runtime as agent_runtime
from sec_agent.agent_runtime import dell_reference_vertical_graph as graph_module


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/research/run_dell_reference_vertical.py"
LAUNCHERS = (
    ROOT / "scripts/research/run_dell_reference_vertical_q1_a01.ps1",
    ROOT / "scripts/research/run_dell_reference_vertical_structured_a01.ps1",
    ROOT / "scripts/research/run_dell_reference_vertical_structured_a02.ps1",
)


def test_help_identifies_the_agent_server_and_langsmith_replacement(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])

    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert "Retired Dell direct runner" in output
    assert "Agent Server" in output
    assert "LangSmith" in output
    assert "{start,resume}" in output


@pytest.mark.parametrize("command", ["start", "resume"])
def test_legacy_commands_raise_one_typed_retirement_error(command: str) -> None:
    with pytest.raises(cli.DellReferenceVerticalCLIError) as error:
        cli.main([command, "--any-former-argument", "ignored"])

    assert error.value.code == cli.LEGACY_RUNTIME_RETIREMENT_CODE
    assert error.value.command == command
    assert str(error.value) == cli.LEGACY_RUNTIME_RETIREMENT_CODE
    assert cli.retirement_receipt(command=command) == {
        "schema_version": "fin_ia_dell_legacy_runtime_retirement_v1",
        "status": "retired",
        "code": cli.LEGACY_RUNTIME_RETIREMENT_CODE,
        "command": command,
        "replacement": "langgraph_agent_server_plus_langsmith",
        "fallback_available": False,
    }


@pytest.mark.parametrize("command", ["start", "resume"])
def test_legacy_process_exits_with_machine_readable_retirement_receipt(
    command: str,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            command,
            "--state-root",
            "should-not-be-read",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == cli.LEGACY_RUNTIME_RETIREMENT_EXIT_CODE
    assert completed.stdout == ""
    receipt = json.loads(completed.stderr)
    assert receipt["code"] == cli.LEGACY_RUNTIME_RETIREMENT_CODE
    assert receipt["command"] == command
    assert receipt["fallback_available"] is False


def test_tombstone_contains_no_local_runtime_composition() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    for forbidden in (
        "open_runtime_checkpointer",
        "sqlite_qualification",
        "build_dell_reference_vertical_graph",
        "_build_dell_reference_vertical_test_graph",
        ".invoke(",
        ".ainvoke(",
        "DEEPSEEK_API_KEY",
    ):
        assert forbidden not in source


def test_all_bound_launchers_fail_before_environment_or_dependency_checks() -> None:
    for launcher in LAUNCHERS:
        text = launcher.read_text(encoding="utf-8")
        assert f"throw '{cli.LEGACY_RUNTIME_RETIREMENT_CODE}'" in text
        for forbidden in (
            "Resolve-Path",
            "Get-FileHash",
            "DEEPSEEK_API_KEY",
            "pythonPath",
            "runArguments",
            "& $",
        ):
            assert forbidden not in text


def test_local_compilation_adapter_is_private_and_not_a_package_api() -> None:
    assert "DellReferenceVerticalCompiledGraph" not in graph_module.__all__
    assert "build_dell_reference_vertical_graph" not in graph_module.__all__
    assert "DellReferenceVerticalCompiledGraph" not in agent_runtime.__all__
    assert "build_dell_reference_vertical_graph" not in agent_runtime.__all__
    assert not hasattr(graph_module, "DellReferenceVerticalCompiledGraph")
    assert not hasattr(graph_module, "build_dell_reference_vertical_graph")
    assert not hasattr(graph_module, "_DellReferenceVerticalTestGraph")
    assert not hasattr(graph_module, "_build_dell_reference_vertical_test_graph")


def test_no_product_consumer_opens_the_legacy_local_checkpointer() -> None:
    consumers: list[str] = []
    definition = ROOT / "src/sec_agent/agent_runtime/runtime_foundation.py"
    for top_level in ("src", "scripts", "apps"):
        for path in (ROOT / top_level).rglob("*.py"):
            if path == definition:
                continue
            if "open_runtime_checkpointer" in path.read_text(
                encoding="utf-8", errors="replace"
            ):
                consumers.append(path.relative_to(ROOT).as_posix())

    assert consumers == []
