"""Explicit local resource mounts for optional integration tests.

No workstation paths or private dataset manifests belong in the public fixture.
The application validates resource digests when opening the composition.
"""
import os
from pathlib import Path

import pytest

from sec_agent.agent_runtime.agent_server_data_composition import _ENV_PATHS


RUNTIME_ENVIRONMENT = {
    name: os.environ[name]
    for name in (*_ENV_PATHS.values(), "FINSIGHT_RESEARCH_RESOURCES_ROOT")
    if name in os.environ
}
RUNTIME_ENVIRONMENT["FIN_REPO_ROOT"] = str(Path(__file__).resolve().parents[1])


def _assert_assets():
    required = (*_ENV_PATHS.values(), "FINSIGHT_RESEARCH_RESOURCES_ROOT")
    missing = [name for name in required if not RUNTIME_ENVIRONMENT.get(name)]
    if missing:
        pytest.skip("Configure local research resources: " + ", ".join(missing))
    for name in _ENV_PATHS.values():
        assert Path(RUNTIME_ENVIRONMENT[name]).is_file(), f"Missing resource for {name}"
    resource_root = Path(RUNTIME_ENVIRONMENT["FINSIGHT_RESEARCH_RESOURCES_ROOT"])
    for name in ("foundation.json", "source-routes.json", "reviewed-evidence.json", "access-policy.json"):
        assert (resource_root / name).is_file(), f"Missing research resource {name}"
