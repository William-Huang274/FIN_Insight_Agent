from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


API_MODEL_BACKENDS = {"deepseek", "openai_compatible"}
LOCAL_MODEL_BACKENDS = {"qwen_vllm"}


@dataclass(frozen=True)
class ModelRoute:
    role: str
    call_mode: str
    backend: str
    model: str
    base_url: str
    api_key_env: str
    profile: str

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["api_key_env"] = self.api_key_env or None
        payload["requires_api_key"] = self.call_mode == "api_model_call"
        return payload


def call_mode_for_backend(backend: str) -> str:
    normalized = str(backend or "").strip()
    if normalized in API_MODEL_BACKENDS:
        return "api_model_call"
    if normalized in LOCAL_MODEL_BACKENDS:
        return "local_model_deployment"
    return "unknown_model_call"


def route_for_role(
    *,
    role: str,
    llm_backend: str,
    model: str,
    base_url: str,
    api_key_env: str = "",
    profile: str = "",
) -> ModelRoute:
    backend = str(llm_backend or "").strip()
    call_mode = call_mode_for_backend(backend)
    profile_name = str(profile or "").strip() or f"{call_mode}:{backend}"
    return ModelRoute(
        role=str(role or "unknown"),
        call_mode=call_mode,
        backend=backend,
        model=str(model or ""),
        base_url=str(base_url or ""),
        api_key_env=str(api_key_env or ""),
        profile=profile_name,
    )


def public_routes_for_backend(
    *,
    roles: list[str],
    llm_backend: str,
    model: str,
    base_url: str,
    api_key_env: str = "",
) -> dict[str, dict[str, Any]]:
    return {
        role: route_for_role(
            role=role,
            llm_backend=llm_backend,
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
        ).to_public_dict()
        for role in roles
    }
