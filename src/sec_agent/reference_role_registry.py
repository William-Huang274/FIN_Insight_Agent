from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping


REFERENCE_ROLE_REGISTRY_SCHEMA = (
    "fin_ia_0_1_3_reference_role_registry_v1_0"
)
DEFAULT_REFERENCE_ROLE_REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_3_reference_role_registry_v1_0.json"
)
REFERENCE_ROLE_IDS = (
    "repository_resource",
    "package_relative_audit",
    "external_content",
    "restricted_runtime_audit",
    "model_run_report",
    "semantic_followup",
)

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "registry_id",
        "status",
        "policy",
        "roles",
        "field_rules",
        "value_rules",
        "rule_canonical_digest",
    }
)
_ROLE_FIELDS = frozenset(
    {"role_id", "closure_behavior", "business_promotable"}
)
_FIELD_RULE_FIELDS = frozenset(
    {"rule_id", "field", "role", "reason"}
)
_VALUE_RULE_FIELDS = frozenset(
    {"rule_id", "matcher", "values", "role", "reason"}
)
_MATCHERS = frozenset(
    {
        "empty",
        "path_root",
        "path_prefix",
        "exact_value",
        "external_scheme",
        "windows_absolute_path",
        "posix_absolute_path",
        "semantic_identifier",
    }
)
_REPOSITORY_LIKE_SUFFIXES = (
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".toml",
    ".yaml",
    ".yml",
)
_POLICY = {
    "registry_is_single_source_of_truth": True,
    "field_rules_precede_value_rules": True,
    "unknown_reference_role_behavior": "collect_all_fail_closed",
    "repository_resource_behavior": "enter_tracked_or_typed_closure",
    "semantic_followup_path_shape_reclassification_forbidden": True,
    "restricted_runtime_audit_business_promotable": False,
    "raw_evidence_business_promotion_separate": True,
    "duplicate_or_rule_order_drift_fails_closed": True,
}


class ReferenceRoleRegistryError(RuntimeError):
    """Stable failure at the typed reference-role authority boundary."""

    def __init__(
        self,
        code: str,
        *,
        failure_envelope: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.failure_envelope = (
            dict(failure_envelope) if failure_envelope is not None else None
        )
        super().__init__(code)


@dataclass(frozen=True)
class ReferenceRoleRule:
    rule_id: str
    role: str
    matcher: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceRoleObservation:
    document_ref: str
    json_pointer: str
    field: str
    value: str
    role: str | None
    rule_id: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "document_ref": self.document_ref,
            "json_pointer": self.json_pointer,
            "field": self.field,
            "value": self.value,
            "role": self.role,
            "rule_id": self.rule_id,
        }


@dataclass(frozen=True)
class ReferenceRoleReport:
    observations: tuple[ReferenceRoleObservation, ...]
    role_counts: tuple[tuple[str, int], ...]
    observation_digest: str

    @property
    def unknowns(self) -> tuple[ReferenceRoleObservation, ...]:
        return tuple(row for row in self.observations if row.role is None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "fin_ia_reference_role_collect_all_report_v1_0",
            "observation_count": len(self.observations),
            "role_counts": {key: value for key, value in self.role_counts},
            "unknown_count": len(self.unknowns),
            "observation_digest": self.observation_digest,
            "unknown_observations": [row.as_dict() for row in self.unknowns],
        }

    def failure_envelope(self) -> dict[str, Any]:
        return {
            "schema_version": "fin_ia_typed_reference_role_failure_v1_0",
            "phase": "repository_reference_role_compilation",
            "code": "hermetic_repository_reference_roles_unknown",
            "unknown_count": len(self.unknowns),
            "observation_digest": self.observation_digest,
            "unknown_observations": [row.as_dict() for row in self.unknowns],
            "business_promotable": False,
        }


