from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


class FeatureFlagError(RuntimeError):
    pass


class FeatureFlagRegistry:
    def __init__(self, payload: Mapping[str, Any]):
        self._payload = dict(payload)
        self._flags = {str(row["flag_id"]): dict(row) for row in payload.get("flags", [])}

    @classmethod
    def from_path(cls, path: str | Path) -> "FeatureFlagRegistry":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def default_mode(self, flag_id: str) -> str:
        return str(self._flag(flag_id).get("default_mode", "off"))

    def authorize(self, flag_id: str, *, mode: str, consumer: str, grants: set[str] | frozenset[str]) -> None:
        flag = self._flag(flag_id)
        if mode not in flag.get("allowed_modes", []):
            raise FeatureFlagError("unsupported_flag_mode")
        if mode == "off":
            raise FeatureFlagError("feature_flag_off")
        if consumer in flag.get("forbidden_consumers", []):
            raise FeatureFlagError("shadow_authority_violation")
        if consumer not in flag.get("allowed_consumers", []):
            raise FeatureFlagError("consumer_not_allowlisted")
        required = set(flag.get("required_capability_grants", []))
        if not required.issubset(set(grants)):
            raise FeatureFlagError("permission_denied")

    def _flag(self, flag_id: str) -> dict[str, Any]:
        try:
            return self._flags[flag_id]
        except KeyError as exc:
            raise FeatureFlagError("unknown_feature_flag") from exc
