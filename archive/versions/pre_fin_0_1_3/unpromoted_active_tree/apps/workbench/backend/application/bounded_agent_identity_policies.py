from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF = (
    "fin01.s3.cell_scoped_research_identity:v1"
)
S3_CELL_SCOPED_RESEARCH_IDENTITY_KINDS = (
    "claim",
    "what_would_change",
)
S3_CELL_SCOPED_RESEARCH_IDENTITY_FAILURE_SUBTYPES = (
    "duplicate_local_id_same_cell",
    "raw_local_id_cross_cell_ambiguous",
    "scoped_ref_duplicate",
    "scoped_ref_mismatch",
    "unknown_scoped_ref",
)


@dataclass(frozen=True, order=True)
class CellScopedResearchRef:
    identity_kind: str
    program_cell_id: str
    local_id: str

    def __post_init__(self) -> None:
        if (
            self.identity_kind not in S3_CELL_SCOPED_RESEARCH_IDENTITY_KINDS
            or not isinstance(self.program_cell_id, str)
            or not self.program_cell_id.strip()
            or not isinstance(self.local_id, str)
            or not self.local_id.strip()
        ):
            raise ValueError("s3_cell_scoped_research_ref_invalid")

    @property
    def runtime_key(self) -> tuple[str, str, str]:
        return (
            self.identity_kind,
            self.program_cell_id,
            self.local_id,
        )

    def to_payload(self) -> dict[str, str]:
        return {
            "identity_kind": self.identity_kind,
            "program_cell_id": self.program_cell_id,
            "local_id": self.local_id,
        }

    @property
    def scoped_ref_digest(self) -> str:
        encoded = json.dumps(
            self.to_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    @property
    def validation_alias(self) -> str:
        return f"scoped:{self.scoped_ref_digest}"


@dataclass(frozen=True)
class ScopedIdentityViolation:
    identity_kind: str
    failure_subtype: str
    failing_item_count: int

    def __post_init__(self) -> None:
        if (
            self.identity_kind not in S3_CELL_SCOPED_RESEARCH_IDENTITY_KINDS
            or self.failure_subtype
            not in S3_CELL_SCOPED_RESEARCH_IDENTITY_FAILURE_SUBTYPES
            or type(self.failing_item_count) is not int
            or self.failing_item_count <= 0
        ):
            raise ValueError("s3_cell_scoped_identity_violation_invalid")


class CellScopedResearchIdentityPolicy:
    """One typed namespace contract shared by Specialist downstream consumers."""

    contract_ref = S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF

    @staticmethod
    def wire_schema(identity_kind: str) -> dict[str, str]:
        if identity_kind not in S3_CELL_SCOPED_RESEARCH_IDENTITY_KINDS:
            raise ValueError("s3_cell_scoped_research_identity_kind_invalid")
        return {
            "identity_kind": identity_kind,
            "program_cell_id": "exact supplied program_cell_id",
            "local_id": f"exact supplied local {identity_kind} id",
        }

    @staticmethod
    def ref(
        identity_kind: str,
        program_cell_id: str,
        local_id: str,
    ) -> CellScopedResearchRef:
        return CellScopedResearchRef(
            identity_kind=str(identity_kind),
            program_cell_id=str(program_cell_id),
            local_id=str(local_id),
        )

    @staticmethod
    def parse(
        value: Any,
        *,
        expected_kind: str,
    ) -> CellScopedResearchRef | ScopedIdentityViolation:
        if (
            not isinstance(value, Mapping)
            or set(value)
            != {"identity_kind", "program_cell_id", "local_id"}
        ):
            return ScopedIdentityViolation(
                identity_kind=expected_kind,
                failure_subtype="scoped_ref_mismatch",
                failing_item_count=1,
            )
        try:
            ref = CellScopedResearchRef(
                identity_kind=str(value.get("identity_kind") or ""),
                program_cell_id=str(value.get("program_cell_id") or ""),
                local_id=str(value.get("local_id") or ""),
            )
        except ValueError:
            return ScopedIdentityViolation(
                identity_kind=expected_kind,
                failure_subtype="scoped_ref_mismatch",
                failing_item_count=1,
            )
        if ref.identity_kind != expected_kind:
            return ScopedIdentityViolation(
                identity_kind=expected_kind,
                failure_subtype="scoped_ref_mismatch",
                failing_item_count=1,
            )
        return ref

    @classmethod
    def derive_surface(
        cls,
        specialist_outputs: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any] | ScopedIdentityViolation:
        cells: list[dict[str, Any]] = []
        observed_cells: set[str] = set()
        observed_scoped: set[tuple[str, str, str]] = set()
        raw_owners: dict[tuple[str, str], set[str]] = {}
        for specialist in specialist_outputs:
            cell_id = str(specialist.get("program_cell_id") or "")
            if not cell_id or cell_id in observed_cells:
                return ScopedIdentityViolation(
                    identity_kind="claim",
                    failure_subtype="scoped_ref_mismatch",
                    failing_item_count=1,
                )
            observed_cells.add(cell_id)
            claim_refs: list[dict[str, str]] = []
            task_refs: list[dict[str, str]] = []
            task_claim_bindings: list[dict[str, dict[str, str]]] = []
            local_claims: set[str] = set()
            local_tasks: set[str] = set()
            for claim in specialist.get("judgment_layer", ()):
                local_id = str(
                    claim.get("claim_id") if isinstance(claim, Mapping) else ""
                )
                if not local_id or local_id in local_claims:
                    return ScopedIdentityViolation(
                        identity_kind="claim",
                        failure_subtype="duplicate_local_id_same_cell",
                        failing_item_count=1,
                    )
                local_claims.add(local_id)
                ref = cls.ref("claim", cell_id, local_id)
                if ref.runtime_key in observed_scoped:
                    return ScopedIdentityViolation(
                        identity_kind="claim",
                        failure_subtype="scoped_ref_duplicate",
                        failing_item_count=1,
                    )
                observed_scoped.add(ref.runtime_key)
                raw_owners.setdefault(("claim", local_id), set()).add(cell_id)
                claim_refs.append(ref.to_payload())
            for task in specialist.get("what_would_change", ()):
                local_id = str(
                    task.get("task_id") if isinstance(task, Mapping) else ""
                )
                claim_local_id = str(
                    task.get("claim_id") if isinstance(task, Mapping) else ""
                )
                if not local_id or local_id in local_tasks:
                    return ScopedIdentityViolation(
                        identity_kind="what_would_change",
                        failure_subtype="duplicate_local_id_same_cell",
                        failing_item_count=1,
                    )
                if claim_local_id not in local_claims:
                    return ScopedIdentityViolation(
                        identity_kind="claim",
                        failure_subtype="unknown_scoped_ref",
                        failing_item_count=1,
                    )
                local_tasks.add(local_id)
                task_ref = cls.ref("what_would_change", cell_id, local_id)
                claim_ref = cls.ref("claim", cell_id, claim_local_id)
                if task_ref.runtime_key in observed_scoped:
                    return ScopedIdentityViolation(
                        identity_kind="what_would_change",
                        failure_subtype="scoped_ref_duplicate",
                        failing_item_count=1,
                    )
                observed_scoped.add(task_ref.runtime_key)
                raw_owners.setdefault(
                    ("what_would_change", local_id), set()
                ).add(cell_id)
                task_refs.append(task_ref.to_payload())
                task_claim_bindings.append(
                    {
                        "task_ref": task_ref.to_payload(),
                        "claim_ref": claim_ref.to_payload(),
                    }
                )
            cells.append(
                {
                    "program_cell_id": cell_id,
                    "claim_refs": claim_refs,
                    "what_would_change_refs": task_refs,
                    "task_claim_bindings": task_claim_bindings,
                }
            )
        return {
            "identity_contract_ref": cls.contract_ref,
            "cells": cells,
            "raw_local_id_cross_cell_ambiguity_counts": {
                kind: sum(
                    1
                    for (owner_kind, _), owners in raw_owners.items()
                    if owner_kind == kind and len(owners) > 1
                )
                for kind in S3_CELL_SCOPED_RESEARCH_IDENTITY_KINDS
            },
        }

    @classmethod
    def index_surface(
        cls,
        surface: Any,
    ) -> (
        dict[str, dict[tuple[str, str, str], CellScopedResearchRef]]
        | ScopedIdentityViolation
    ):
        if (
            not isinstance(surface, Mapping)
            or surface.get("identity_contract_ref") != cls.contract_ref
            or set(surface)
            != {
                "identity_contract_ref",
                "cells",
                "raw_local_id_cross_cell_ambiguity_counts",
            }
            or not isinstance(surface.get("cells"), list)
        ):
            return ScopedIdentityViolation(
                identity_kind="claim",
                failure_subtype="scoped_ref_mismatch",
                failing_item_count=1,
            )
        indexes = {
            kind: {} for kind in S3_CELL_SCOPED_RESEARCH_IDENTITY_KINDS
        }
        observed_cells: set[str] = set()
        binding_pairs: set[
            tuple[tuple[str, str, str], tuple[str, str, str]]
        ] = set()
        bound_task_keys: set[tuple[str, str, str]] = set()
        for cell in surface["cells"]:
            if (
                not isinstance(cell, Mapping)
                or set(cell)
                != {
                    "program_cell_id",
                    "claim_refs",
                    "what_would_change_refs",
                    "task_claim_bindings",
                }
            ):
                return ScopedIdentityViolation(
                    identity_kind="claim",
                    failure_subtype="scoped_ref_mismatch",
                    failing_item_count=1,
                )
            cell_id = str(cell.get("program_cell_id") or "")
            if not cell_id or cell_id in observed_cells:
                return ScopedIdentityViolation(
                    identity_kind="claim",
                    failure_subtype="scoped_ref_mismatch",
                    failing_item_count=1,
                )
            observed_cells.add(cell_id)
            for kind, field in (
                ("claim", "claim_refs"),
                ("what_would_change", "what_would_change_refs"),
            ):
                values = cell.get(field)
                if not isinstance(values, list):
                    return ScopedIdentityViolation(
                        identity_kind=kind,
                        failure_subtype="scoped_ref_mismatch",
                        failing_item_count=1,
                    )
                for value in values:
                    parsed = cls.parse(value, expected_kind=kind)
                    if isinstance(parsed, ScopedIdentityViolation):
                        return parsed
                    if parsed.program_cell_id != cell_id:
                        return ScopedIdentityViolation(
                            identity_kind=kind,
                            failure_subtype="scoped_ref_mismatch",
                            failing_item_count=1,
                        )
                    if parsed.runtime_key in indexes[kind]:
                        return ScopedIdentityViolation(
                            identity_kind=kind,
                            failure_subtype="scoped_ref_duplicate",
                            failing_item_count=1,
                        )
                    indexes[kind][parsed.runtime_key] = parsed
            bindings = cell.get("task_claim_bindings")
            if not isinstance(bindings, list):
                return ScopedIdentityViolation(
                    identity_kind="what_would_change",
                    failure_subtype="scoped_ref_mismatch",
                    failing_item_count=1,
                )
            for binding in bindings:
                if (
                    not isinstance(binding, Mapping)
                    or set(binding) != {"task_ref", "claim_ref"}
                ):
                    return ScopedIdentityViolation(
                        identity_kind="what_would_change",
                        failure_subtype="scoped_ref_mismatch",
                        failing_item_count=1,
                    )
                task_ref = cls.parse(
                    binding.get("task_ref"),
                    expected_kind="what_would_change",
                )
                claim_ref = cls.parse(
                    binding.get("claim_ref"),
                    expected_kind="claim",
                )
                if isinstance(task_ref, ScopedIdentityViolation):
                    return task_ref
                if isinstance(claim_ref, ScopedIdentityViolation):
                    return claim_ref
                pair = (task_ref.runtime_key, claim_ref.runtime_key)
                if (
                    task_ref.program_cell_id != cell_id
                    or claim_ref.program_cell_id != cell_id
                    or task_ref.runtime_key
                    not in indexes["what_would_change"]
                    or claim_ref.runtime_key not in indexes["claim"]
                    or task_ref.runtime_key in bound_task_keys
                    or pair in binding_pairs
                ):
                    return ScopedIdentityViolation(
                        identity_kind="what_would_change",
                        failure_subtype="scoped_ref_mismatch",
                        failing_item_count=1,
                    )
                binding_pairs.add(pair)
                bound_task_keys.add(task_ref.runtime_key)
        if {
            task_key for task_key, _ in binding_pairs
        } != set(indexes["what_would_change"]):
            return ScopedIdentityViolation(
                identity_kind="what_would_change",
                failure_subtype="unknown_scoped_ref",
                failing_item_count=1,
            )
        ambiguity_counts = surface.get(
            "raw_local_id_cross_cell_ambiguity_counts"
        )
        expected_ambiguity_counts = {
            kind: sum(
                1
                for local_id in {
                    key[2] for key in indexes[kind]
                }
                if sum(
                    1
                    for key in indexes[kind]
                    if key[2] == local_id
                )
                > 1
            )
            for kind in S3_CELL_SCOPED_RESEARCH_IDENTITY_KINDS
        }
        if (
            not isinstance(ambiguity_counts, Mapping)
            or set(ambiguity_counts)
            != set(S3_CELL_SCOPED_RESEARCH_IDENTITY_KINDS)
            or any(
                type(ambiguity_counts.get(kind)) is not int
                for kind in S3_CELL_SCOPED_RESEARCH_IDENTITY_KINDS
            )
            or dict(ambiguity_counts) != expected_ambiguity_counts
        ):
            return ScopedIdentityViolation(
                identity_kind="claim",
                failure_subtype="scoped_ref_mismatch",
                failing_item_count=1,
            )
        return indexes


@dataclass(frozen=True)
class CompactScopedReferenceAlias:
    """One request-scoped Provider alias for an authoritative typed ref."""

    alias: str
    ref: CellScopedResearchRef

    def to_prompt_payload(self) -> dict[str, str]:
        return {
            "alias": self.alias,
            **self.ref.to_payload(),
        }


@dataclass(frozen=True)
class CompactScopedReferenceAliasTable:
    """Closed Provider-wire codec; aliases never become canonical identity."""

    rows: tuple[CompactScopedReferenceAlias, ...]
    contract_ref: str = "fin01.s3.compact_scoped_reference_alias:v1"

    @classmethod
    def from_surface(
        cls,
        surface: Mapping[str, Any],
    ) -> CompactScopedReferenceAliasTable | ScopedIdentityViolation:
        indexes = CellScopedResearchIdentityPolicy.index_surface(surface)
        if isinstance(indexes, ScopedIdentityViolation):
            return indexes
        rows: list[CompactScopedReferenceAlias] = []
        for kind, prefix in (
            ("claim", "C"),
            ("what_would_change", "W"),
        ):
            for ordinal, ref in enumerate(indexes[kind].values(), start=1):
                if ordinal > 999:
                    return ScopedIdentityViolation(
                        identity_kind=kind,
                        failure_subtype="scoped_ref_mismatch",
                        failing_item_count=1,
                    )
                rows.append(
                    CompactScopedReferenceAlias(
                        alias=f"{prefix}{ordinal:03d}",
                        ref=ref,
                    )
                )
        return cls(rows=tuple(rows))

    @property
    def by_alias(self) -> dict[str, CellScopedResearchRef]:
        return {row.alias: row.ref for row in self.rows}

    def aliases_for_kind(self, identity_kind: str) -> tuple[str, ...]:
        if identity_kind not in S3_CELL_SCOPED_RESEARCH_IDENTITY_KINDS:
            raise ValueError("s3_cell_scoped_research_identity_kind_invalid")
        return tuple(
            row.alias
            for row in self.rows
            if row.ref.identity_kind == identity_kind
        )

    def to_prompt_payload(self) -> dict[str, Any]:
        return {
            "alias_contract_ref": self.contract_ref,
            "rows": [row.to_prompt_payload() for row in self.rows],
        }

    def expand(
        self,
        value: Any,
        *,
        expected_kind: str,
    ) -> CellScopedResearchRef | ScopedIdentityViolation:
        if expected_kind not in S3_CELL_SCOPED_RESEARCH_IDENTITY_KINDS:
            raise ValueError("s3_cell_scoped_research_identity_kind_invalid")
        if not isinstance(value, str) or not value:
            return ScopedIdentityViolation(
                identity_kind=expected_kind,
                failure_subtype="scoped_ref_mismatch",
                failing_item_count=1,
            )
        ref = self.by_alias.get(value)
        if ref is None:
            # A value that would only resolve after trimming/case-folding is a
            # malformed ref, not an unknown authoritative identity.
            normalized_aliases = {
                alias.strip().casefold() for alias in self.by_alias
            }
            subtype = (
                "scoped_ref_mismatch"
                if value.strip().casefold() in normalized_aliases
                else "unknown_scoped_ref"
            )
            return ScopedIdentityViolation(
                identity_kind=expected_kind,
                failure_subtype=subtype,
                failing_item_count=1,
            )
        if ref.identity_kind != expected_kind:
            return ScopedIdentityViolation(
                identity_kind=expected_kind,
                failure_subtype="scoped_ref_mismatch",
                failing_item_count=1,
            )
        return ref

    def expand_list(
        self,
        values: Any,
        *,
        expected_kind: str,
        allow_empty: bool,
    ) -> list[dict[str, str]] | ScopedIdentityViolation:
        if not isinstance(values, list) or (not allow_empty and not values):
            return ScopedIdentityViolation(
                identity_kind=expected_kind,
                failure_subtype="scoped_ref_mismatch",
                failing_item_count=1,
            )
        if len(values) > len(self.aliases_for_kind(expected_kind)):
            return ScopedIdentityViolation(
                identity_kind=expected_kind,
                failure_subtype="scoped_ref_mismatch",
                failing_item_count=1,
            )
        expanded: list[dict[str, str]] = []
        observed: set[str] = set()
        for value in values:
            if isinstance(value, str) and value in observed:
                return ScopedIdentityViolation(
                    identity_kind=expected_kind,
                    failure_subtype="scoped_ref_duplicate",
                    failing_item_count=1,
                )
            parsed = self.expand(value, expected_kind=expected_kind)
            if isinstance(parsed, ScopedIdentityViolation):
                return parsed
            observed.add(value)
            expanded.append(parsed.to_payload())
        return expanded
