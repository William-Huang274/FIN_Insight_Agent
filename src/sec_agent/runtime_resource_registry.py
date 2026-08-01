from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


RUNTIME_RESOURCE_REGISTRY_SCHEMA = (
    "fin_ia_0_1_3_runtime_resource_registry_v1_0"
)
DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_3_runtime_resource_registry_v1_0.json"
)

_RESOURCE_ROW_FIELDS = frozenset(
    {
        "resource_id",
        "repo_relative_path",
        "sha256",
        "bytes",
        "classification",
        "consumer_ids",
        "load_phase",
        "required",
        "source_owner",
    }
)
_FORBIDDEN_PREFIXES = (".codex_runtime", ".git")
_RESOURCE_SUFFIXES = frozenset(
    {".json", ".jsonl", ".md", ".toml", ".yaml", ".yml"}
)
_REPOSITORY_ROOTS = frozenset(
    {"apps", "configs", "docs", "scripts", "src", "tests"}
)


class RuntimeResourceRegistryError(RuntimeError):
    """Deterministic failure at the Runtime resource authority boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class RuntimeResource:
    resource_id: str
    repo_relative_path: str
    sha256: str
    bytes: int
    classification: str
    consumer_ids: tuple[str, ...]
    load_phase: str
    required: bool
    source_owner: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "repo_relative_path": self.repo_relative_path,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "classification": self.classification,
            "consumer_ids": list(self.consumer_ids),
            "load_phase": self.load_phase,
            "required": self.required,
            "source_owner": self.source_owner,
        }


@dataclass(frozen=True)
class RuntimeResourceRegistry:
    registry_ref: str
    registry_id: str
    resources: tuple[RuntimeResource, ...]
    detector_python_refs: tuple[str, ...]
    resource_canonical_digest: str

    def by_id(self) -> dict[str, RuntimeResource]:
        return {row.resource_id: row for row in self.resources}

    def by_path(self) -> dict[str, RuntimeResource]:
        return {row.repo_relative_path: row for row in self.resources}

    def package_paths(self) -> tuple[Path, ...]:
        return tuple(
            Path(value)
            for value in sorted(
                {
                    self.registry_ref,
                    *(row.repo_relative_path for row in self.resources),
                }
            )
        )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise RuntimeResourceRegistryError(
                f"runtime_resource_registry_duplicate_json_key:{key}"
            )
        output[key] = value
    return output


def _strict_json_bytes(value: bytes, *, code: str) -> dict[str, Any]:
    try:
        parsed = json.loads(
            value.decode("utf-8"),
            object_pairs_hook=_strict_object,
        )
    except RuntimeResourceRegistryError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeResourceRegistryError(code) from exc
    if not isinstance(parsed, dict):
        raise RuntimeResourceRegistryError(code)
    return parsed


def _nonblank(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeResourceRegistryError(code)
    return value.strip()


def _literal_string_mapping(path: Path, variable_name: str) -> dict[str, str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_compatibility_adapter_parse_failed"
        ) from exc
    candidate: ast.AST | None = None
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == variable_name
        ):
            candidate = node.value
            break
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable_name
            for target in node.targets
        ):
            candidate = node.value
            break
    try:
        value = ast.literal_eval(candidate) if candidate is not None else None
    except (TypeError, ValueError) as exc:
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_compatibility_adapter_not_literal"
        ) from exc
    if (
        not isinstance(value, dict)
        or not value
        or not all(
            isinstance(key, str)
            and key.strip()
            and isinstance(item, str)
            and item.strip()
            for key, item in value.items()
        )
    ):
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_compatibility_adapter_invalid"
        )
    return {str(key): str(item) for key, item in value.items()}


def _repo_relative_path(
    repository_root: Path,
    value: Any,
    *,
    missing_code: str,
) -> Path:
    text = _nonblank(value, "runtime_resource_registry_path_invalid")
    normalized = text.replace("\\", "/")
    candidate = Path(normalized)
    if (
        normalized != candidate.as_posix()
        or candidate.is_absolute()
        or ".." in candidate.parts
        or any(
            normalized == prefix or normalized.startswith(prefix + "/")
            for prefix in _FORBIDDEN_PREFIXES
        )
    ):
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_path_forbidden"
        )
    lexical = repository_root / candidate
    resolved = lexical.resolve()
    try:
        resolved.relative_to(repository_root)
    except ValueError as exc:
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_symlink_escape"
        ) from exc
    if not lexical.is_file():
        raise RuntimeResourceRegistryError(f"{missing_code}:{normalized}")
    return candidate


def load_runtime_resource_registry(
    repository_root: str | Path,
    registry_ref: str = DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
) -> RuntimeResourceRegistry:
    root = Path(repository_root).resolve()
    relative = _repo_relative_path(
        root,
        registry_ref,
        missing_code="runtime_resource_registry_missing",
    )
    registry = _strict_json_bytes(
        (root / relative).read_bytes(),
        code="runtime_resource_registry_json_invalid",
    )
    expected_top_level = {
        "schema_version",
        "registry_id",
        "status",
        "policy",
        "detector_python_refs",
        "resource_count",
        "resource_bytes",
        "resource_canonical_digest",
        "resources",
    }
    if set(registry) != expected_top_level:
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_top_level_invalid"
        )
    if registry["schema_version"] != RUNTIME_RESOURCE_REGISTRY_SCHEMA:
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_schema_invalid"
        )
    if registry["status"] != "tracked_typed_runtime_resource_authority":
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_status_invalid"
        )
    policy = registry["policy"]
    required_policy = {
        "registry_is_source_of_truth": True,
        "static_scanner_is_detector_only": True,
        "direct_unregistered_runtime_read_fails_closed": True,
        "missing_unknown_duplicate_or_digest_drift_fails_closed": True,
        "permutation_or_cross_version_fails_closed": True,
        "ignored_untracked_codex_runtime_and_git_forbidden": True,
        "traversal_and_symlink_escape_forbidden": True,
    }
    if (
        not isinstance(policy, Mapping)
        or set(policy) != set(required_policy)
        or any(
            policy.get(key) is not expected
            for key, expected in required_policy.items()
        )
    ):
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_policy_invalid"
        )

    detector_values = registry["detector_python_refs"]
    if not isinstance(detector_values, list):
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_detector_refs_invalid"
        )
    detector_refs: list[str] = []
    for value in detector_values:
        detector_path = _repo_relative_path(
            root,
            value,
            missing_code="runtime_resource_registry_detector_source_missing",
        )
        if detector_path.suffix != ".py":
            raise RuntimeResourceRegistryError(
                "runtime_resource_registry_detector_ref_not_python"
            )
        detector_refs.append(detector_path.as_posix())
    if detector_refs != sorted(set(detector_refs)):
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_detector_refs_not_canonical"
        )

    raw_rows = registry["resources"]
    if not isinstance(raw_rows, list) or not raw_rows:
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_rows_invalid"
        )
    resources: list[RuntimeResource] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for raw in raw_rows:
        if not isinstance(raw, Mapping) or set(raw) != _RESOURCE_ROW_FIELDS:
            raise RuntimeResourceRegistryError(
                "runtime_resource_registry_row_invalid"
            )
        resource_id = _nonblank(
            raw["resource_id"],
            "runtime_resource_registry_resource_id_invalid",
        )
        if resource_id in seen_ids:
            raise RuntimeResourceRegistryError(
                "runtime_resource_registry_duplicate_resource_id"
            )
        path = _repo_relative_path(
            root,
            raw["repo_relative_path"],
            missing_code="runtime_resource_registry_required_resource_missing",
        )
        path_text = path.as_posix()
        if path.suffix.lower() not in _RESOURCE_SUFFIXES:
            raise RuntimeResourceRegistryError(
                "runtime_resource_registry_resource_suffix_invalid"
            )
        if path_text in seen_paths:
            raise RuntimeResourceRegistryError(
                "runtime_resource_registry_duplicate_resource_path"
            )
        expected_sha = _nonblank(
            raw["sha256"],
            "runtime_resource_registry_sha256_invalid",
        ).lower()
        expected_bytes = raw["bytes"]
        consumer_values = raw["consumer_ids"]
        normalized_consumers = (
            [str(item).strip() for item in consumer_values]
            if isinstance(consumer_values, list)
            else []
        )
        if (
            not re.fullmatch(r"[0-9a-f]{64}", expected_sha)
            or type(expected_bytes) is not int
            or expected_bytes < 0
            or not isinstance(consumer_values, list)
            or not consumer_values
            or not all(
                isinstance(item, str) and item.strip()
                for item in consumer_values
            )
            or normalized_consumers != sorted(set(normalized_consumers))
            or type(raw["required"]) is not bool
            or raw["required"] is not True
        ):
            raise RuntimeResourceRegistryError(
                "runtime_resource_registry_row_contract_invalid"
            )
        value = (root / path).read_bytes()
        if len(value) != expected_bytes or _sha256_bytes(value) != expected_sha:
            raise RuntimeResourceRegistryError(
                f"runtime_resource_registry_digest_or_bytes_drift:{resource_id}"
            )
        resources.append(
            RuntimeResource(
                resource_id=resource_id,
                repo_relative_path=path_text,
                sha256=expected_sha,
                bytes=expected_bytes,
                classification=_nonblank(
                    raw["classification"],
                    "runtime_resource_registry_classification_invalid",
                ),
                consumer_ids=tuple(normalized_consumers),
                load_phase=_nonblank(
                    raw["load_phase"],
                    "runtime_resource_registry_load_phase_invalid",
                ),
                required=True,
                source_owner=_nonblank(
                    raw["source_owner"],
                    "runtime_resource_registry_source_owner_invalid",
                ),
            )
        )
        seen_ids.add(resource_id)
        seen_paths.add(path_text)
    if [row.resource_id for row in resources] != sorted(seen_ids):
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_resource_order_invalid"
        )
    research_adapter_ref = "src/sec_agent/research_skills.py"
    if research_adapter_ref in detector_refs:
        mapping = _literal_string_mapping(
            root / research_adapter_ref,
            "SKILL_FILES",
        )
        adapter_rows = {
            row.resource_id: row.repo_relative_path
            for row in resources
            if row.classification == "prompt_skill_instruction"
        }
        expected_adapter_rows = {
            f"research_skill.{skill_id}": (
                "src/sec_agent/prompts/skills/" + filename
            )
            for skill_id, filename in mapping.items()
        }
        if adapter_rows != expected_adapter_rows:
            raise RuntimeResourceRegistryError(
                "runtime_resource_registry_compatibility_adapter_drift"
            )
    canonical_rows = [row.as_dict() for row in resources]
    canonical_digest = _sha256_bytes(_canonical_bytes(canonical_rows))
    if (
        registry["resource_count"] != len(resources)
        or registry["resource_bytes"] != sum(row.bytes for row in resources)
        or registry["resource_canonical_digest"] != canonical_digest
    ):
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_aggregate_drift"
        )
    return RuntimeResourceRegistry(
        registry_ref=relative.as_posix(),
        registry_id=_nonblank(
            registry["registry_id"],
            "runtime_resource_registry_id_invalid",
        ),
        resources=tuple(resources),
        detector_python_refs=tuple(detector_refs),
        resource_canonical_digest=canonical_digest,
    )


def registered_runtime_resource(
    repository_root: str | Path,
    resource_id: str,
    *,
    registry_ref: str = DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
) -> RuntimeResource:
    registry = load_runtime_resource_registry(repository_root, registry_ref)
    try:
        return registry.by_id()[str(resource_id)]
    except KeyError as exc:
        raise RuntimeResourceRegistryError(
            f"runtime_resource_registry_unknown_resource_id:{resource_id}"
        ) from exc


def resolve_registered_runtime_resource(
    repository_root: str | Path,
    resource_id: str,
    *,
    registry_ref: str = DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
) -> Path:
    root = Path(repository_root).resolve()
    row = registered_runtime_resource(
        root,
        resource_id,
        registry_ref=registry_ref,
    )
    return root / Path(row.repo_relative_path)


def read_registered_runtime_bytes(
    repository_root: str | Path,
    resource_id: str,
    *,
    registry_ref: str = DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
) -> bytes:
    return resolve_registered_runtime_resource(
        repository_root,
        resource_id,
        registry_ref=registry_ref,
    ).read_bytes()


def read_registered_runtime_text(
    repository_root: str | Path,
    resource_id: str,
    *,
    registry_ref: str = DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
) -> str:
    try:
        return read_registered_runtime_bytes(
            repository_root,
            resource_id,
            registry_ref=registry_ref,
        ).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeResourceRegistryError(
            f"runtime_resource_registry_resource_not_utf8:{resource_id}"
        ) from exc


def read_registered_runtime_json(
    repository_root: str | Path,
    resource_id: str,
    *,
    registry_ref: str = DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
) -> dict[str, Any]:
    return _strict_json_bytes(
        read_registered_runtime_bytes(
            repository_root,
            resource_id,
            registry_ref=registry_ref,
        ),
        code=f"runtime_resource_registry_resource_json_invalid:{resource_id}",
    )


def detect_repo_relative_runtime_resource_literals(
    repository_root: str | Path,
    registry: RuntimeResourceRegistry | None = None,
) -> tuple[str, ...]:
    """Detect static resource literals; the registry remains authoritative."""

    root = Path(repository_root).resolve()
    current = registry or load_runtime_resource_registry(root)
    detected: set[str] = set()
    for source_ref in current.detector_python_refs:
        source = root / source_ref
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), str(source))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            raise RuntimeResourceRegistryError(
                f"runtime_resource_registry_detector_parse_failed:{source_ref}"
            ) from exc
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            literal = node.value.strip().replace("\\", "/")
            candidate = Path(literal)
            if (
                candidate.suffix.lower() in _RESOURCE_SUFFIXES
                and candidate.parts
                and candidate.parts[0] in _REPOSITORY_ROOTS
            ):
                detected.add(candidate.as_posix())
            elif (
                source_ref == "src/sec_agent/research_skills.py"
                and candidate.suffix.lower() == ".md"
                and len(candidate.parts) == 1
            ):
                detected.add(
                    (Path("src/sec_agent/prompts/skills") / candidate).as_posix()
                )
    return tuple(sorted(detected))


def assert_no_unregistered_runtime_resource_literals(
    repository_root: str | Path,
    *,
    registry_ref: str = DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
    ignored_literals: Sequence[str] = (),
) -> tuple[str, ...]:
    registry = load_runtime_resource_registry(repository_root, registry_ref)
    registered = set(registry.by_path())
    ignored = {str(value).replace("\\", "/") for value in ignored_literals}
    detected = set(
        detect_repo_relative_runtime_resource_literals(
            repository_root,
            registry,
        )
    )
    unknown = sorted(detected - registered - ignored)
    if unknown:
        raise RuntimeResourceRegistryError(
            "runtime_resource_registry_unregistered_literal:"
            + ",".join(unknown)
        )
    return tuple(sorted(detected))
