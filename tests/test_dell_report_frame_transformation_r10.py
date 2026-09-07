from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from retrieval.dell_report_frame_transformation_r10 import (
    FrameTransformationBindingR10Error,
    build_frame_transformation_binding_r10,
    transformation_binding_digest_r10,
    validate_frame_transformation_binding_r10,
    validate_predicate_frame_r10_integrity,
)
from retrieval.dell_report_predicate_frames_r10 import (
    ASP_TARGET,
    SUPPLIER_TARGET,
    extract_predicate_frames,
)
from retrieval.query_plan import canonical_digest


def _metadata() -> dict:
    return {
        "ticker": "DELL",
        "source_type": "PUBLIC_WEB",
        "source_tier": "named_counterparty_or_standards_primary",
        "publication_date": "2025-05-27",
    }


def _frame(target_id: str, text: str):
    frames = extract_predicate_frames(
        target_id=target_id,
        text=text,
        metadata=_metadata(),
    )
    accepted = [row for row in frames if row.accepted]
    assert len(accepted) == 1
    return accepted[0]


@pytest.mark.parametrize(
    ("target_id", "source_text", "compiled_text"),
    [
        (
            ASP_TARGET,
            "Quarter update. Dell offered PowerEdge hardware for USD 15 in FY2026.",
            "Dell offered PowerEdge hardware for USD 15 in FY2026.",
        ),
        (
            SUPPLIER_TARGET,
            "Background note. NVIDIA provides GPUs to Dell.",
            "NVIDIA provides GPUs to Dell.",
        ),
    ],
)
def test_r10_source_compiled_binding_accepts_semantic_equivalence_with_different_representation(
    target_id: str,
    source_text: str,
    compiled_text: str,
) -> None:
    source = _frame(target_id, source_text)
    compiled = _frame(target_id, compiled_text)
    assert source.representation_frame_digest != (
        compiled.representation_frame_digest
    )
    assert source.semantic_signature_digest == compiled.semantic_signature_digest

    binding = build_frame_transformation_binding_r10(
        canonical_source_family_id="FAMILY::DELL::R10::001",
        source_record_id="SOURCE::DELL::R10::001",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R10::001"],
        compiled_window_ids=["WINDOW::DELL::R10::001"],
        compiled_frame=compiled,
        transformation_type="bounded_window",
    )
    assert binding.binding_accepted is True
    assert binding.representation_digest_equal is False
    assert binding.semantic_signature_equal is True
    assert binding.loss_flags == ()
    assert binding.addition_flags == ()
    assert binding.ambiguity_flags == ()
    assert len(binding.role_mappings) == (
        len(source.role_bindings)
        + len(source.scope_bindings)
        + (1 if target_id == ASP_TARGET else 0)
    )
    relation_mappings = [
        row
        for row in binding.role_mappings
        if row.role == "argument_relation.hardware_product_price"
    ]
    assert len(relation_mappings) == (1 if target_id == ASP_TARGET else 0)
    validate_frame_transformation_binding_r10(binding.as_dict())
    body = binding.as_dict()
    body.pop("binding_digest")
    assert binding.binding_digest == canonical_digest(body)
    for mapping in binding.role_mappings:
        mapping_body = mapping.as_dict()
        mapping_body.pop("mapping_digest")
        assert mapping.mapping_digest == canonical_digest(mapping_body)
    with pytest.raises(FrozenInstanceError):
        binding.binding_accepted = False  # type: ignore[misc]


def test_r10_transformation_diagnostics_and_gate_reject_semantic_role_loss() -> None:
    source = _frame(
        ASP_TARGET,
        "Dell offered PowerEdge hardware for USD 15 in FY2026.",
    )
    changed = _frame(
        ASP_TARGET,
        "Dell offered PowerEdge hardware for USD 16 in FY2026.",
    )
    diagnostic = build_frame_transformation_binding_r10(
        canonical_source_family_id="FAMILY::DELL::R10::002",
        source_record_id="SOURCE::DELL::R10::002",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R10::002"],
        compiled_window_ids=["WINDOW::DELL::R10::002"],
        compiled_frame=changed,
        transformation_type="normalized_slice",
        require_lossless=False,
    )
    assert diagnostic.binding_accepted is False
    assert diagnostic.semantic_signature_equal is False
    assert "unmapped_source_role:price:15:1" in diagnostic.loss_flags
    assert "unmapped_compiled_role:price:16:1" in diagnostic.addition_flags
    assert any(
        row.startswith(
            "unmapped_source_role:argument_relation.hardware_product_price:"
        )
        for row in diagnostic.loss_flags
    )
    assert any(
        row.startswith(
            "unmapped_compiled_role:argument_relation.hardware_product_price:"
        )
        for row in diagnostic.addition_flags
    )
    assert "semantic_signature_mismatch" in diagnostic.ambiguity_flags
    with pytest.raises(
        FrameTransformationBindingR10Error,
        match="R10_transformation_not_lossless",
    ):
        build_frame_transformation_binding_r10(
            canonical_source_family_id="FAMILY::DELL::R10::002",
            source_record_id="SOURCE::DELL::R10::002",
            source_frame=source,
            compiled_object_ids=["OBJECT::DELL::R10::002"],
            compiled_window_ids=["WINDOW::DELL::R10::002"],
            compiled_frame=changed,
            transformation_type="normalized_slice",
        )


