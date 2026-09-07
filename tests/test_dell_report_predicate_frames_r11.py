from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from retrieval.dell_report_predicate_frames_r11 import (
    ASP_TARGET,
    CAPACITY_TARGET,
    HBM_TARGET,
    SUPPLIER_TARGET,
    UNITS_TARGET,
    YIELD_TARGET,
    classify_package,
    extract_predicate_frames,
    frame_boundary_decisions,
    frame_records,
    normalize_text,
)
from retrieval.query_plan import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
R7_TEST_REF = ROOT / "tests/test_dell_report_internal_chain_ceiling_r7.py"


def _metadata() -> dict:
    return {
        "ticker": "DELL",
        "source_type": "PUBLIC_WEB",
        "source_tier": "named_counterparty_or_standards_primary",
        "publication_date": "2025-05-27",
    }


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            UNITS_TARGET,
            "Dell shipped marketing materials and NVIDIA delivered four "
            "PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            CAPACITY_TARGET,
            "Dell received financing and GPU capacity was allocated in Q1 2026.",
        ),
        (
            HBM_TARGET,
            "HBM supply was available to HP and Dell announced earnings in Q1 2026.",
        ),
    ],
)
def test_r11_no_comma_independent_events_split_and_cannot_union_roles(
    target_id: str,
    text: str,
) -> None:
    normalized = normalize_text(text)
    decisions = frame_boundary_decisions(text)
    split = [row for row in decisions if row.decision == "split"]
    assert len(split) == 1
    decision = split[0]
    assert normalized[decision.span_start : decision.span_end].strip() == "and"
    assert decision.left_predicate_span is not None
    assert decision.right_subject_span is not None
    assert decision.right_predicate_span is not None
    assert decision.decision_digest == canonical_digest(
        {
            key: value
            for key, value in decision.as_dict().items()
            if key != "decision_digest"
        }
    )
    assert len(frame_records(text)) == 2
    assessment = classify_package(
        target_id=target_id,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] != "complete_bounded_target_package"
    assert assessment["accepted_frame_id"] is None


def test_r11_compound_company_subject_keeps_one_shared_predicate_frame() -> None:
    text = "Dell, NVIDIA, and Micron partnered for AI delivery."
    decisions = frame_boundary_decisions(text)
    assert [row.decision for row in decisions] == ["compound_subject"]
    assert len(frame_records(text)) == 1
    assessment = classify_package(
        target_id=SUPPLIER_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] == "complete_bounded_target_package"


@pytest.mark.parametrize(
    "right_owner",
    [
        "Acme",
        "Supermicro",
        "Northstar Systems",
        "in Q2 Acme",
    ],
)
def test_r11_open_vocabulary_right_owner_splits_without_entity_allowlist(
    right_owner: str,
) -> None:
    text = (
        "Dell quoted support for USD 150 and "
        f"{right_owner} offered PowerEdge XE9680 hardware for USD 15."
    )
    normalized = normalize_text(text)
    decisions = frame_boundary_decisions(text)
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.decision == "split"
    assert decision.ownership_state == "independent_owner_proved"
    assert decision.reason == (
        "coordinator_with_proved_right_owner_and_finite_predicate"
    )
    assert decision.explicit_owner_proof == (
        "case_or_material_np_before_finite_predicate"
    )
    assert decision.right_subject_span is not None
    expected_owner = "Acme" if right_owner == "in Q2 Acme" else right_owner
    assert normalized[
        decision.right_subject_span[0] : decision.right_subject_span[1]
    ] == normalize_text(expected_owner)
    assert len(frame_records(text)) == 2
    assessment = classify_package(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] != "complete_bounded_target_package"
    assert assessment["accepted_frame_id"] is None