@dataclass(frozen=True)
class ReferenceRoleRegistry:
    registry_ref: str
    registry_id: str
    roles: tuple[str, ...]
    field_rules: tuple[ReferenceRoleRule, ...]
    value_rules: tuple[ReferenceRoleRule, ...]
    rule_canonical_digest: str

    def package_paths(self) -> tuple[Path, ...]:
        return (Path(self.registry_ref),)

    def classify(
        self,
        *,
        document_ref: str,
        json_pointer: str,
        field: str,
        value: str,
    ) -> ReferenceRoleObservation:
        for rule in self.field_rules:
            if field in rule.values:
                return ReferenceRoleObservation(
                    document_ref=document_ref,
                    json_pointer=json_pointer,
                    field=field,
                    value=value,
                    role=rule.role,
                    rule_id=rule.rule_id,
                )
        for rule in self.value_rules:
            if _matches(rule.matcher, rule.values, value):
                return ReferenceRoleObservation(
                    document_ref=document_ref,
                    json_pointer=json_pointer,
                    field=field,
                    value=value,
                    role=rule.role,
                    rule_id=rule.rule_id,
                )
        return ReferenceRoleObservation(
            document_ref=document_ref,
            json_pointer=json_pointer,
            field=field,
            value=value,
            role=None,
            rule_id=None,
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
            raise ReferenceRoleRegistryError(
                f"reference_role_registry_duplicate_json_key:{key}"
            )
        output[key] = value
    return output


def _strict_json_bytes(value: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(
            value.decode("utf-8"),
            object_pairs_hook=_strict_object,
        )
    except ReferenceRoleRegistryError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceRoleRegistryError(
            "reference_role_registry_json_invalid"
        ) from exc
    if not isinstance(parsed, dict):
        raise ReferenceRoleRegistryError(
            "reference_role_registry_json_invalid"
        )
    return parsed


def _nonblank(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReferenceRoleRegistryError(code)
    return value.strip()


def _registry_path(root: Path, value: str) -> Path:
    normalized = value.strip().replace("\\", "/")
    candidate = Path(normalized)
    if (
        not normalized
        or candidate.is_absolute()
        or ".." in candidate.parts
        or normalized != candidate.as_posix()
    ):
        raise ReferenceRoleRegistryError(
            "reference_role_registry_path_forbidden"
        )
    lexical = root / candidate
    resolved = lexical.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ReferenceRoleRegistryError(
            "reference_role_registry_symlink_escape"
        ) from exc
    if not lexical.is_file():
        raise ReferenceRoleRegistryError(
            f"reference_role_registry_missing:{normalized}"
        )
    return candidate


def _normalized_values(value: Any, code: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ReferenceRoleRegistryError(code)
    output = tuple(str(item).strip() for item in value)
    if not output or any(not item for item in output):
        raise ReferenceRoleRegistryError(code)
    if list(output) != sorted(set(output)):
        raise ReferenceRoleRegistryError(
            "reference_role_registry_rule_values_not_canonical"
        )
    return output


def load_reference_role_registry(
    repository_root: str | Path,
    registry_ref: str = DEFAULT_REFERENCE_ROLE_REGISTRY_REF,
) -> ReferenceRoleRegistry:
    root = Path(repository_root).resolve()
    relative = _registry_path(root, registry_ref)
    document = _strict_json_bytes((root / relative).read_bytes())
    if set(document) != _TOP_LEVEL_FIELDS:
        raise ReferenceRoleRegistryError(
            "reference_role_registry_top_level_invalid"
        )
    if document["schema_version"] != REFERENCE_ROLE_REGISTRY_SCHEMA:
        raise ReferenceRoleRegistryError(
            "reference_role_registry_schema_invalid"
        )
    if document["status"] != "typed_reference_role_authority":
        raise ReferenceRoleRegistryError(
            "reference_role_registry_status_invalid"
        )
    policy = document["policy"]
    if (
        not isinstance(policy, Mapping)
        or set(policy) != set(_POLICY)
        or any(policy.get(key) != value for key, value in _POLICY.items())
    ):
        raise ReferenceRoleRegistryError(
            "reference_role_registry_policy_invalid"
        )

    raw_roles = document["roles"]
    if not isinstance(raw_roles, list):
        raise ReferenceRoleRegistryError(
            "reference_role_registry_roles_invalid"
        )
    roles: list[str] = []
    for raw in raw_roles:
        if not isinstance(raw, Mapping) or set(raw) != _ROLE_FIELDS:
            raise ReferenceRoleRegistryError(
                "reference_role_registry_role_invalid"
            )
        role = _nonblank(
            raw["role_id"], "reference_role_registry_role_id_invalid"
        )
        behavior = _nonblank(
            raw["closure_behavior"],
            "reference_role_registry_closure_behavior_invalid",
        )
        promotable = raw["business_promotable"]
        if type(promotable) is not bool or not behavior:
            raise ReferenceRoleRegistryError(
                "reference_role_registry_role_invalid"
            )
        if role == "repository_resource":
            if behavior != "package" or promotable is not False:
                raise ReferenceRoleRegistryError(
                    "reference_role_registry_repository_role_invalid"
                )
        elif behavior != "observe_not_package" or promotable is not False:
            raise ReferenceRoleRegistryError(
                "reference_role_registry_nonrepository_role_invalid"
            )
        roles.append(role)
    if tuple(roles) != REFERENCE_ROLE_IDS:
        raise ReferenceRoleRegistryError(
            "reference_role_registry_roles_not_exact"
        )

    rule_ids: set[str] = set()
    field_rules: list[ReferenceRoleRule] = []
    seen_fields: set[str] = set()
    raw_field_rules = document["field_rules"]
    if not isinstance(raw_field_rules, list) or not raw_field_rules:
        raise ReferenceRoleRegistryError(
            "reference_role_registry_field_rules_invalid"
        )
    for raw in raw_field_rules:
        if not isinstance(raw, Mapping) or set(raw) != _FIELD_RULE_FIELDS:
            raise ReferenceRoleRegistryError(
                "reference_role_registry_field_rule_invalid"
            )
        rule_id = _nonblank(
            raw["rule_id"], "reference_role_registry_rule_id_invalid"
        )
        field = _nonblank(
            raw["field"], "reference_role_registry_field_invalid"
        )
        role = _nonblank(
            raw["role"], "reference_role_registry_rule_role_invalid"
        )
        _nonblank(raw["reason"], "reference_role_registry_reason_invalid")
        if rule_id in rule_ids or field in seen_fields or role not in roles:
            raise ReferenceRoleRegistryError(
                "reference_role_registry_field_rule_invalid"
            )
        rule_ids.add(rule_id)
        seen_fields.add(field)
        field_rules.append(
            ReferenceRoleRule(rule_id, role, "field", (field,))
        )

    value_rules: list[ReferenceRoleRule] = []
    raw_value_rules = document["value_rules"]
    if not isinstance(raw_value_rules, list) or not raw_value_rules:
        raise ReferenceRoleRegistryError(
            "reference_role_registry_value_rules_invalid"
        )
    for raw in raw_value_rules:
        if not isinstance(raw, Mapping) or set(raw) != _VALUE_RULE_FIELDS:
            raise ReferenceRoleRegistryError(
                "reference_role_registry_value_rule_invalid"
            )
        rule_id = _nonblank(
            raw["rule_id"], "reference_role_registry_rule_id_invalid"
        )
        matcher = _nonblank(
            raw["matcher"], "reference_role_registry_matcher_invalid"
        )
        role = _nonblank(
            raw["role"], "reference_role_registry_rule_role_invalid"
        )
        values = _normalized_values(
            raw["values"], "reference_role_registry_rule_values_invalid"
        )
        _nonblank(raw["reason"], "reference_role_registry_reason_invalid")
        if (
            rule_id in rule_ids
            or matcher not in _MATCHERS
            or role not in roles
        ):
            raise ReferenceRoleRegistryError(
                "reference_role_registry_value_rule_invalid"
            )
        if matcher in {"empty", "windows_absolute_path", "posix_absolute_path", "semantic_identifier"} and values != ("enabled",):
            raise ReferenceRoleRegistryError(
                "reference_role_registry_marker_rule_invalid"
            )
        rule_ids.add(rule_id)
        value_rules.append(
            ReferenceRoleRule(rule_id, role, matcher, values)
        )

    ordered_rule_ids = [
        *(row.rule_id for row in field_rules),
        *(row.rule_id for row in value_rules),
    ]
    if ordered_rule_ids != sorted(ordered_rule_ids):
        raise ReferenceRoleRegistryError(
            "reference_role_registry_rule_order_invalid"
        )

    canonical_rules = {
        "roles": raw_roles,
        "field_rules": raw_field_rules,
        "value_rules": raw_value_rules,
    }
    digest = _sha256_bytes(_canonical_bytes(canonical_rules))
    if document["rule_canonical_digest"] != digest:
        raise ReferenceRoleRegistryError(
            "reference_role_registry_canonical_digest_drift"
        )
    return ReferenceRoleRegistry(
        registry_ref=relative.as_posix(),
        registry_id=_nonblank(
            document["registry_id"],
            "reference_role_registry_id_invalid",
        ),
        roles=tuple(roles),
        field_rules=tuple(field_rules),
        value_rules=tuple(value_rules),
        rule_canonical_digest=digest,
    )


def _matches(matcher: str, values: tuple[str, ...], value: str) -> bool:
    normalized = value.strip().replace("\\", "/")
    if matcher == "empty":
        return not normalized
    if matcher == "windows_absolute_path":
        return bool(re.match(r"^[A-Za-z]:/", normalized))
    if matcher == "posix_absolute_path":
        return normalized.startswith("/")
    if matcher == "path_root":
        return any(
            normalized == item or normalized.startswith(item + "/")
            for item in values
        )
    if matcher == "path_prefix":
        return any(normalized.startswith(item) for item in values)
    if matcher == "exact_value":
        return normalized in values
    if matcher == "external_scheme":
        match = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*):", normalized)
        return match is not None and match.group(1).lower() in values
    if matcher == "semantic_identifier":
        return (
            bool(normalized)
            and not any(marker in normalized for marker in ("/", "\\"))
            and not normalized.lower().endswith(_REPOSITORY_LIKE_SUFFIXES)
        )
    raise ReferenceRoleRegistryError(
        "reference_role_registry_matcher_unreachable"
    )


def iter_reference_strings(
    value: Any,
    *,
    pointer: str = "",
) -> Iterable[tuple[str, str, str]]:
    if isinstance(value, Mapping):
        for key in sorted(value):
            item = value[key]
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            child_pointer = f"{pointer}/{escaped}"
            if (
                isinstance(item, str)
                and (key == "ref" or str(key).endswith("_ref"))
            ):
                yield str(key), item, child_pointer
            else:
                yield from iter_reference_strings(
                    item,
                    pointer=child_pointer,
                )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_reference_strings(
                item,
                pointer=f"{pointer}/{index}",
            )


def collect_reference_roles(
    registry: ReferenceRoleRegistry,
    documents: Iterable[tuple[str, Mapping[str, Any]]],
) -> ReferenceRoleReport:
    observations = [
        registry.classify(
            document_ref=document_ref,
            json_pointer=pointer,
            field=field,
            value=value,
        )
        for document_ref, document in documents
        for field, value, pointer in iter_reference_strings(document)
    ]
    observations.sort(
        key=lambda row: (
            row.document_ref,
            row.json_pointer,
            row.field,
            row.value,
            row.role or "",
            row.rule_id or "",
        )
    )
    counts = {
        role: sum(row.role == role for row in observations)
        for role in REFERENCE_ROLE_IDS
    }
    counts["unknown"] = sum(row.role is None for row in observations)
    digest = _sha256_bytes(
        _canonical_bytes([row.as_dict() for row in observations])
    )
    return ReferenceRoleReport(
        observations=tuple(observations),
        role_counts=tuple((key, counts[key]) for key in (*REFERENCE_ROLE_IDS, "unknown")),
        observation_digest=digest,
    )
