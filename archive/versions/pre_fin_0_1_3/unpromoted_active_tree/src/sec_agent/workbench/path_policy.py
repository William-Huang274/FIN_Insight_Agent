from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ConfigDict

from .runtime_config import env_flag


class PathPolicyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_external_paths: bool
    allowed_roots: list[str]


class PathPolicyViolation(ValueError):
    def __init__(self, path: Path, allowed_roots: list[Path]):
        self.path = path
        self.allowed_roots = allowed_roots
        roots = ", ".join(str(root) for root in allowed_roots)
        super().__init__(f"path_not_allowed: {path}; allowed_roots: {roots}")


class WorkbenchPathPolicy:
    def __init__(
        self,
        *,
        repo_root: str | Path,
        extra_allowed_roots: Iterable[str | Path] = (),
        allow_external_paths: bool | None = None,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.allow_external_paths = (
            env_flag("WORKBENCH_ALLOW_EXTERNAL_PATHS", default=False)
            if allow_external_paths is None
            else bool(allow_external_paths)
        )
        roots: list[Path] = [
            self.repo_root,
            self.repo_root / "configs",
            self.repo_root / "data",
            self.repo_root / "reports",
            self.repo_root / "eval_sets",
        ]
        roots.extend(Path(value) for value in extra_allowed_roots if str(value).strip())
        env_roots = os.environ.get("WORKBENCH_ALLOWED_ROOTS", "")
        roots.extend(Path(value) for value in env_roots.split(os.pathsep) if value.strip())
        self.allowed_roots = _dedupe_resolved_roots(roots)

    def report(self) -> PathPolicyReport:
        return PathPolicyReport(
            allow_external_paths=self.allow_external_paths,
            allowed_roots=[str(root) for root in self.allowed_roots],
        )

    def resolve(self, value: str | Path, *, base: str | Path | None = None) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = Path(base).resolve() / path if base else self.repo_root / path
        resolved = path.resolve()
        self.assert_allowed(resolved)
        return resolved

    def assert_allowed(self, path: str | Path) -> None:
        resolved = Path(path).resolve()
        if self.allow_external_paths:
            return
        if not any(_is_relative_to(resolved, root) for root in self.allowed_roots):
            raise PathPolicyViolation(resolved, self.allowed_roots)


def _dedupe_resolved_roots(roots: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        resolved = root.resolve()
        key = str(resolved).lower()
        if key not in seen:
            result.append(resolved)
            seen.add(key)
    return result


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
