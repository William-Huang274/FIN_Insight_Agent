from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field


class WorkbenchRuntimeLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_active_jobs: int = Field(default=2, ge=1, le=32)
    default_timeout_s: int | None = Field(default=None, ge=1, le=86400)
    cancel_grace_s: int = Field(default=5, ge=1, le=60)
    event_page_max: int = Field(default=5000, ge=100, le=50000)


class WorkbenchDeploymentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime_profile: str = "auto"
    image_kind: str = "backend"
    release_id: str = "local"
    script_update_mode: str = "image_rebuild"
    data_update_mode: str = "data_build_jobs"
    update_interface_version: str = "finsight_workbench_update_interfaces_v0.1"


def runtime_limits_from_env() -> WorkbenchRuntimeLimits:
    return WorkbenchRuntimeLimits(
        max_active_jobs=_env_int("WORKBENCH_MAX_ACTIVE_JOBS", default=2, minimum=1, maximum=32),
        default_timeout_s=_env_optional_int("WORKBENCH_DEFAULT_TIMEOUT_S", minimum=1, maximum=86400),
        cancel_grace_s=_env_int("WORKBENCH_CANCEL_GRACE_S", default=5, minimum=1, maximum=60),
        event_page_max=_env_int("WORKBENCH_EVENT_PAGE_MAX", default=5000, minimum=100, maximum=50000),
    )


def deployment_config_from_env() -> WorkbenchDeploymentConfig:
    return WorkbenchDeploymentConfig(
        runtime_profile=_clean_env("WORKBENCH_RUNTIME_PROFILE", default="auto"),
        image_kind=_clean_env("WORKBENCH_IMAGE_KIND", default="backend"),
        release_id=_clean_env("WORKBENCH_RELEASE_ID", default="local"),
        script_update_mode=_clean_env("WORKBENCH_SCRIPT_UPDATE_MODE", default="image_rebuild"),
        data_update_mode=_clean_env("WORKBENCH_DATA_UPDATE_MODE", default="data_build_jobs"),
        update_interface_version=_clean_env(
            "WORKBENCH_UPDATE_INTERFACE_VERSION",
            default="finsight_workbench_update_interfaces_v0.1",
        ),
    )


def env_flag(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _clean_env(name: str, *, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _env_int(name: str, *, default: int, minimum: int, maximum: int) -> int:
    value = _env_optional_int(name, minimum=minimum, maximum=maximum)
    return default if value is None else value


def _env_optional_int(name: str, *, minimum: int, maximum: int) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except ValueError:
        return None
    return max(minimum, min(parsed, maximum))
