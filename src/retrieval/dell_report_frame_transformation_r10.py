from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping, Sequence

from .dell_report_predicate_frames_r10 import (
    PredicateFrame,
    RoleBinding,
    _argument_relation_rows_for_frame,
    _semantic_signature_body_for_frame,
)
from .query_plan import canonical_digest


TRANSFORMATION_TYPES = frozenset(
    {
        "exact_slice",
        "normalized_slice",
        "bounded_window",
        "many_object_same_source",
    }
)


class FrameTransformationBindingR10Error(ValueError):
    pass


@dataclass(frozen=True)
class RoleTransformationMapping:
    mapping_id: str
    role: str
    normalized_value: str
    source_span: tuple[int, int]
    compiled_span: tuple[int, int]
    source_kind: str
    compiled_kind: str
    mapping_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "role": self.role,
            "normalized_value": self.normalized_value,
            "source_span": list(self.source_span),
            "compiled_span": list(self.compiled_span),
            "source_kind": self.source_kind,
            "compiled_kind": self.compiled_kind,
            "mapping_digest": self.mapping_digest,
        }


@dataclass(frozen=True)
class FrameTransformationBinding:
    binding_id: str
    canonical_source_family_id: str
    source_record_id: str
    source_frame_id: str
    source_frame_digest: str
    source_frame_span: tuple[int, int]
    source_semantic_signature_digest: str
    compiled_object_ids: tuple[str, ...]
    compiled_window_ids: tuple[str, ...]
    compiled_frame_id: str
    compiled_frame_digest: str
    compiled_frame_span: tuple[int, int]
    compiled_semantic_signature_digest: str
    transformation_type: str
    role_mappings: tuple[RoleTransformationMapping, ...]
    representation_digest_equal: bool
    semantic_signature_equal: bool
    loss_flags: tuple[str, ...]
    addition_flags: tuple[str, ...]
    ambiguity_flags: tuple[str, ...]
    binding_accepted: bool
    binding_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "canonical_source_family_id": self.canonical_source_family_id,
            "source_record_id": self.source_record_id,
            "source_frame_id": self.source_frame_id,
            "source_frame_digest": self.source_frame_digest,
            "source_frame_span": list(self.source_frame_span),
            "source_semantic_signature_digest": (
                self.source_semantic_signature_digest
            ),
            "compiled_object_ids": list(self.compiled_object_ids),
            "compiled_window_ids": list(self.compiled_window_ids),
            "compiled_frame_id": self.compiled_frame_id,
            "compiled_frame_digest": self.compiled_frame_digest,
            "compiled_frame_span": list(self.compiled_frame_span),
            "compiled_semantic_signature_digest": (
                self.compiled_semantic_signature_digest
            ),
            "transformation_type": self.transformation_type,
            "role_mappings": [row.as_dict() for row in self.role_mappings],
            "representation_digest_equal": self.representation_digest_equal,
            "semantic_signature_equal": self.semantic_signature_equal,
            "loss_flags": list(self.loss_flags),
            "addition_flags": list(self.addition_flags),
            "ambiguity_flags": list(self.ambiguity_flags),
            "binding_accepted": self.binding_accepted,
            "binding_digest": self.binding_digest,
        }


def _require_identifier(value: str, *, field: str) -> str:
    if not value or value.strip() != value or re.search(r"[\x00-\x1f]", value):
        raise FrameTransformationBindingR10Error(
            f"R10_transformation_invalid_identifier:{field}"
        )
    return value


def _frame_representation_body(frame: PredicateFrame) -> dict[str, Any]:
    body = frame.as_dict()
    for key in (
        "frame_id",
        "frame_digest",
        "representation_frame_digest",
    ):
        body.pop(key)
    return body


def validate_predicate_frame_r10_integrity(frame: PredicateFrame) -> None:
    expected_semantic = canonical_digest(_semantic_signature_body_for_frame(frame))
    expected_representation = canonical_digest(_frame_representation_body(frame))
    if frame.semantic_signature_digest != expected_semantic:
        raise FrameTransformationBindingR10Error(
            "R10_transformation_source_or_compiled_semantic_digest_invalid"
        )
    if (
        frame.frame_digest != expected_representation
        or frame.representation_frame_digest != expected_representation
        or frame.frame_id
        != f"FRAME::R10::{expected_representation[:24].upper()}"
    ):
        raise FrameTransformationBindingR10Error(
            "R10_transformation_source_or_compiled_representation_digest_invalid"
        )


