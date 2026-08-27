from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from retrieval.dell_report_frame_transformation_r12 import (
    FrameTransformationBindingR12Error,
    build_frame_transformation_binding_r12,
    transformation_binding_digest_r12,
    validate_frame_transformation_binding_r12,
    validate_predicate_frame_r12_integrity,
)
from retrieval.dell_report_predicate_frames_r12 import (
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
def test_r12_source_compiled_binding_accepts_semantic_equivalence_with_different_representation(
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

    binding = build_frame_transformation_binding_r12(
        canonical_source_family_id="FAMILY::DELL::R12::001",
        source_record_id="SOURCE::DELL::R12::001",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R12::001"],
        compiled_window_ids=["WINDOW::DELL::R12::001"],
        compiled_frame=compiled,
        transformation_type="bounded_window",
    )
    assert binding.binding_accepted is True
    assert binding.representation_digest_equal is False
    assert binding.semantic_signature_equal is True
    assert binding.loss_flags == ()
    assert binding.addition_flags == ()
    assert binding.ambiguity_flags == ()
    assert binding.proof_rebind_flags == ()
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
    if target_id == ASP_TARGET:
        relation_mapping = relation_mappings[0]
        assert relation_mapping.source_proof_digest is not None
        assert relation_mapping.compiled_proof_digest is not None
        assert {
            row[0] for row in relation_mapping.source_proof_spans
        } == {
            "object",
            "product",
            "connector",
            "governing_nominal_head",
            "price",
        }
        assert {
            row[0] for row in relation_mapping.compiled_proof_spans
        } == {
            "object",
            "product",
            "connector",
            "governing_nominal_head",
            "price",
        }
    validate_frame_transformation_binding_r12(binding.as_dict())
    body = binding.as_dict()
    body.pop("binding_digest")
    assert binding.binding_digest == canonical_digest(body)
    for mapping in binding.role_mappings:
        mapping_body = mapping.as_dict()
        mapping_body.pop("mapping_digest")
        assert mapping.mapping_digest == canonical_digest(mapping_body)
    with pytest.raises(FrozenInstanceError):
        binding.binding_accepted = False  # type: ignore[misc]


def test_r12_transformation_diagnostics_and_gate_reject_semantic_role_loss() -> None:
    source = _frame(
        ASP_TARGET,
        "Dell offered PowerEdge hardware for USD 15 in FY2026.",
    )
    changed = _frame(
        ASP_TARGET,
        "Dell offered PowerEdge hardware for USD 16 in FY2026.",
    )
    diagnostic = build_frame_transformation_binding_r12(
        canonical_source_family_id="FAMILY::DELL::R12::002",
        source_record_id="SOURCE::DELL::R12::002",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R12::002"],
        compiled_window_ids=["WINDOW::DELL::R12::002"],
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
        FrameTransformationBindingR12Error,
        match="R12_transformation_not_lossless",
    ):
        build_frame_transformation_binding_r12(
            canonical_source_family_id="FAMILY::DELL::R12::002",
            source_record_id="SOURCE::DELL::R12::002",
            source_frame=source,
            compiled_object_ids=["OBJECT::DELL::R12::002"],
            compiled_window_ids=["WINDOW::DELL::R12::002"],
            compiled_frame=changed,
            transformation_type="normalized_slice",
        )


def test_r12_relation_loss_rejects_cross_group_product_price_compilation() -> None:
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

    diagnostic = build_frame_transformation_binding_r12(
        canonical_source_family_id="FAMILY::DELL::R12::RELATION",
        source_record_id="SOURCE::DELL::R12::RELATION",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R12::RELATION"],
        compiled_window_ids=["WINDOW::DELL::R12::RELATION"],
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
        FrameTransformationBindingR12Error,
        match="R12_transformation_not_lossless",
    ):
        build_frame_transformation_binding_r12(
            canonical_source_family_id="FAMILY::DELL::R12::RELATION",
            source_record_id="SOURCE::DELL::R12::RELATION",
            source_frame=source,
            compiled_object_ids=["OBJECT::DELL::R12::RELATION"],
            compiled_window_ids=["WINDOW::DELL::R12::RELATION"],
            compiled_frame=compiled,
            transformation_type="normalized_slice",
        )


def test_r12_price_attachment_proof_type_change_is_semantic_drift() -> None:
    source = _frame(
        ASP_TARGET,
        "Dell offered PowerEdge XE9680 hardware for USD 15.",
    )
    compiled = _frame(
        ASP_TARGET,
        "Dell offered USD 15 for PowerEdge XE9680 hardware.",
    )
    assert source.semantic_signature_digest != compiled.semantic_signature_digest
    diagnostic = build_frame_transformation_binding_r12(
        canonical_source_family_id="FAMILY::DELL::R12::PROOF-TYPE",
        source_record_id="SOURCE::DELL::R12::PROOF-TYPE",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R12::PROOF-TYPE"],
        compiled_window_ids=["WINDOW::DELL::R12::PROOF-TYPE"],
        compiled_frame=compiled,
        transformation_type="normalized_slice",
        require_lossless=False,
    )
    assert diagnostic.binding_accepted is False
    assert "semantic_signature_mismatch" in diagnostic.ambiguity_flags
    relation_losses = [
        row
        for row in diagnostic.loss_flags
        if row.startswith(
            "unmapped_source_role:argument_relation.hardware_product_price:"
        )
    ]
    relation_additions = [
        row
        for row in diagnostic.addition_flags
        if row.startswith(
            "unmapped_compiled_role:argument_relation.hardware_product_price:"
        )
    ]
    assert len(relation_losses) == 1
    assert len(relation_additions) == 1


def test_r12_connector_proof_rebind_for_to_at_is_typed_and_rejected() -> None:
    source = _frame(
        ASP_TARGET,
        "Dell offered PowerEdge XE9680 hardware for USD 15.",
    )
    compiled = _frame(
        ASP_TARGET,
        "Dell offered PowerEdge XE9680 hardware at USD 15.",
    )
    diagnostic = build_frame_transformation_binding_r12(
        canonical_source_family_id="FAMILY::DELL::R12::PROOF-REBIND",
        source_record_id="SOURCE::DELL::R12::PROOF-REBIND",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R12::PROOF-REBIND"],
        compiled_window_ids=["WINDOW::DELL::R12::PROOF-REBIND"],
        compiled_frame=compiled,
        transformation_type="normalized_slice",
        require_lossless=False,
    )
    assert diagnostic.binding_accepted is False
    assert diagnostic.semantic_signature_equal is False
    assert diagnostic.representation_digest_equal is False
    assert diagnostic.proof_rebind_flags
    assert diagnostic.proof_rebind_flags[0].startswith(
        "argument_relation_proof_rebind:hardware|xe9680|15|"
    )
    assert "semantic_signature_mismatch" in diagnostic.ambiguity_flags
    with pytest.raises(
        FrameTransformationBindingR12Error,
        match="R12_transformation_not_lossless",
    ):
        build_frame_transformation_binding_r12(
            canonical_source_family_id="FAMILY::DELL::R12::PROOF-REBIND",
            source_record_id="SOURCE::DELL::R12::PROOF-REBIND",
            source_frame=source,
            compiled_object_ids=["OBJECT::DELL::R12::PROOF-REBIND"],
            compiled_window_ids=["WINDOW::DELL::R12::PROOF-REBIND"],
            compiled_frame=compiled,
            transformation_type="normalized_slice",
        )


def test_r12_saved_binding_validator_rejects_resigned_proof_rebind() -> None:
    source = _frame(
        ASP_TARGET,
        "Dell offered PowerEdge XE9680 hardware for USD 15.",
    )
    compiled = _frame(
        ASP_TARGET,
        "Dell offered PowerEdge XE9680 hardware at USD 15.",
    )
    diagnostic = build_frame_transformation_binding_r12(
        canonical_source_family_id="FAMILY::DELL::R12::RESIGNED-REBIND",
        source_record_id="SOURCE::DELL::R12::RESIGNED-REBIND",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R12::RESIGNED-REBIND"],
        compiled_window_ids=["WINDOW::DELL::R12::RESIGNED-REBIND"],
        compiled_frame=compiled,
        transformation_type="normalized_slice",
        require_lossless=False,
    ).as_dict()
    assert diagnostic["proof_rebind_flags"]
    diagnostic["binding_accepted"] = True
    diagnostic["semantic_signature_equal"] = True
    diagnostic["loss_flags"] = []
    diagnostic["addition_flags"] = []
    diagnostic["ambiguity_flags"] = []
    core = dict(diagnostic)
    core.pop("binding_digest")
    core.pop("binding_id")
    diagnostic["binding_id"] = (
        "FRAMEBIND::R12::" f"{canonical_digest(core)[:24].upper()}"
    )
    body = dict(diagnostic)
    body.pop("binding_digest")
    diagnostic["binding_digest"] = canonical_digest(body)

    with pytest.raises(
        FrameTransformationBindingR12Error,
        match="R12_transformation_binding_contains_material_flags",
    ):
        validate_frame_transformation_binding_r12(diagnostic)


def test_r12_clause_ownership_proof_loss_rejects_transformation() -> None:
    source = _frame(
        SUPPLIER_TARGET,
        "NVIDIA provides GPUs and in Q2 ships them to Dell.",
    )
    compiled = _frame(
        SUPPLIER_TARGET,
        "NVIDIA provides GPUs to Dell.",
    )
    assert source.semantic_signature_digest != compiled.semantic_signature_digest
    diagnostic = build_frame_transformation_binding_r12(
        canonical_source_family_id="FAMILY::DELL::R12::OWNER-PROOF",
        source_record_id="SOURCE::DELL::R12::OWNER-PROOF",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R12::OWNER-PROOF"],
        compiled_window_ids=["WINDOW::DELL::R12::OWNER-PROOF"],
        compiled_frame=compiled,
        transformation_type="normalized_slice",
        require_lossless=False,
    )
    assert diagnostic.binding_accepted is False
    assert any(
        row.startswith("unmapped_source_role:clause_ownership.shared_subject_proved:")
        for row in diagnostic.loss_flags
    )
    assert "semantic_signature_mismatch" in diagnostic.ambiguity_flags


def test_r12_equal_proofs_map_provenance_even_when_absolute_spans_shift() -> None:
    source = _frame(
        SUPPLIER_TARGET,
        "Context. NVIDIA provides GPUs and in Q2 ships them to Dell.",
    )
    compiled = _frame(
        SUPPLIER_TARGET,
        "NVIDIA provides GPUs and in Q2 ships them to Dell.",
    )
    assert source.semantic_signature_digest == compiled.semantic_signature_digest
    binding = build_frame_transformation_binding_r12(
        canonical_source_family_id="FAMILY::DELL::R12::OWNER-MAP",
        source_record_id="SOURCE::DELL::R12::OWNER-MAP",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R12::OWNER-MAP"],
        compiled_window_ids=["WINDOW::DELL::R12::OWNER-MAP"],
        compiled_frame=compiled,
        transformation_type="bounded_window",
    )
    proof_mapping = next(
        row
        for row in binding.role_mappings
        if row.role == "clause_ownership.shared_subject_proved"
    )
    assert proof_mapping.source_proof_digest is not None
    assert proof_mapping.compiled_proof_digest is not None
    assert proof_mapping.source_proof_spans
    assert proof_mapping.compiled_proof_spans
    assert proof_mapping.source_proof_spans != proof_mapping.compiled_proof_spans


def test_r12_transformation_recomputes_frame_integrity_before_trusting_digest() -> None:
    frame = _frame(
        SUPPLIER_TARGET,
        "NVIDIA provides GPUs to Dell.",
    )
    validate_predicate_frame_r12_integrity(frame)
    tampered = replace(frame, semantic_signature_digest="0" * 64)
    with pytest.raises(
        FrameTransformationBindingR12Error,
        match="semantic_digest_invalid",
    ):
        validate_predicate_frame_r12_integrity(tampered)


def test_r12_transformation_recomputes_price_attachment_proof_digest() -> None:
    frame = _frame(
        ASP_TARGET,
        "Dell offered PowerEdge XE9680 hardware for USD 15.",
    )
    tampered_group = replace(frame.argument_groups[0], proof_digest="0" * 64)
    tampered = replace(frame, argument_groups=(tampered_group,))
    with pytest.raises(
        FrameTransformationBindingR12Error,
        match="price_attachment_proof_digest_invalid",
    ):
        validate_predicate_frame_r12_integrity(tampered)


def test_r12_transformation_recomputes_clause_ownership_proof_digest() -> None:
    frame = _frame(
        SUPPLIER_TARGET,
        "NVIDIA provides GPUs and in Q2 ships them to Dell.",
    )
    tampered_proof = replace(
        frame.clause_ownership_proofs[0],
        decision_digest="0" * 64,
    )
    tampered = replace(frame, clause_ownership_proofs=(tampered_proof,))
    with pytest.raises(
        FrameTransformationBindingR12Error,
        match="clause_ownership_proof_digest_invalid",
    ):
        validate_predicate_frame_r12_integrity(tampered)


def test_r12_transformation_binding_set_digest_is_order_independent() -> None:
    source = _frame(
        SUPPLIER_TARGET,
        "Context. NVIDIA provides GPUs to Dell.",
    )
    compiled = _frame(SUPPLIER_TARGET, "NVIDIA provides GPUs to Dell.")
    first = build_frame_transformation_binding_r12(
        canonical_source_family_id="FAMILY::DELL::R12::003",
        source_record_id="SOURCE::DELL::R12::003",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R12::003"],
        compiled_window_ids=["WINDOW::DELL::R12::003"],
        compiled_frame=compiled,
        transformation_type="bounded_window",
    )
    second = build_frame_transformation_binding_r12(
        canonical_source_family_id="FAMILY::DELL::R12::004",
        source_record_id="SOURCE::DELL::R12::004",
        source_frame=source,
        compiled_object_ids=["OBJECT::DELL::R12::004"],
        compiled_window_ids=["WINDOW::DELL::R12::004"],
        compiled_frame=compiled,
        transformation_type="many_object_same_source",
    )
    assert transformation_binding_digest_r12([first, second]) == (
        transformation_binding_digest_r12([second, first])
    )