@pytest.mark.parametrize(
    "adjunct",
    [
        "in Q2",
        "later in Q2",
        "under the agreement",
    ],
)
def test_r11_fronted_functional_adjunct_proves_shared_subject(
    adjunct: str,
) -> None:
    text = f"NVIDIA provides GPUs and {adjunct} ships them to Dell."
    normalized = normalize_text(text)
    decisions = frame_boundary_decisions(text)
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.decision == "no_split"
    assert decision.ownership_state == "shared_subject_proved"
    assert decision.shared_subject_proof == (
        "no_owner_np_before_finite_predicate"
    )
    assert decision.leading_adjunct_span is not None
    assert normalized[
        decision.leading_adjunct_span[0] : decision.leading_adjunct_span[1]
    ] == normalize_text(adjunct)
    assert decision.right_subject_span is None
    assert len(frame_records(text)) == 1
    assessment = classify_package(
        target_id=SUPPLIER_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] == "complete_bounded_target_package"
    accepted = next(
        row
        for row in assessment["predicate_frames"]
        if row["frame_id"] == assessment["accepted_frame_id"]
    )
    assert [
        row["ownership_state"]
        for row in accepted["clause_ownership_proofs"]
    ] == ["shared_subject_proved"]


@pytest.mark.parametrize(
    "collision_owner",
    [
        "Rose Systems",
        "Target Labs",
        "Will Technologies",
    ],
)
def test_r11_case_preserved_predicate_token_collision_is_owner_not_verb(
    collision_owner: str,
) -> None:
    text = (
        "Dell quoted support for USD 150 and "
        f"{collision_owner} offered PowerEdge XE9680 hardware for USD 15."
    )
    decision = frame_boundary_decisions(text)[0]
    assert decision.decision == "split"
    assert decision.ownership_state == "independent_owner_proved"
    assert len(decision.right_predicate_candidate_spans) >= 2
    assert len(frame_records(text)) == 2
    assessment = classify_package(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] != "complete_bounded_target_package"
    assert assessment["accepted_frame_id"] is None


@pytest.mark.parametrize("unknown_head", ["cost", "wugged", "zorps"])
def test_r11_unseen_material_clause_head_creates_ambiguity_barrier(
    unknown_head: str,
) -> None:
    text = (
        "Dell quoted support for USD 150 and Northstar Systems "
        f"{unknown_head} PowerEdge XE9680 hardware for USD 15."
    )
    decision = frame_boundary_decisions(text)[0]
    assert decision.decision == "split"
    assert decision.ownership_state == "ambiguous_material_boundary"
    assert decision.ambiguity_reason == (
        "finite_predicate_unproved_role_barrier_required"
    )
    assert len(frame_records(text)) == 2
    assessment = classify_package(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] != "complete_bounded_target_package"
    assert assessment["accepted_frame_id"] is None


def test_r11_casefold_length_alignment_failure_is_a_typed_role_barrier() -> None:
    text = (
        "Dell quoted support for USD 150 and Straße Systems offered "
        "PowerEdge XE9680 hardware for USD 15."
    )
    decision = frame_boundary_decisions(text)[0]
    assert decision.decision == "split"
    assert decision.ownership_state == "ambiguous_material_boundary"
    assert decision.surface_alignment_pass is False
    assert decision.ambiguity_reason == "surface_alignment_failed"
    assessment = classify_package(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] != "complete_bounded_target_package"
    assert assessment["accepted_frame_id"] is None


@pytest.mark.parametrize(
    "text",
    [
        "NVIDIA provides GPUs and HBM to Dell.",
        "NVIDIA provides GPUs and has also shipped them to Dell.",
    ],
)
def test_r11_shared_object_or_auxiliary_continuation_does_not_false_split(
    text: str,
) -> None:
    decisions = frame_boundary_decisions(text)
    assert all(row.decision != "split" for row in decisions)
    assert len(frame_records(text)) == 1
    assessment = classify_package(
        target_id=SUPPLIER_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] == "complete_bounded_target_package"