def _relation_role_rows(frame: PredicateFrame) -> tuple[RoleBinding, ...]:
    rows: list[RoleBinding] = []
    for relation in _argument_relation_rows_for_frame(frame):
        relation_type = str(relation["relation_type"])
        normalized_value = "|".join(
            (
                f"product={relation['product']}",
                f"price={relation['price']}",
                f"object_class={relation['object_class']}",
                f"attachment={relation['attachment']}",
            )
        )
        span_start = int(relation["span_start"])
        span_end = int(relation["span_end"])
        local_start = max(0, span_start - frame.span_start)
        local_end = max(local_start, span_end - frame.span_start)
        rows.append(
            RoleBinding(
                role=f"argument_relation.{relation_type}",
                raw_text=frame.frame_text[local_start:local_end],
                normalized_value=normalized_value,
                span_start=span_start,
                span_end=span_end,
                source_kind="argument_group_relation",
            )
        )
    return tuple(rows)


def _semantic_role_rows(frame: PredicateFrame) -> tuple[RoleBinding, ...]:
    return tuple(
        sorted(
            (
                *frame.role_bindings,
                *frame.scope_bindings,
                *_relation_role_rows(frame),
            ),
            key=lambda row: (
                row.role,
                row.normalized_value,
                row.span_start,
                row.span_end,
                row.source_kind,
            ),
        )
    )


def _role_key(binding: RoleBinding) -> tuple[str, str]:
    return binding.role, binding.normalized_value


def _mapping(
    source: RoleBinding,
    compiled: RoleBinding,
) -> RoleTransformationMapping:
    core = {
        "role": source.role,
        "normalized_value": source.normalized_value,
        "source_span": (source.span_start, source.span_end),
        "compiled_span": (compiled.span_start, compiled.span_end),
        "source_kind": source.source_kind,
        "compiled_kind": compiled.source_kind,
    }
    mapping_id = f"ROLEMAP::R10::{canonical_digest(core)[:24].upper()}"
    body = {"mapping_id": mapping_id, **core}
    return RoleTransformationMapping(
        mapping_id=mapping_id,
        role=source.role,
        normalized_value=source.normalized_value,
        source_span=core["source_span"],
        compiled_span=core["compiled_span"],
        source_kind=source.source_kind,
        compiled_kind=compiled.source_kind,
        mapping_digest=canonical_digest(body),
    )


