from __future__ import annotations

import ast
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "deploy/dell_agent_server/compose.q1-specialist-paid-shadow.yaml"
HOST_RUNNER = ROOT / "scripts/qualification/dell_q1_specialist_paid_shadow/run_once.py"
CONTAINER_RUNNER = ROOT / "scripts/qualification/dell_q1_specialist_paid_shadow/container_once.py"


def test_paid_shadow_overlay_keeps_provider_authority_and_artifact_scope_on_api() -> None:
    value = yaml.safe_load(OVERLAY.read_text(encoding="utf-8"))
    assert set(value["services"]) == {"langgraph-api"}
    api = value["services"]["langgraph-api"]
    environment = api["environment"]
    assert environment["FINSIGHT_DELL_EXECUTION_PROFILE"] == "product"
    assert environment["FINSIGHT_DELL_SERVING_MODE"] == "q1_specialist_paid_shadow_v1"
    assert "DEEPSEEK_API_KEY" in environment
    assert not {"HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"}.intersection(environment)
    mounts = {row["target"]: row for row in api["volumes"]}
    assert mounts["/run/fin-insight/paid-shadow-authority.json"]["read_only"] is True
    artifact = mounts["${FINSIGHT_DELL_PAID_SHADOW_ARTIFACT_CONTAINER_PATH:?set by the one-shot host runner}"]
    assert artifact["read_only"] is False
    assert mounts["/opt/fin-insight-qualification/dell-q1-specialist-paid-shadow"]["read_only"] is True


def test_paid_shadow_runner_has_one_start_and_no_resume_cleanup_or_direct_invoke() -> None:
    host_text = HOST_RUNNER.read_text(encoding="utf-8")
    container_text = CONTAINER_RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(container_text)
    calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert calls.count("start_specialist_run") == 1
    assert "resume_run" not in calls
    assert ".invoke(" not in container_text
    assert "FIN_REPO_ROOT" in container_text
    combined = host_text + container_text
    assert "docker\", \"down" not in combined
    assert "down\", \"-v" not in combined
