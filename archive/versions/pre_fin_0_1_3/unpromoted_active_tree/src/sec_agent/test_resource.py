from __future__ import annotations

from pathlib import Path


class RepositoryTestResourceError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def repository_test_resource(
    repository_root: Path,
    dependency_bundle_id: str,
    repository_relative_path: str,
) -> Path:
    """Resolve a declared non-Python test resource without host escape.

    The bundle id is intentionally present at the call site so the static
    contract compiler can connect the read to a typed dependency resolver.
    Runtime membership is still compiled from the registry; this helper owns
    only path safety and an auditable call shape.
    """

    if not dependency_bundle_id.strip():
        raise RepositoryTestResourceError(
            "repository_test_resource_bundle_id_missing"
        )
    normalized = repository_relative_path.replace("\\", "/")
    relative = Path(normalized)
    if relative.is_absolute() or ".." in relative.parts:
        raise RepositoryTestResourceError(
            "repository_test_resource_path_forbidden"
        )
    root = repository_root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RepositoryTestResourceError(
            "repository_test_resource_path_escape"
        ) from exc
    if not path.is_file():
        raise RepositoryTestResourceError(
            f"repository_test_resource_missing:{relative.as_posix()}"
        )
    return path
