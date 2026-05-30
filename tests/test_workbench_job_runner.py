from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from sec_agent.workbench.job_runner import (
    CommandSpec,
    build_agent_ask_command,
    build_agent_session_turn_command,
    build_native_checkpoint_resume_command,
    detect_run_dir_from_output,
    start_command_job,
)
from sec_agent.workbench.jobs import new_agent_ask_job, new_eval_run_job
from sec_agent.workbench.profiles import ModelRouteProfile, RuntimeProfile, WorkbenchProfile
from sec_agent.workbench.store import WorkbenchStore


def test_detect_run_dir_from_artifacts_line(tmp_path: Path) -> None:
    run_dir = _write_minimal_run(tmp_path / "run_a")

    detected = detect_run_dir_from_output([f"[artifacts] {run_dir}"], cwd=tmp_path)

    assert detected == run_dir.resolve()


def test_detect_run_dir_from_session_state_line(tmp_path: Path) -> None:
    run_dir = _write_minimal_run(tmp_path / "run_b")

    detected = detect_run_dir_from_output([f"sec_agent_state: {run_dir / 'sec_agent_state.json'}"], cwd=tmp_path)

    assert detected == run_dir.resolve()


def test_detect_run_dir_from_graph_json_line(tmp_path: Path) -> None:
    run_dir = _write_minimal_run(tmp_path / "run_c")
    message = json.dumps({"run_root": str(run_dir), "sec_agent_state_path": str(run_dir / "sec_agent_state.json")})

    detected = detect_run_dir_from_output([message], cwd=tmp_path)

    assert detected == run_dir.resolve()


def test_detect_run_dir_from_wsl_artifacts_line(tmp_path: Path) -> None:
    if not tmp_path.drive:
        return
    run_dir = _write_minimal_run(tmp_path / "run_wsl")
    drive = tmp_path.drive.rstrip(":").lower()
    rest = run_dir.resolve().as_posix().split(":", 1)[1].lstrip("/")
    wsl_run_dir = f"/mnt/{drive}/{rest}"

    detected = detect_run_dir_from_output([f"[artifacts] {wsl_run_dir}"], cwd=tmp_path)

    assert detected == run_dir.resolve()


def test_command_job_attaches_detected_run_dir(tmp_path: Path) -> None:
    store = WorkbenchStore(tmp_path / "workbench.sqlite")
    run_dir = _write_minimal_run(tmp_path / "agent_run")
    code = f"print('[artifacts] {run_dir.as_posix()}', flush=True)"
    job = new_agent_ask_job(prompt="hello", command_mode="ask-api", job_id="ask_fixture", profile_id="profile_a")
    spec = CommandSpec(args=[sys.executable, "-u", "-c", code], cwd=tmp_path, label="fixture_agent")

    start_command_job(store, job, spec)
    finished = _wait_for_job(store, "ask_fixture")
    events = store.list_run_events("ask_fixture")

    assert finished.status == "completed"
    assert finished.run_dir == str(run_dir.resolve())
    assert finished.metadata["detected_run_dir"] == str(run_dir.resolve())
    assert any("detected run_dir:" in event.message for event in events)


def test_command_job_attaches_eval_output_summary(tmp_path: Path) -> None:
    store = WorkbenchStore(tmp_path / "workbench.sqlite")
    output_path = tmp_path / "eval_result.json"
    code = (
        "import json, pathlib\n"
        f"path = pathlib.Path({str(output_path)!r})\n"
        "path.write_text(json.dumps({'schema_version': 'demo_v1', 'run_id': 'run_a', "
        "'case_count': 2, 'pass_count': 2, 'failure_count': 0, 'all_pass': True}), encoding='utf-8')\n"
        "print('eval wrote output', flush=True)\n"
    )
    job = new_eval_run_job(eval_id="context_api_smoke", output_path=output_path, job_id="eval_fixture")
    spec = CommandSpec(args=[sys.executable, "-u", "-c", code], cwd=tmp_path, label="eval:fixture")

    start_command_job(store, job, spec)
    finished = _wait_for_job(store, "eval_fixture")
    events = store.list_run_events("eval_fixture")

    assert finished.status == "completed"
    assert finished.metadata["eval_summary"]["status"] == "pass"
    assert finished.metadata["eval_summary"]["case_count"] == 2
    assert any("eval summary:" in event.message for event in events)


def test_build_agent_ask_command_can_target_wsl(tmp_path: Path) -> None:
    profile = WorkbenchProfile(
        profile_id="wsl_demo",
        display_name="WSL demo",
        env_file="D:/FIN_Insight_Agent/data/workbench_private/profiles/full_source_wsl.env",
        model_route=ModelRouteProfile(api_key_env="DEMO_API_KEY"),
        runtime=RuntimeProfile(
            python="/home/william/venvs/finsight/bin/python",
            bge_model="D:/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/snapshots/demo",
            bge_device="cpu",
            execution_shell="wsl",
            wsl_distro="Ubuntu-22.04",
            wsl_repo_root="/mnt/d/FIN_Insight_Agent",
        ),
    )

    spec = build_agent_ask_command(
        repo_root=tmp_path,
        profile=profile,
        prompt="hello",
        command_mode="ask-full-source-api",
    )

    assert spec.args[:7] == ["wsl.exe", "-d", "Ubuntu-22.04", "--cd", "/mnt/d/FIN_Insight_Agent", "--exec", "env"]
    assert "FIN_REPO_ROOT=/mnt/d/FIN_Insight_Agent" in spec.args
    assert "SEC_AGENT_PROFILE_ENV=/mnt/d/FIN_Insight_Agent/data/workbench_private/profiles/full_source_wsl.env" in spec.args
    assert "PY=/home/william/venvs/finsight/bin/python" in spec.args
    assert "BGE_MODEL=/mnt/d/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/snapshots/demo" in spec.args
    assert "BGE_DEVICE=cpu" in spec.args
    assert any(item.startswith("SEC_AGENT_PROMPT_FILE=") for item in spec.args)
    assert spec.args[-3] == "bash"
    assert spec.args[-2] == "-lc"
    assert 'ask-full-source-api "$prompt"' in spec.args[-1]
    assert spec.cleanup_paths[0].read_text(encoding="utf-8") == "hello"
    assert spec.label == "wsl:ask-full-source-api"