def test_r11_predicate_at_right_offset_zero_is_shared_subject_continuation() -> None:
    text = (
        "Dell quoted support for USD 150 and offered PowerEdge XE9680 "
        "hardware for USD 15."
    )
    decisions = frame_boundary_decisions(text)
    assert [row.decision for row in decisions] == ["no_split"]
    assert decisions[0].right_subject_span is None
    assert len(frame_records(text)) == 1
    assessment = classify_package(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] == "complete_bounded_target_package"


@pytest.mark.parametrize(
    (
        "text",
        "expected_actuality",
        "expected_lifecycle",
        "expected_speech",
        "expected_owner",
        "expected_relation",
        "modifier_surface",
    ),
    [
        (
            "Dell and NVIDIA partnered for delivery; this partnership was later suspended.",
            "actual",
            "suspended",
            "direct",
            "Dell",
            "changes_lifecycle_status",
            "suspended",
        ),
        (
            "Dell discontinued its partnership with NVIDIA for delivery.",
            "actual",
            "discontinued",
            "direct",
            "Dell",
            "changes_lifecycle_status",
            "discontinued",
        ),
        (
            "Dell is exploring a partnership with NVIDIA for delivery.",
            "exploratory",
            "active",
            "direct",
            "Dell",
            "governs_actuality",
            "exploring",
        ),
        (
            "According to an analyst, Dell partnered with NVIDIA for delivery.",
            "actual",
            "active",
            "third_party_attributed",
            "an analyst",
            "owns_assertion",
            "according to an analyst,",
        ),
    ],
)
def test_r11_semantic_state_is_typed_and_bound_by_exact_scope_edge(
    text: str,
    expected_actuality: str,
    expected_lifecycle: str,
    expected_speech: str,
    expected_owner: str,
    expected_relation: str,
    modifier_surface: str,
) -> None:
    normalized = normalize_text(text)
    frames = extract_predicate_frames(
        target_id=SUPPLIER_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert len(frames) == 1
    frame = frames[0]
    assert frame.accepted is False
    assert frame.actuality == expected_actuality
    assert frame.lifecycle_status == expected_lifecycle
    assert frame.speech_mode == expected_speech
    assert frame.assertion_owner is not None
    assert frame.assertion_owner.normalized_value == expected_owner
    edge = next(row for row in frame.scope_edges if row.relation == expected_relation)
    assert edge.target_assertion_frame_id == frame.assertion_frame_id
    assert edge.source_modifier_frame_id.startswith("MODIFIER::R11::")
    assert normalized[edge.evidence_span_start : edge.evidence_span_end] == (
        modifier_surface
    )
    assert edge.edge_digest == canonical_digest(
        {
            key: value
            for key, value in edge.as_dict().items()
            if key != "edge_digest"
        }
    )


def test_r11_unrelated_state_change_does_not_veto_independent_positive_frame() -> None:
    text = (
        "Dell and NVIDIA partnered for delivery while HP discontinued "
        "another relationship."
    )
    assert len(frame_records(text)) == 2
    assessment = classify_package(
        target_id=SUPPLIER_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] == "complete_bounded_target_package"
    accepted = next(
        row
        for row in assessment["predicate_frames"]
        if row["frame_id"] == assessment["accepted_frame_id"]
    )
    assert accepted["lifecycle_status"] == "active"
    assert accepted["scope_edges"] == []


@pytest.mark.parametrize(
    ("text", "expected_classes", "expected_price", "expected_complete"),
    [
        (
            "Dell quoted support for USD 150 and PowerEdge XE9680 hardware "
            "for USD 15.",
            ["support", "hardware"],
            "15",
            True,
        ),
        (
            "Dell quoted a support package for USD 150 for PowerEdge XE9680 "
            "hardware.",
            ["support"],
            None,
            False,
        ),
        (
            "Dell quoted $150 for support plus $15 for PowerEdge XE9680 hardware.",
            ["support", "hardware"],
            "15",
            True,
        ),
    ],
)
def test_r11_price_is_bound_to_typed_argument_group_not_record_global_value(
    text: str,
    expected_classes: list[str],
    expected_price: str | None,
    expected_complete: bool,
) -> None:
    normalized = normalize_text(text)
    frames = extract_predicate_frames(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert len(frames) == 1
    frame = frames[0]
    assert [row.object_class for row in frame.argument_groups] == expected_classes
    for group in frame.argument_groups:
        assert normalized[group.span_start : group.span_end] == group.raw_text
        assert group.governing_predicate_span == (
            frame.predicate_span_start,
            frame.predicate_span_end,
        )
        assert normalized[group.price_span[0] : group.price_span[1]].strip()
        assert group.group_digest == canonical_digest(
            {
                key: value
                for key, value in group.as_dict().items()
                if key not in {"group_id", "group_digest"}
            }
        )
    prices = frame.bindings("price")
    assert [row.normalized_value for row in prices] == (
        [expected_price] if expected_price is not None else []
    )
    assert "150" not in [row.normalized_value for row in prices]
    assert frame.accepted is expected_complete


@pytest.mark.parametrize(
    "text",
    [
        "Dell quoted support for USD 150.",
        "Dell quoted freight for USD 150.",
        "Dell quoted financing for USD 150.",
    ],
)
def test_r11_non_hardware_price_near_neighbors_fail_closed(text: str) -> None:
    frame = extract_predicate_frames(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )[0]
    assert frame.accepted is False
    assert frame.bindings("price") == ()
    assert frame.argument_groups[0].object_class in {
        "support",
        "freight",
        "financing",
    }


@pytest.mark.parametrize(
    "text",
    [
        (
            "Dell offered PowerEdge XE9680 hardware under a global contract "
            "amount of USD 15."
        ),
        (
            "Dell offered PowerEdge XE9680 hardware with maintenance costing "
            "USD 15."
        ),
        (
            "Dell offered PowerEdge XE9680 hardware with a delivery fee of "
            "USD 15."
        ),
        (
            "Dell offered PowerEdge XE9680 hardware under a lease payment of "
            "USD 15."
        ),
        (
            "Dell offered PowerEdge XE9680 hardware with a quasar levy of "
            "USD 15."
        ),
        (
            "Dell offered PowerEdge XE9680 hardware under a nebula escrow of "
            "USD 15."
        ),
    ],
)
def test_r11_price_copresence_without_direct_attachment_never_admits_relation(
    text: str,
) -> None:
    frame = extract_predicate_frames(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )[0]
    assert frame.accepted is False
    assert frame.bindings("product") == ()
    assert frame.bindings("price") == ()
    group = frame.argument_groups[0]
    assert group.proof_state == "unproved"
    assert group.proof_type == "no_direct_price_attachment_path"
    assert group.connector_span is None
    assert group.competing_object_span is not None
    assert group.ambiguity == "price_object_attachment_unproved"


@pytest.mark.parametrize(
    ("text", "proof_type"),
    [
        (
            "Dell offered PowerEdge XE9680 hardware for USD 15.",
            "object_to_price_explicit_connector",
        ),
        (
            "Dell quoted USD 15 for PowerEdge XE9680 hardware.",
            "price_to_object_explicit_connector",
        ),
        (
            "Dell offered PowerEdge XE9680 hardware priced at USD 15.",
            "object_to_price_explicit_connector",
        ),
        (
            "Dell stated USD 15 as the purchase price for PowerEdge XE9680 "
            "hardware.",
            "price_to_object_explicit_connector",
        ),
    ],
)
def test_r11_affirmative_price_attachment_has_traversable_span_proof(
    text: str,
    proof_type: str,
) -> None:
    frame = extract_predicate_frames(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )[0]
    assert frame.accepted is True
    group = frame.argument_groups[0]
    assert group.proof_state == "affirmative"
    assert group.proof_type == proof_type
    assert group.connector_span is not None
    assert group.object_span is not None
    assert group.product_span is not None
    assert group.object_span[0] <= group.product_span[0]
    assert group.product_span[1] <= group.object_span[1]
    assert group.proof_digest == canonical_digest(
        {
            "proof_state": group.proof_state,
            "proof_type": group.proof_type,
            "object_class": group.object_class,
            "object_span": group.object_span,
            "product_span": group.product_span,
            "price_span": group.price_span,
            "connector_span": group.connector_span,
            "competing_object_span": group.competing_object_span,
        }
    )


def test_r11_cross_group_product_and_hardware_price_cannot_complete_asp() -> None:
    text = (
        "Dell offered PowerEdge XE9680 and support for USD 100 plus "
        "hardware for USD 15."
    )
    frame = extract_predicate_frames(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )[0]
    assert frame.accepted is False
    assert frame.bindings("product") == ()
    assert frame.bindings("price") == ()
    assert all(row.product_span is None for row in frame.argument_groups)
    assert "bounded_hardware_or_server_object" in frame.missing_required_roles
    assert "currency_price" in frame.missing_required_roles


def test_r11_generic_hardware_price_has_no_specific_product_relation() -> None:
    frame = extract_predicate_frames(
        target_id=ASP_TARGET,
        text="Dell offered hardware for USD 15.",
        metadata=_metadata(),
    )[0]
    assert frame.accepted is False
    assert frame.argument_groups[0].normalized_product == (
        "bounded_hardware_configuration"
    )
    assert frame.bindings("product") == ()
    assert frame.bindings("price") == ()


def test_r11_multiple_product_price_relations_fail_closed() -> None:
    text = (
        "Dell offered PowerEdge XE9680 hardware for USD 15 plus "
        "PowerEdge XE9712 hardware for USD 16."
    )
    frame = extract_predicate_frames(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )[0]
    assert frame.accepted is False
    assert frame.bindings("product") == ()
    assert frame.bindings("price") == ()
    assert (
        "ambiguous_multiple_hardware_product_price_argument_relations"
        in frame.ambiguities
    )


def test_r11_multiple_products_inside_one_price_group_fail_closed() -> None:
    frame = extract_predicate_frames(
        target_id=ASP_TARGET,
        text=(
            "Dell offered PowerEdge XE9680/XE9712 hardware for USD 15."
        ),
        metadata=_metadata(),
    )[0]
    assert frame.accepted is False
    assert frame.bindings("product") == ()
    assert frame.bindings("price") == ()
    assert frame.argument_groups[0].product_span is None
    assert frame.argument_groups[0].ambiguity == (
        "ambiguous_multiple_products_in_argument_group"
    )
    assert "ambiguous_price_to_hardware_argument" in frame.ambiguities


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            ASP_TARGET,
            "NVIDIA quoted $15, and Dell sold the PowerEdge XE9680 hardware.",
        ),
        (ASP_TARGET, "Dell quoted $15 for PowerEdge hardware, allegedly."),
        (SUPPLIER_TARGET, "NVIDIA shipped chips, and Dell sold PowerEdge servers."),
        (
            SUPPLIER_TARGET,
            "NVIDIA supplies Dell AI servers, according to an unconfirmed report.",
        ),
        (
            CAPACITY_TARGET,
            "Dell received financing alongside GPU capacity being allocated to HP "
            "in Q1 2026.",
        ),
        (
            YIELD_TARGET,
            "Solar-panel production yield was 90%, and GPU sales rose in 2026.",
        ),
        (HBM_TARGET, "HBM supply was available to HP, and Dell announced earnings."),
        (
            UNITS_TARGET,
            "Dell shipped marketing materials, and NVIDIA delivered four PowerEdge "
            "XE9680 AI servers in Q1 2026.",
        ),
    ],
)
def test_r11_inherits_r8_fresh_negative_surface(target_id: str, text: str) -> None:
    assessment = classify_package(
        target_id=target_id,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] != "complete_bounded_target_package"
    assert assessment["accepted_frame_id"] is None


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (SUPPLIER_TARGET, "NVIDIA provides GPUs to Dell."),
        (CAPACITY_TARGET, "NVIDIA released GPU capacity to Dell in Q1 2026."),
        (YIELD_TARGET, "HBM production yielded 90% in 2026."),
        (HBM_TARGET, "Dell PowerEdge servers use HBM in Q1 2026."),
        (
            UNITS_TARGET,
            "Dell dispatched four PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (ASP_TARGET, "Dell offered PowerEdge hardware for USD 15 in FY2026."),
        (SUPPLIER_TARGET, "NVIDIA is Dell's supplier for AI server delivery."),
        (
            SUPPLIER_TARGET,
            "We expanded the Dell AI factory ecosystem with partners, including NVIDIA.",
        ),
        (
            CAPACITY_TARGET,
            "GPU production capacity was earmarked for Dell in Q1 2026.",
        ),
        (
            CAPACITY_TARGET,
            "GPU production capacity was allocated to Dell in Q1 2026, but another "
            "component was unavailable.",
        ),
        (YIELD_TARGET, "HBM production achieved a 90% yield in 2026."),
        (
            YIELD_TARGET,
            "HBM production yield was 80% in 2026, and next process target is 95%.",
        ),
        (HBM_TARGET, "Dell PowerEdge systems incorporated HBM in Q1 2026."),
        (
            UNITS_TARGET,
            "Dell sent four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            UNITS_TARGET,
            "Dell said it shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (ASP_TARGET, "Dell sold two Dell PowerEdge XE9680 servers for $15."),
        (
            ASP_TARGET,
            "Dell quoted $15 for two Dell PowerEdge XE9680 servers and will offer "
            "support later.",
        ),
    ],
)
def test_r11_inherits_frozen_positive_surface(target_id: str, text: str) -> None:
    assessment = classify_package(
        target_id=target_id,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] == "complete_bounded_target_package"
    assert assessment["accepted_frame_id"].startswith("FRAME::R11::")


