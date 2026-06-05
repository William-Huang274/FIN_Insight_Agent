from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_compose_installs_workbench_api_requirements() -> None:
    config = yaml.safe_load((REPO_ROOT / "compose.runtime.yaml").read_text(encoding="utf-8"))

    build_args = config["services"]["workbench"]["build"]["args"]

    assert build_args["REQUIREMENTS_FILE"] == "requirements.txt"
    assert build_args["EXTRA_REQUIREMENTS_FILE"] == "requirements-workbench.txt"
    assert build_args["WORKBENCH_IMAGE_KIND"] == "runtime"
    assert build_args["WORKBENCH_RUNTIME_PROFILE"] == "integrated"


def test_compose_mutable_mounts_can_move_off_repo_drive() -> None:
    config = yaml.safe_load((REPO_ROOT / "compose.yaml").read_text(encoding="utf-8"))

    volumes = config["services"]["workbench"]["volumes"]

    assert "${WORKBENCH_CONFIGS_MOUNT:-./configs}:/app/configs" in volumes
    assert "${WORKBENCH_DATA_MOUNT:-./data}:/app/data" in volumes
    assert "${WORKBENCH_REPORTS_MOUNT:-./reports}:/app/reports" in volumes


def test_dockerfile_supports_extra_requirements_layer() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG EXTRA_REQUIREMENTS_FILE=" in dockerfile
    assert 'python -m pip install --no-cache-dir -r "${EXTRA_REQUIREMENTS_FILE}"' in dockerfile


def test_vite_entrypoint_is_not_ignored() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    entrypoint = REPO_ROOT / "apps/workbench/frontend/vite/index.html"

    assert "!/apps/workbench/frontend/vite/index.html" in gitignore
    assert 'id="root"' in entrypoint.read_text(encoding="utf-8")