def test_build_agent_ask_command_passes_api_key_to_wsl_env_not_args(tmp_path: Path) -> None:
    profile = WorkbenchProfile(
        profile_id="wsl_secret",
        display_name="WSL secret",
        model_route=ModelRouteProfile(api_key_env="DEMO_API_KEY"),
        runtime=RuntimeProfile(
            execution_shell="wsl",
            wsl_repo_root="/mnt/d/FIN_Insight_Agent",
        ),
    )

    spec = build_agent_ask_command(
        repo_root=tmp_path,
        profile=profile,
        prompt="hello",
        command_mode="ask-full-source-api",
        api_key_value="secret-value",
    )

    assert spec.env_overrides["DEMO_API_KEY"] == "secret-value"
    assert "DEMO_API_KEY/u" in spec.env_overrides["WSLENV"]
    assert "secret-value" not in " ".join(spec.args)


def test_build_agent_session_turn_command_targets_context_cli(tmp_path: Path) -> None:
    profile = WorkbenchProfile(
        profile_id="wsl_session",
        display_name="WSL session",
        runtime=RuntimeProfile(
            python="/home/william/venvs/finsight/bin/python",
            bge_model="/mnt/d/hf_cache/bge",
            execution_shell="wsl",
            wsl_repo_root="/mnt/d/FIN_Insight_Agent",
        ),
    )

    spec = build_agent_session_turn_command(
        repo_root=tmp_path,
        profile=profile,
        prompt="follow up",
        command_mode="session-full-source-api",
        session_id="thread_a",
        tenant_id="tenant_a",
        user_id="user_a",
    )

    assert spec.label == "wsl:session-full-source-api"
    assert "SEC_AGENT_SESSION_ID=thread_a" in spec.args
    assert "SEC_AGENT_TENANT_ID=tenant_a" in spec.args
    assert "SEC_AGENT_USER_ID=user_a" in spec.args
    assert spec.args[-3] == "bash"
    assert spec.args[-2] == "-lc"
    assert "session-full-source-api" in spec.args[-1]
    assert '--prompt "$prompt"' in spec.args[-1]
    assert spec.cleanup_paths[0].read_text(encoding="utf-8") == "follow up"


def test_build_native_checkpoint_resume_command_keeps_secret_out_of_args(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "run" / "langgraph_node_checkpoints.json"
    checkpoint_path.parent.mkdir()
    checkpoint_path.write_text("{}\n", encoding="utf-8")
    profile = WorkbenchProfile(
        profile_id="native_resume",
        display_name="Native resume",
        model_route=ModelRouteProfile(api_key_env="DEMO_API_KEY"),
        runtime=RuntimeProfile(python="python", execution_shell="local"),
    )

    spec = build_native_checkpoint_resume_command(
        repo_root=tmp_path,
        profile=profile,
        checkpoint_path=checkpoint_path,
        api_key_value="secret-value",
        stop_after_node="run_deterministic_gates",
    )

    joined = " ".join(spec.args)
    assert spec.label == "native-checkpoint-resume"
    assert spec.args[:3] == ["python", "-u", "scripts/cloud/sec_agent_graph_runner.py"]
    assert "--resume-native-checkpoint" in spec.args
    assert "--native-resume-include-synthesis" in spec.args
    assert "--native-stop-after-node" in spec.args
    assert spec.env_overrides["DEMO_API_KEY"] == "secret-value"
    assert "secret-value" not in joined


def test_build_native_checkpoint_resume_command_can_target_wsl(tmp_path: Path) -> None:
    profile = WorkbenchProfile(
        profile_id="native_wsl",
        display_name="Native WSL",
        runtime=RuntimeProfile(
            python="/home/william/venvs/finsight/bin/python",
            execution_shell="wsl",
            wsl_repo_root="/mnt/d/FIN_Insight_Agent",
        ),
    )

    spec = build_native_checkpoint_resume_command(
        repo_root=tmp_path,
        profile=profile,
        checkpoint_path="eval/sec_cases/run/langgraph_node_checkpoints.json",
        include_synthesis=False,
        checkpoint_mode="memory",
    )

    assert spec.label == "wsl:native-checkpoint-resume"
    assert "SEC_AGENT_NATIVE_CHECKPOINT_PATH=" in " ".join(spec.args)
    assert spec.args[-3] == "bash"
    assert spec.args[-2] == "-lc"
    assert 'sec_agent_graph_runner.py --resume-native-checkpoint "$SEC_AGENT_NATIVE_CHECKPOINT_PATH"' in spec.args[-1]
    assert "--native-resume-include-synthesis" not in spec.args[-1]


def _write_minimal_run(run_dir: Path) -> Path:
    run_dir.mkdir(parents=True)
    (run_dir / "sec_agent_state.json").write_text(
        json.dumps({"run_id": "fixture", "status": "completed"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return run_dir


def _wait_for_job(store: WorkbenchStore, job_id: str):
    for _ in range(50):
        job = store.get_run_job(job_id)
        if job and job.status in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {job_id}")