def _immutable_r7_negative_semantic_cases() -> list[tuple[str, str]]:
    function_names = {
        "test_R7_freezes_every_R4_semantic_attack",
        "test_R7_freezes_fresh_R5_clause_and_polarity_attacks",
        "test_R7_rejects_speculative_or_absent_typed_propositions",
        "test_R7_freezes_fresh_R6_single_proposition_attacks",
    }
    tree = ast.parse(R7_TEST_REF.read_text(encoding="utf-8"))
    cases: list[tuple[str, str]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in function_names:
            continue
        parametrizations = [
            decorator
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "parametrize"
        ]
        assert len(parametrizations) == 1
        literal = ast.literal_eval(parametrizations[0].args[1])
        cases.extend((str(target_id), str(text)) for target_id, text in literal)
    return cases


def test_r11_inherits_all_63_r7_negative_semantic_attacks() -> None:
    cases = _immutable_r7_negative_semantic_cases()
    assert len(cases) == 63
    assert canonical_digest(cases) == (
        "6e618bcf3567a7e49c4a832379c5aadf0eadae939f5c69dd09f00cfe00754227"
    )
    false_completes = []
    for target_id, text in cases:
        assessment = classify_package(
            target_id=target_id,
            text=text,
            metadata=_metadata(),
        )
        if assessment["classification"] == "complete_bounded_target_package":
            false_completes.append((target_id, text))
    assert false_completes == []


def test_r11_frame_records_and_bindings_are_deterministic_and_immutable() -> None:
    kwargs = {
        "target_id": UNITS_TARGET,
        "text": "Dell dispatched four PowerEdge XE9680 AI servers in Q1 2026.",
        "metadata": _metadata(),
    }
    first = extract_predicate_frames(**kwargs)
    second = extract_predicate_frames(**kwargs)
    assert [row.as_dict() for row in first] == [row.as_dict() for row in second]
    assert first[0].frame_digest == second[0].frame_digest
    with pytest.raises(FrozenInstanceError):
        first[0].frame_id = "mutated"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        first[0].role_bindings[0].normalized_value = "mutated"  # type: ignore[misc]