def test_r10_relation_loss_rejects_cross_group_product_price_compilation() -> None:
    source = _frame(
        ASP_TARGET,
        "Dell offered PowerEdge XE9680 hardware for USD 15.",
    )
    compiled_frames = extract_predicate_frames(
        target_id=ASP_TARGET,
        text=(
            "Dell offered PowerEdge XE9680 and support for USD 100 plus "
            "hardware for USD 15."
        ),
        metadata=_metadata(),
    )
    assert len(compiled_frames) == 1
    compiled = compiled_frames[0]
    assert source.accepted is True
    assert compiled.accepted is False
    assert source.semantic_signature_digest != compiled.semantic_signature_digest

    diagnostic = build_frame_transformation_binding_r10(
        canonical_source_family_id="FAMILY::DELL::R10::RELATION",
        source_record_id="SOURCE::DELL::R10::RELATION",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R10::RELATION"],
        compiled_window_ids=["WINDOW::DELL::R10::RELATION"],
        compiled_frame=compiled,
        transformation_type="normalized_slice",
        require_lossless=False,
    )
    assert diagnostic.binding_accepted is False
    assert diagnostic.semantic_signature_equal is False
    assert any(
        flag.startswith(
            "unmapped_source_role:argument_relation.hardware_product_price:"
        )
        for flag in diagnostic.loss_flags
    )
    assert "semantic_signature_mismatch" in diagnostic.ambiguity_flags
    assert "completion_state_mismatch" in diagnostic.ambiguity_flags
    with pytest.raises(
        FrameTransformationBindingR10Error,
        match="R10_transformation_not_lossless",
    ):
        build_frame_transformation_binding_r10(
            canonical_source_family_id="FAMILY::DELL::R10::RELATION",
            source_record_id="SOURCE::DELL::R10::RELATION",
            source_frame=source,
            compiled_object_ids=["OBJECT::DELL::R10::RELATION"],
            compiled_window_ids=["WINDOW::DELL::R10::RELATION"],
            compiled_frame=compiled,
            transformation_type="normalized_slice",
        )


def test_r10_transformation_recomputes_frame_integrity_before_trusting_digest() -> None:
    frame = _frame(
        SUPPLIER_TARGET,
        "NVIDIA provides GPUs to Dell.",
    )
    validate_predicate_frame_r10_integrity(frame)
    tampered = replace(frame, semantic_signature_digest="0" * 64)
    with pytest.raises(
        FrameTransformationBindingR10Error,
        match="semantic_digest_invalid",
    ):
        validate_predicate_frame_r10_integrity(tampered)


def test_r10_transformation_binding_set_digest_is_order_independent() -> None:
    source = _frame(
        SUPPLIER_TARGET,
        "Context. NVIDIA provides GPUs to Dell.",
    )
    compiled = _frame(SUPPLIER_TARGET, "NVIDIA provides GPUs to Dell.")
    first = build_frame_transformation_binding_r10(
        canonical_source_family_id="FAMILY::DELL::R10::003",
        source_record_id="SOURCE::DELL::R10::003",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R10::003"],
        compiled_window_ids=["WINDOW::DELL::R10::003"],
        compiled_frame=compiled,
        transformation_type="bounded_window",
    )
    second = build_frame_transformation_binding_r10(
        canonical_source_family_id="FAMILY::DELL::R10::004",
        source_record_id="SOURCE::DELL::R10::004",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R10::004"],
        compiled_window_ids=["WINDOW::DELL::R10::004"],
        compiled_frame=compiled,
        transformation_type="many_object_same_source",
    )
    assert transformation_binding_digest_r10([first, second]) == (
        transformation_binding_digest_r10([second, first])
    )