def _role_mappings(
    source_frame: PredicateFrame,
    compiled_frame: PredicateFrame,
) -> tuple[
    tuple[RoleTransformationMapping, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    source_by_key: dict[tuple[str, str], list[RoleBinding]] = defaultdict(list)
    compiled_by_key: dict[tuple[str, str], list[RoleBinding]] = defaultdict(list)
    for row in _semantic_role_rows(source_frame):
        source_by_key[_role_key(row)].append(row)
    for row in _semantic_role_rows(compiled_frame):
        compiled_by_key[_role_key(row)].append(row)

    mappings: list[RoleTransformationMapping] = []
    loss_flags: list[str] = []
    addition_flags: list[str] = []
    keys = sorted(set(source_by_key) | set(compiled_by_key))
    for role, normalized_value in keys:
        source_rows = source_by_key[(role, normalized_value)]
        compiled_rows = compiled_by_key[(role, normalized_value)]
        for source, compiled in zip(source_rows, compiled_rows, strict=False):
            mappings.append(_mapping(source, compiled))
        if len(source_rows) > len(compiled_rows):
            loss_flags.append(
                f"unmapped_source_role:{role}:{normalized_value}:"
                f"{len(source_rows) - len(compiled_rows)}"
            )
        if len(compiled_rows) > len(source_rows):
            addition_flags.append(
                f"unmapped_compiled_role:{role}:{normalized_value}:"
                f"{len(compiled_rows) - len(source_rows)}"
            )
    return (
        tuple(sorted(mappings, key=lambda row: row.mapping_id)),
        tuple(sorted(loss_flags)),
        tuple(sorted(addition_flags)),
    )


def build_frame_transformation_binding_r10(
    *,
    canonical_source_family_id: str,
    source_record_id: str,
    source_frame: PredicateFrame,
    compiled_object_ids: Sequence[str],
    compiled_window_ids: Sequence[str],
    compiled_frame: PredicateFrame,
    transformation_type: str,
    require_lossless: bool = True,
) -> FrameTransformationBinding:
    validate_predicate_frame_r10_integrity(source_frame)
    validate_predicate_frame_r10_integrity(compiled_frame)
    family_id = _require_identifier(
        canonical_source_family_id,
        field="canonical_source_family_id",
    )
    record_id = _require_identifier(source_record_id, field="source_record_id")
    object_ids = tuple(
        sorted(
            {
                _require_identifier(str(value), field="compiled_object_id")
                for value in compiled_object_ids
            }
        )
    )
    window_ids = tuple(
        sorted(
            {
                _require_identifier(str(value), field="compiled_window_id")
                for value in compiled_window_ids
            }
        )
    )
    role_mappings, loss_flags, addition_flags = _role_mappings(
        source_frame,
        compiled_frame,
    )
    ambiguity_flags: list[str] = []
    if transformation_type not in TRANSFORMATION_TYPES:
        ambiguity_flags.append("unsupported_transformation_type")
    if not object_ids:
        ambiguity_flags.append("compiled_object_ids_empty")
    if not window_ids:
        ambiguity_flags.append("compiled_window_ids_empty")
    if source_frame.target_id != compiled_frame.target_id:
        ambiguity_flags.append("target_id_mismatch")
    semantic_equal = (
        source_frame.semantic_signature_digest
        == compiled_frame.semantic_signature_digest
    )
    if not semantic_equal:
        ambiguity_flags.append("semantic_signature_mismatch")
    if source_frame.accepted != compiled_frame.accepted:
        ambiguity_flags.append("completion_state_mismatch")
    accepted = not loss_flags and not addition_flags and not ambiguity_flags
    core = {
        "canonical_source_family_id": family_id,
        "source_record_id": record_id,
        "source_frame_id": source_frame.frame_id,
        "source_frame_digest": source_frame.representation_frame_digest,
        "source_frame_span": (source_frame.span_start, source_frame.span_end),
        "source_semantic_signature_digest": (
            source_frame.semantic_signature_digest
        ),
        "compiled_object_ids": object_ids,
        "compiled_window_ids": window_ids,
        "compiled_frame_id": compiled_frame.frame_id,
        "compiled_frame_digest": compiled_frame.representation_frame_digest,
        "compiled_frame_span": (
            compiled_frame.span_start,
            compiled_frame.span_end,
        ),
        "compiled_semantic_signature_digest": (
            compiled_frame.semantic_signature_digest
        ),
        "transformation_type": transformation_type,
        "role_mappings": [row.as_dict() for row in role_mappings],
        "representation_digest_equal": (
            source_frame.representation_frame_digest
            == compiled_frame.representation_frame_digest
        ),
        "semantic_signature_equal": semantic_equal,
        "loss_flags": loss_flags,
        "addition_flags": addition_flags,
        "ambiguity_flags": tuple(sorted(ambiguity_flags)),
        "binding_accepted": accepted,
    }
    binding_id = f"FRAMEBIND::R10::{canonical_digest(core)[:24].upper()}"
    body = {"binding_id": binding_id, **core}
    binding = FrameTransformationBinding(
        binding_id=binding_id,
        canonical_source_family_id=family_id,
        source_record_id=record_id,
        source_frame_id=source_frame.frame_id,
        source_frame_digest=source_frame.representation_frame_digest,
        source_frame_span=core["source_frame_span"],
        source_semantic_signature_digest=(
            source_frame.semantic_signature_digest
        ),
        compiled_object_ids=object_ids,
        compiled_window_ids=window_ids,
        compiled_frame_id=compiled_frame.frame_id,
        compiled_frame_digest=compiled_frame.representation_frame_digest,
        compiled_frame_span=core["compiled_frame_span"],
        compiled_semantic_signature_digest=(
            compiled_frame.semantic_signature_digest
        ),
        transformation_type=transformation_type,
        role_mappings=role_mappings,
        representation_digest_equal=core["representation_digest_equal"],
        semantic_signature_equal=semantic_equal,
        loss_flags=loss_flags,
        addition_flags=addition_flags,
        ambiguity_flags=core["ambiguity_flags"],
        binding_accepted=accepted,
        binding_digest=canonical_digest(body),
    )
    if require_lossless and not binding.binding_accepted:
        findings = (
            *binding.loss_flags,
            *binding.addition_flags,
            *binding.ambiguity_flags,
        )
        raise FrameTransformationBindingR10Error(
            "R10_transformation_not_lossless:" + "|".join(findings)
        )
    return binding


def build_missing_compiled_frame_binding_r10(
    *,
    canonical_source_family_id: str,
    source_record_id: str,
    source_frame: PredicateFrame,
) -> FrameTransformationBinding:
    """Emit an explicit, self-digested diagnostic for an unmaterialized frame."""

    validate_predicate_frame_r10_integrity(source_frame)
    family_id = _require_identifier(
        canonical_source_family_id,
        field="canonical_source_family_id",
    )
    record_id = _require_identifier(source_record_id, field="source_record_id")
    counts = Counter(_role_key(row) for row in _semantic_role_rows(source_frame))
    loss_flags = tuple(
        sorted(
            f"unmapped_source_role:{role}:{normalized_value}:{count}"
            for (role, normalized_value), count in counts.items()
        )
    )
    core = {
        "canonical_source_family_id": family_id,
        "source_record_id": record_id,
        "source_frame_id": source_frame.frame_id,
        "source_frame_digest": source_frame.representation_frame_digest,
        "source_frame_span": (source_frame.span_start, source_frame.span_end),
        "source_semantic_signature_digest": (
            source_frame.semantic_signature_digest
        ),
        "compiled_object_ids": (),
        "compiled_window_ids": (),
        "compiled_frame_id": "MISSING::R10::COMPILED_FRAME",
        "compiled_frame_digest": "0" * 64,
        "compiled_frame_span": (-1, -1),
        "compiled_semantic_signature_digest": "0" * 64,
        "transformation_type": "bounded_window",
        "role_mappings": [],
        "representation_digest_equal": False,
        "semantic_signature_equal": False,
        "loss_flags": loss_flags,
        "addition_flags": (),
        "ambiguity_flags": (
            "compiled_frame_missing",
            "compiled_object_ids_empty",
            "compiled_window_ids_empty",
            "semantic_signature_mismatch",
        ),
        "binding_accepted": False,
    }
    binding_id = f"FRAMEBIND::R10::{canonical_digest(core)[:24].upper()}"
    body = {"binding_id": binding_id, **core}
    return FrameTransformationBinding(
        binding_id=binding_id,
        canonical_source_family_id=family_id,
        source_record_id=record_id,
        source_frame_id=source_frame.frame_id,
        source_frame_digest=source_frame.representation_frame_digest,
        source_frame_span=core["source_frame_span"],
        source_semantic_signature_digest=(
            source_frame.semantic_signature_digest
        ),
        compiled_object_ids=(),
        compiled_window_ids=(),
        compiled_frame_id=core["compiled_frame_id"],
        compiled_frame_digest=core["compiled_frame_digest"],
        compiled_frame_span=core["compiled_frame_span"],
        compiled_semantic_signature_digest=core[
            "compiled_semantic_signature_digest"
        ],
        transformation_type=core["transformation_type"],
        role_mappings=(),
        representation_digest_equal=False,
        semantic_signature_equal=False,
        loss_flags=loss_flags,
        addition_flags=(),
        ambiguity_flags=core["ambiguity_flags"],
        binding_accepted=False,
        binding_digest=canonical_digest(body),
    )


def transformation_binding_digest_r10(
    bindings: Iterable[FrameTransformationBinding],
) -> str:
    rows = sorted(
        (row.as_dict() for row in bindings),
        key=lambda row: str(row["binding_id"]),
    )
    return canonical_digest(rows)


def validate_frame_transformation_binding_r10(
    value: Mapping[str, Any],
) -> None:
    body = dict(value)
    observed = str(body.pop("binding_digest", ""))
    if observed != canonical_digest(body):
        raise FrameTransformationBindingR10Error(
            "R10_transformation_binding_self_digest_invalid"
        )
    if value.get("binding_accepted") is not True:
        raise FrameTransformationBindingR10Error(
            "R10_transformation_binding_not_accepted"
        )
    if value.get("semantic_signature_equal") is not True:
        raise FrameTransformationBindingR10Error(
            "R10_transformation_binding_semantic_signature_mismatch"
        )
    if any(value.get(field) for field in (
        "loss_flags",
        "addition_flags",
        "ambiguity_flags",
    )):
        raise FrameTransformationBindingR10Error(
            "R10_transformation_binding_contains_material_flags"
        )
