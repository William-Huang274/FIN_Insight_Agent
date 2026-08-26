from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from retrieval.dell_report_predicate_frames_r8 import (
    ASP_TARGET,
    CAPACITY_TARGET,
    HBM_TARGET,
    SUPPLIER_TARGET,
    UNITS_TARGET,
    YIELD_TARGET,
    classify_package,
    extract_predicate_frames,
    frame_records,
    normalize_text,
)
from retrieval.dell_report_public_validation_r8 import (
    DellReportPublicValidationR8Error,
    validate_public_scalar_tree_r8,
    validate_public_string_r8,
)
from retrieval.dell_report_internal_chain_ceiling_r8 import (
    ATTEMPT_ID,
    ATTEMPT_RECEIPT_REF,
    AUTHORITY,
    EXECUTION_CONTRACT,
    EXPECTED_BOUND_INPUT_IDS,
    EXPECTED_IMPLEMENTATION_PATHS,
    MIN_FREE_BYTES_BEFORE_ATTEMPT,
    POLICY_REF,
    PRIVATE_REF,
    PRIVATE_RESULT_SCHEMA_VERSION,
    PROGRAM_ID,
    PUBLIC_REF,
    RAW_EXECUTION_CAPTURE_REF,
    SEMANTIC_CONTRACT,
    TERMINAL_FAILURE_RECEIPT_REF,
    DellReportInternalChainCeilingR8Error,
    assess_dell_report_internal_chain_r8_packages,
    build_dell_report_internal_chain_ceiling_r8_public_projection,
    validate_dell_report_internal_chain_ceiling_r8_policy,
)
from retrieval.query_plan import canonical_digest
from scripts.data_retrieval import (
    run_dell_report_internal_chain_ceiling_r8 as r8_runner,
)


ROOT = Path(__file__).resolve().parents[1]
R7_TEST_REF = ROOT / "tests/test_dell_report_internal_chain_ceiling_r7.py"


def _metadata() -> dict:
    return {
        "ticker": "DELL",
        "source_type": "PUBLIC_WEB",
        "source_tier": "named_counterparty_or_standards_primary",
        "publication_date": "2025-05-27",
    }


def _source(source_id: str, text: str) -> dict:
    return {
        "evidence_id": source_id,
        "text": text,
        "metadata": {},
        **_metadata(),
    }


def _object(object_id: str, source_id: str, text: str) -> dict:
    return {
        "compiled_object_id": object_id,
        "candidate_not_evidence": True,
        "evidence_promoted": False,
        "numeric_authority": False,
        "lineage_source_record_ids": [source_id],
        "model_text": text,
        "base_object_view": {
            "source_record_id": source_id,
            "focus_binding": {"mode": "parent_context"},
            **_metadata(),
        },
    }


@pytest.mark.parametrize(
    ("target_id", "text", "expected_frames"),
    [
        (
            ASP_TARGET,
            "NVIDIA quoted $15, and Dell sold the PowerEdge XE9680 hardware.",
            2,
        ),
        (
            ASP_TARGET,
            "Dell quoted $15 for PowerEdge hardware, allegedly.",
            1,
        ),
        (
            SUPPLIER_TARGET,
            "NVIDIA shipped chips, and Dell sold PowerEdge servers.",
            2,
        ),
        (
            SUPPLIER_TARGET,
            "NVIDIA supplies Dell AI servers, according to an unconfirmed report.",
            1,
        ),
        (
            CAPACITY_TARGET,
            "Dell received financing alongside GPU capacity being allocated to HP in Q1 2026.",
            2,
        ),
        (
            YIELD_TARGET,
            "Solar-panel production yield was 90%, and GPU sales rose in 2026.",
            2,
        ),
        (
            HBM_TARGET,
            "HBM supply was available to HP, and Dell announced earnings.",
            2,
        ),
        (
            UNITS_TARGET,
            "Dell shipped marketing materials, and NVIDIA delivered four "
            "PowerEdge XE9680 AI servers in Q1 2026.",
            2,
        ),
    ],
)
def test_r8_fresh_audit_false_complete_attacks_are_frame_local(
    target_id: str,
    text: str,
    expected_frames: int,
) -> None:
    records = frame_records(text)
    assert len(records) == expected_frames
    assessment = classify_package(
        target_id=target_id,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] != "complete_bounded_target_package"
    assert assessment["accepted_frame_id"] is None
    for frame in assessment["predicate_frames"]:
        assert frame["span_start"] <= frame["predicate_span_start"]
        assert frame["predicate_span_end"] <= frame["span_end"]
        for binding in frame["role_bindings"] + frame["scope_bindings"]:
            assert frame["span_start"] <= binding["span_start"]
            assert binding["span_end"] <= frame["span_end"]


def test_r8_trailing_uncertainty_is_bound_to_the_full_frame() -> None:
    frames = extract_predicate_frames(
        target_id=SUPPLIER_TARGET,
        text=(
            "NVIDIA supplies Dell AI servers, according to an "
            "unconfirmed report."
        ),
        metadata=_metadata(),
    )
    assert len(frames) == 1
    frame = frames[0]
    assert frame.modality == "alleged_or_rumor"
    assert "alleged_rumor_or_unconfirmed_target_frame" in frame.limitations
    assert any(row.role == "scope.modality" for row in frame.scope_bindings)


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            SUPPLIER_TARGET,
            "Dell and NVIDIA partnered for delivery, but the partnership was later suspended.",
        ),
        (
            CAPACITY_TARGET,
            "GPU production capacity was allocated to Dell in Q1 2026; "
            "the allocation was later revoked.",
        ),
        (
            YIELD_TARGET,
            "HBM production yield was 90% in 2026, but the figure was later withdrawn.",
        ),
        (
            ASP_TARGET,
            "Dell quoted $15 for PowerEdge hardware, but the quote was later withdrawn.",
        ),
    ],
)
def test_r8_coreferential_retraction_is_inside_the_target_frame_scope(
    target_id: str,
    text: str,
) -> None:
    records = frame_records(text)
    assert len(records) == 1
    frames = extract_predicate_frames(
        target_id=target_id,
        text=text,
        metadata=_metadata(),
    )
    assert len(frames) == 1
    frame = frames[0]
    assert frame.accepted is False
    assert frame.status == "revoked_suspended_or_withdrawn"
    status_binding = next(
        row for row in frame.scope_bindings if row.role == "scope.status"
    )
    assert frame.span_start <= status_binding.span_start
    assert status_binding.span_end <= frame.span_end


def test_r8_future_language_in_next_sentence_does_not_modify_current_partnership() -> None:
    text = (
        "NVIDIA and Dell are partnering to deliver AI infrastructure. "
        "This platform will power future systems."
    )
    records = frame_records(text)
    assert len(records) == 2
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
    assert accepted["modality"] == "actual"
    assert "will" not in accepted["frame_text"]


def test_r8_malformed_period_boundary_does_not_leak_next_sentence_roles() -> None:
    text = (
        "Dell and NVIDIA have partnered for decades and continue to push "
        "innovation . In its last earnings call, Dell projected that its AI "
        "server business will grow."
    )
    records = frame_records(text)
    assert len(records) == 2
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
    assert accepted["frame_text"].endswith("push innovation")
    assert "product:ai_server_system" not in accepted["role_anchors"]
    assert accepted["modality"] == "actual"


def test_r8_residual_sentence_split_preserves_initialism() -> None:
    records = frame_records(
        "One of Dell's U.S. factories shipped four PowerEdge AI servers in Q1 2026."
    )
    assert len(records) == 1
    assert "u.s. factories" in records[0].text


def test_r8_coordinator_split_preserves_compound_company_subject() -> None:
    text = (
        "Dell, NVIDIA, and Micron partnered to deliver AI infrastructure."
    )
    records = frame_records(text)
    assert len(records) == 1
    assessment = classify_package(
        target_id=SUPPLIER_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] == "complete_bounded_target_package"


def test_r8_dell_product_with_supplier_component_keeps_dell_as_actor() -> None:
    assessment = classify_package(
        target_id=SUPPLIER_TARGET,
        text=(
            "Dell servers with NVIDIA GB200 are shipping at scale for "
            "customers."
        ),
        metadata=_metadata(),
    )
    assert assessment["classification"] == "complete_bounded_target_package"
    accepted = next(
        row
        for row in assessment["predicate_frames"]
        if row["frame_id"] == assessment["accepted_frame_id"]
    )
    actors = [
        row["normalized_value"]
        for row in accepted["role_bindings"]
        if row["role"] == "actor"
    ]
    assert actors == ["Dell"]
    suppliers = [
        row["normalized_value"]
        for row in accepted["role_bindings"]
        if row["role"] == "supplier"
    ]
    recipients = [
        row["normalized_value"]
        for row in accepted["role_bindings"]
        if row["role"] == "recipient"
    ]
    assert suppliers == ["nvidia"]
    assert recipients == ["customer_market"]
    assert "counterparty:nvidia" in accepted["role_anchors"]
    assert "supplier_entity:nvidia" in accepted["role_anchors"]


@pytest.mark.parametrize(
    ("target_id", "text", "expected_predicate"),
    [
        (SUPPLIER_TARGET, "NVIDIA provides GPUs to Dell.", "provides"),
        (
            CAPACITY_TARGET,
            "NVIDIA released GPU capacity to Dell in Q1 2026.",
            "released",
        ),
        (YIELD_TARGET, "HBM production yielded 90% in 2026.", "yielded"),
        (
            HBM_TARGET,
            "Dell PowerEdge servers use HBM in Q1 2026.",
            "use",
        ),
        (
            UNITS_TARGET,
            "Dell dispatched four PowerEdge XE9680 AI servers in Q1 2026.",
            "dispatched",
        ),
        (
            ASP_TARGET,
            "Dell offered PowerEdge hardware for USD 15 in FY2026.",
            "offered",
        ),
    ],
)
def test_r8_fresh_audit_positive_controls_have_span_bound_roles(
    target_id: str,
    text: str,
    expected_predicate: str,
) -> None:
    assessment = classify_package(
        target_id=target_id,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] == "complete_bounded_target_package"
    assert assessment["accepted_frame_id"].startswith("FRAME::R8::")
    accepted = next(
        row
        for row in assessment["predicate_frames"]
        if row["frame_id"] == assessment["accepted_frame_id"]
    )
    predicates = [
        row for row in accepted["role_bindings"] if row["role"] == "predicate"
    ]
    assert len(predicates) == 1
    assert predicates[0]["normalized_value"] == expected_predicate
    assert accepted["accepted"] is True
    assert accepted["missing_required_roles"] == []
    assert accepted["ambiguities"] == []


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (SUPPLIER_TARGET, "Dell and NVIDIA have no partnership for delivery."),
        (SUPPLIER_TARGET, "NVIDIA failed to supply Dell for AI server delivery."),
        (SUPPLIER_TARGET, "Dell and NVIDIA may partner for delivery."),
        (
            SUPPLIER_TARGET,
            "Dell and NVIDIA partnered for delivery, but the partnership was later suspended.",
        ),
        (SUPPLIER_TARGET, "NVIDIA can supply Dell for AI server delivery."),
        (
            CAPACITY_TARGET,
            "GPU production capacity was not allocated to Dell in Q1 2026.",
        ),
        (
            CAPACITY_TARGET,
            "GPU production capacity will be allocated to Dell in Q1 2026.",
        ),
        (
            CAPACITY_TARGET,
            "GPU production capacity was allocated to HP rather than to Dell in Q1 2026.",
        ),
        (
            CAPACITY_TARGET,
            "Zero GPU production capacity was allocated to Dell in Q1 2026.",
        ),
        (
            CAPACITY_TARGET,
            "GPU production capacity was allocated to Dell in Q1 2026; "
            "the allocation was later revoked.",
        ),
        (
            YIELD_TARGET,
            "HBM production yield rate is forecast to reach 90% in 2026.",
        ),
        (
            YIELD_TARGET,
            "Prototype-line HBM production yield was 90% in 2026.",
        ),
        (
            YIELD_TARGET,
            "HBM production yield was 90%, but the figure was later withdrawn.",
        ),
        (
            YIELD_TARGET,
            "Simulated HBM production yield was 90% in 2026.",
        ),
        (
            YIELD_TARGET,
            "HBM supply was constrained. Orange juice production yield was 90% in 2026.",
        ),
        (
            HBM_TARGET,
            "HBM supply capacity was unavailable to Dell in Q1 2026.",
        ),
        (
            HBM_TARGET,
            "HBM capacity was available in Q1 2026; PowerEdge systems were "
            "configured without HBM.",
        ),
        (
            UNITS_TARGET,
            "Dell has not shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            UNITS_TARGET,
            "Acme reported Dell shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            UNITS_TARGET,
            "Dell disputed reports it shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            ASP_TARGET,
            "Dell expects to quote $15 for two PowerEdge XE9680 servers.",
        ),
        (
            ASP_TARGET,
            "Dell allegedly quoted $15 for two Dell PowerEdge XE9680 servers.",
        ),
        (
            ASP_TARGET,
            "Dell quoted $15 for two Dell PowerEdge XE9680 servers, but the "
            "quote was later withdrawn.",
        ),
        (ASP_TARGET, "HPE quoted $15. Dell offered two PowerEdge XE9680 servers."),
    ],
)
def test_r8_preserves_selected_r7_negative_semantic_contract(
    target_id: str,
    text: str,
) -> None:
    assessment = classify_package(
        target_id=target_id,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] != "complete_bounded_target_package"
    assert assessment["accepted_frame_id"] is None


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


def test_r8_inherits_all_immutable_r7_negative_semantic_attacks() -> None:
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


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            SUPPLIER_TARGET,
            "NVIDIA is Dell's supplier for AI server delivery.",
        ),
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
            "GPU production capacity was allocated to Dell in Q1 2026, but "
            "another component was unavailable.",
        ),
        (
            YIELD_TARGET,
            "HBM production achieved a 90% yield in 2026.",
        ),
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
        (
            ASP_TARGET,
            "Dell sold two Dell PowerEdge XE9680 servers for $15.",
        ),
        (
            ASP_TARGET,
            "Dell quoted $15 for two Dell PowerEdge XE9680 servers and will offer support later.",
        ),
    ],
)
def test_r8_preserves_selected_r7_positive_semantic_contract(
    target_id: str,
    text: str,
) -> None:
    assessment = classify_package(
        target_id=target_id,
        text=text,
        metadata=_metadata(),
    )
    assert assessment["classification"] == "complete_bounded_target_package"
    assert assessment["accepted_frame_id"].startswith("FRAME::R8::")


def test_r8_price_anchor_uses_hardware_argument_not_support_price() -> None:
    assessment = classify_package(
        target_id=ASP_TARGET,
        text=(
            "Dell quoted $150 for support plus $15 for PowerEdge "
            "XE9680 hardware."
        ),
        metadata=_metadata(),
    )
    assert assessment["classification"] == "complete_bounded_target_package"
    assert "price.hardware.currency_usd:15" in assessment[
        "accepted_frame_role_anchors"
    ]
    assert "price.hardware.currency_usd:150" not in assessment[
        "accepted_frame_role_anchors"
    ]
    frame = next(
        row
        for row in assessment["predicate_frames"]
        if row["frame_id"] == assessment["accepted_frame_id"]
    )
    prices = [row for row in frame["role_bindings"] if row["role"] == "price"]
    assert [row["normalized_value"] for row in prices] == ["15"]
    assert prices[0]["raw_text"].strip() == "$15"


def test_r8_frame_digest_and_role_bindings_are_deterministic_and_immutable() -> None:
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


def test_r8_frame_and_role_spans_are_exact_normalized_document_slices() -> None:
    text = (
        "Dell and NVIDIA partnered for delivery, but the partnership was "
        "later suspended. Dell offered PowerEdge hardware for USD 15 in "
        "FY2026."
    )
    normalized = normalize_text(text)
    frames = extract_predicate_frames(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert len(frames) == 1
    frame = frames[0]
    assert normalized[frame.span_start : frame.span_end] == frame.frame_text
    predicate = next(
        row for row in frame.role_bindings if row.role == "predicate"
    )
    assert normalized[predicate.span_start : predicate.span_end] == (
        predicate.raw_text
    )


@pytest.mark.parametrize(
    ("field", "payload"),
    [
        (
            "request_ids",
            "REQ::DELL::TOKEN_LIVE_PRODUCTION_A1B2C3D4E5F6G7H8::V1",
        ),
        (
            "target_proposition",
            "See https%2525253A%2525252F%2525252Fexample.invalid%2525252Fprivate",
        ),
    ],
)
def test_r8_public_validation_rejects_fresh_audit_bypasses(
    field: str,
    payload: str,
) -> None:
    with pytest.raises(DellReportPublicValidationR8Error):
        validate_public_string_r8(
            payload,
            field=field,
            path=f"public.{field}",
        )


def test_r8_public_validation_checks_nested_identifiers_before_acceptance() -> None:
    public = {
        "case_key": "DELL",
        "request_ids": ["REQ::DELL::ASP::V1"],
        "target_id": ASP_TARGET,
        "sha256": "a" * 64,
        "ref": "docs/project_os/current_context_pack.zh-CN.md",
        "target_proposition": "Dell offered hardware for $15 in FY2026.",
    }
    validate_public_scalar_tree_r8(
        public,
        target_ids=frozenset({ASP_TARGET}),
        attempt_id="dell-rsq-03b-internal-chain-r8",
    )
    assert (
        validate_public_string_r8(
            "REQ::DELL::ASP::V1",
            field="request_ids",
            path="public.request_ids[0]",
        )
        == "REQ::DELL::ASP::V1"
    )


@pytest.mark.parametrize(
    ("field", "payload"),
    [
        ("target_proposition", "See www.example.invalid/private"),
        ("target_proposition", "See https://example.invalid/private"),
        ("target_proposition", "See s3://private-bucket/raw.json"),
        ("target_proposition", "See /private/source/raw.json"),
        ("known_boundary", r"Private source at D:\secret\raw.txt"),
        (
            "target_proposition",
            "api_key = token_live_production_A1b2C3d4E5f6",
        ),
        (
            "target_proposition",
            "opaque Ab3Def5Gh7Jk9Lm2Np4Qr6St8Uv0Wx1Yz",
        ),
        (
            "target_proposition",
            "See h%74tps%3A%2F%2Fexample.invalid%2Fprivate",
        ),
        ("target_proposition", r"See ..\..\private\raw.txt"),
        ("target_proposition", "See ../../private/raw.txt"),
        (
            "ref",
            "configs/test/sk-proj-A1b2C3d4E5f6G7h8J9k0.json",
        ),
        (
            "ref",
            "configs/test/Ab3Def5Gh7Jk9Lm2Np4Qr6St8Uv0Wx1Yz.json",
        ),
        ("target_proposition", "unsafe\u202evalue"),
    ],
)
def test_r8_public_validation_inherits_r7_threat_controls(
    field: str,
    payload: str,
) -> None:
    with pytest.raises(DellReportPublicValidationR8Error):
        validate_public_string_r8(
            payload,
            field=field,
            path=f"public.{field}",
        )


def test_r8_public_validation_accepts_financial_narrative_and_repo_refs() -> None:
    assert validate_public_string_r8(
        "Dell PowerEdge XE9680 的 FY2026 bounded price 约为 $15，仍不是 company-wide ASP。",
        field="target_proposition",
        path="public.target_proposition",
    ).endswith("company-wide ASP。")
    assert validate_public_string_r8(
        "docs/project_os/current_context_pack.zh-CN.md",
        field="ref",
        path="public.ref",
    ) == "docs/project_os/current_context_pack.zh-CN.md"


def test_r8_source_object_union_final_share_the_same_frame_classifier() -> None:
    text = "Dell offered PowerEdge hardware for USD 15 in FY2026."
    source_rows = [_source("SRC::R8::ASP", text)]
    object_rows = [_object("COBJ::R8ASP0001", "SRC::R8::ASP", text)]
    corpus = assess_dell_report_internal_chain_r8_packages(
        target_id=ASP_TARGET,
        source_rows=source_rows,
        object_rows=object_rows,
    )
    assert corpus["coverage_gaps"] == []
    assert corpus["source_packages"][0]["classification"] == (
        "complete_bounded_target_package"
    )
    assert corpus["compiled_packages"][0]["classification"] == (
        "complete_bounded_target_package"
    )
    assert corpus["source_packages"][0]["accepted_frame_id"].startswith(
        "FRAME::R8::"
    )
    selected = assess_dell_report_internal_chain_r8_packages(
        target_id=ASP_TARGET,
        source_rows=source_rows,
        object_rows=object_rows,
        selected_object_ids={"COBJ::R8ASP0001"},
        rank_by_object_id={"COBJ::R8ASP0001": 2},
    )
    assert selected["compiled_packages"][0]["completion_rank"] == 2
    assert selected["compiled_packages"][0]["accepted_frame_digest"] == (
        corpus["compiled_packages"][0]["accepted_frame_digest"]
    )


def test_r8_material_coverage_does_not_accept_cross_frame_object_union() -> None:
    source_text = "Dell offered PowerEdge hardware for USD 15 in FY2026."
    object_text = (
        "NVIDIA quoted USD 15, and Dell sold PowerEdge hardware in FY2026."
    )
    source_rows = [_source("SRC::R8::GAP", source_text)]
    object_rows = [_object("COBJ::R8GAP0001", "SRC::R8::GAP", object_text)]
    corpus = assess_dell_report_internal_chain_r8_packages(
        target_id=ASP_TARGET,
        source_rows=source_rows,
        object_rows=object_rows,
    )
    assert corpus["source_packages"][0]["classification"] == (
        "complete_bounded_target_package"
    )
    assert corpus["compiled_packages"][0]["classification"] != (
        "complete_bounded_target_package"
    )
    assert corpus["coverage_gap_canonical_family_claim_count"] == 1
    assert corpus["coverage_gaps"][0]["anchor_mode"] == (
        "accepted_frame_role_span_bound_v4"
    )


def _redigest(value: dict) -> dict:
    body = dict(value)
    body.pop("result_digest", None)
    value["result_digest"] = canonical_digest(body)
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _r8_projection_fixture() -> dict:
    path = (
        ROOT
        / "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_"
        "candidate_ceiling/dell-rsq-03b-internal-chain-r7/full_result.json"
    )
    private = json.loads(path.read_text(encoding="utf-8"))
    private["schema_version"] = PRIVATE_RESULT_SCHEMA_VERSION
    private["attempt_id"] = ATTEMPT_ID
    private["status"] = (
        "dell_03B_R8_span_bound_predicate_frame_anchor_public_threat_ceiling_executed"
    )
    authority = dict(private["authority"])
    authority["03B_R8_execution_consumed"] = authority.pop(
        "03B_R7_execution_consumed"
    )
    private["authority"] = authority
    bindings = dict(private["input_bindings"])
    for binding_id in (
        "R7_public",
        "R7_private",
        "R7_attempt_receipt",
        "R7_fresh_audit",
        "R8_policy",
    ):
        bindings[binding_id] = {
            "ref": f"configs/test/{binding_id}.json",
            "sha256": "a" * 64,
            "result_digest": "b" * 64,
        }
    bindings["git_identity"] = dict(bindings["git_identity"])
    bindings["git_identity"]["authority_commit_changed_paths"] = [POLICY_REF]
    private["input_bindings"] = bindings
    private["policy_digest"] = "d" * 64
    return _redigest(private)


def test_r8_public_projection_accepts_bound_fixture_and_drops_private_rows() -> None:
    private = _r8_projection_fixture()
    public = build_dell_report_internal_chain_ceiling_r8_public_projection(
        private_result=private,
        private_ref=PRIVATE_REF,
        private_sha256="c" * 64,
    )
    assert public["attempt_id"] == ATTEMPT_ID
    assert "raw_execution_receipt" not in public
    assert all(
        not any(key.startswith("private_") for key in row)
        for row in public["target_results"]
    )


@pytest.mark.parametrize(
    ("field", "payload"),
    [
        (
            "request_ids",
            ["REQ::DELL::TOKEN_LIVE_PRODUCTION_A1B2C3D4E5F6G7H8::V1"],
        ),
        (
            "target_proposition",
            "See https%2525253A%2525252F%2525252Fexample.invalid%2525252Fprivate",
        ),
    ],
)
def test_r8_public_projection_rejects_fresh_bypasses_inside_valid_schema(
    field: str,
    payload: object,
) -> None:
    private = deepcopy(_r8_projection_fixture())
    private["target_results"][0][field] = payload
    _redigest(private)
    with pytest.raises(DellReportPublicValidationR8Error):
        build_dell_report_internal_chain_ceiling_r8_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


@pytest.mark.parametrize(
    ("container", "field"),
    [
        ("target", "private_secret_payload"),
        ("candidate_ceiling", "source_locator"),
    ],
)
def test_r8_public_projection_rejects_unknown_fields_before_projection(
    container: str,
    field: str,
) -> None:
    private = deepcopy(_r8_projection_fixture())
    target = private["target_results"][0]
    destination = target if container == "target" else target[container]
    destination[field] = "SENSITIVE EXCERPT"
    _redigest(private)
    with pytest.raises(DellReportInternalChainCeilingR8Error):
        build_dell_report_internal_chain_ceiling_r8_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


def _r8_policy_fixture() -> tuple[dict, dict[str, dict]]:
    r7_policy_path = (
        ROOT
        / "configs/retrieval/"
        "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_6.json"
    )
    r7_policy = json.loads(r7_policy_path.read_text(encoding="utf-8"))
    values = {
        binding_id[0].lower() + binding_id[1:]: json.loads(
            (ROOT / row["ref"]).read_text(encoding="utf-8")
        )
        for binding_id, row in r7_policy["bound_inputs"].items()
    }
    r7_public_path = (
        ROOT
        / "configs/retrieval/"
        "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_6.json"
    )
    r7_private_path = ROOT / (
        "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_"
        "candidate_ceiling/dell-rsq-03b-internal-chain-r7/full_result.json"
    )
    r7_receipt_path = r7_private_path.with_name("attempt_consumption_receipt.json")
    r7_audit_path = ROOT / (
        "configs/audits/fin_ia_0_1_3_commit_22c85026_dell_03b_"
        "r7_fresh_dual_audit_fail_v1_0.json"
    )
    values.update(
        {
            "r7_policy": r7_policy,
            "r7_public": json.loads(r7_public_path.read_text(encoding="utf-8")),
            "r7_private": json.loads(r7_private_path.read_text(encoding="utf-8")),
            "r7_attempt_receipt": json.loads(
                r7_receipt_path.read_text(encoding="utf-8")
            ),
            "r7_fresh_audit": json.loads(
                r7_audit_path.read_text(encoding="utf-8")
            ),
        }
    )
    bound_inputs = deepcopy(r7_policy["bound_inputs"])
    for binding_id, path in (
        ("R7_policy", r7_policy_path),
        ("R7_public", r7_public_path),
        ("R7_private", r7_private_path),
        ("R7_attempt_receipt", r7_receipt_path),
        ("R7_fresh_audit", r7_audit_path),
    ):
        value_key = binding_id.casefold()
        value = values[value_key]
        bound_inputs[binding_id] = {
            "ref": path.relative_to(ROOT).as_posix(),
            "sha256": _sha(path),
            **(
                {"result_digest": value["result_digest"]}
                if value.get("result_digest")
                else {}
            ),
        }
    policy = deepcopy(r7_policy)
    policy.update(
        {
            "schema_version": (
                "fin_ia_dell_report_internal_chain_ceiling_policy_v1_7"
            ),
            "status": (
                "same_stage_R8_execution_authorized_after_fresh_R7_audit_failure"
            ),
            "program_id": PROGRAM_ID,
            "attempt_id": ATTEMPT_ID,
            "execution_contract": dict(EXECUTION_CONTRACT),
            "semantic_contract": dict(SEMANTIC_CONTRACT),
            "output_contract": {
                "policy_ref": POLICY_REF,
                "private_result_ref": PRIVATE_REF,
                "public_result_ref": PUBLIC_REF,
                "attempt_consumption_receipt_ref": ATTEMPT_RECEIPT_REF,
                "raw_execution_capture_ref": RAW_EXECUTION_CAPTURE_REF,
                "terminal_failure_receipt_ref": TERMINAL_FAILURE_RECEIPT_REF,
                "alternate_output_paths_authorized": False,
                "private_public_same_path_authorized": False,
                "exclusive_create_required": True,
                "atomic_pair_with_rollback_required": True,
                "same_attempt_retry_authorized": False,
                "minimum_free_bytes_before_attempt": MIN_FREE_BYTES_BEFORE_ATTEMPT,
            },
            "bound_inputs": bound_inputs,
            "execution_identity": {
                "branch": "codex/fin013-dell-s1-s2-product-bridge",
                "implementation_commit": "a" * 40,
                "implementation_tree": "b" * 40,
                "authority_commit_changed_paths": [POLICY_REF],
                "authority_commit_parent_must_equal_implementation_commit": True,
                "HEAD_must_equal_upstream": True,
            },
            "implementation_bindings": [
                {"path": path, "sha256": "a" * 64}
                for path in sorted(EXPECTED_IMPLEMENTATION_PATHS)
            ],
            "authority": dict(AUTHORITY),
        }
    )
    _redigest(policy)
    assert set(policy["bound_inputs"]) == EXPECTED_BOUND_INPUT_IDS
    return policy, values


def test_r8_policy_binds_immutable_r7_failure_and_predecessor_chain() -> None:
    policy, values = _r8_policy_fixture()
    validated = validate_dell_report_internal_chain_ceiling_r8_policy(
        policy,
        **values,
    )
    assert validated["attempt_id"] == "dell-rsq-03b-internal-chain-r1"


def test_r8_policy_rejects_missing_r7_material_finding() -> None:
    policy, values = _r8_policy_fixture()
    drift = deepcopy(values)
    drift["r7_fresh_audit"] = deepcopy(values["r7_fresh_audit"])
    drift["r7_fresh_audit"]["material_findings"] = [
        row
        for row in drift["r7_fresh_audit"]["material_findings"]
        if row.get("finding_id")
        != "R7-P2-3-public-allowed-value-secret-and-fixed-depth-decode-bypass"
    ]
    _redigest(drift["r7_fresh_audit"])
    with pytest.raises(
        DellReportInternalChainCeilingR8Error,
        match="required_R7_findings_invalid",
    ):
        validate_dell_report_internal_chain_ceiling_r8_policy(
            policy,
            **drift,
        )


@pytest.mark.parametrize(
    "field",
    ("raw_execution_capture_ref", "terminal_failure_receipt_ref"),
)
def test_r8_policy_requires_failure_preservation_output_paths(
    field: str,
) -> None:
    policy, values = _r8_policy_fixture()
    policy["output_contract"].pop(field)
    _redigest(policy)
    with pytest.raises(
        DellReportInternalChainCeilingR8Error,
        match="output_contract_invalid",
    ):
        validate_dell_report_internal_chain_ceiling_r8_policy(
            policy,
            **values,
        )


def test_r8_runner_requires_an_explicit_mode() -> None:
    with pytest.raises(SystemExit) as exc_info:
        r8_runner.main([])
    assert exc_info.value.code == 2


def test_r8_formal_runner_fails_before_receipt_when_policy_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    private = tmp_path / "private" / "full_result.json"
    public = tmp_path / "public.json"
    receipt = private.with_name("attempt_consumption_receipt.json")
    raw_capture = private.with_name("raw_execution_capture.json")
    terminal_failure = private.with_name("terminal_failure_receipt.json")
    monkeypatch.setattr(r8_runner, "DEFAULT_PRIVATE", private)
    monkeypatch.setattr(r8_runner, "DEFAULT_PUBLIC", public)
    monkeypatch.setattr(r8_runner, "ATTEMPT_RECEIPT", receipt)
    monkeypatch.setattr(r8_runner, "RAW_EXECUTION_CAPTURE", raw_capture)
    monkeypatch.setattr(
        r8_runner,
        "TERMINAL_FAILURE_RECEIPT",
        terminal_failure,
    )
    monkeypatch.setattr(r8_runner, "POLICY", tmp_path / "missing_policy.json")
    monkeypatch.setattr(
        r8_runner,
        "_require_output_disk_capacity",
        lambda: {"free_bytes": 1, "minimum_free_bytes": 1},
    )
    with pytest.raises(
        FileNotFoundError,
        match="dell_03B_R8_canonical_policy_missing",
    ):
        r8_runner.run_authorized_formal()
    assert not receipt.exists()
    assert not receipt.parent.exists()


def test_r8_raw_capture_precedes_redacted_terminal_failure_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "attempt"
    attempt_dir.mkdir()
    raw_capture_path = attempt_dir / "raw_execution_capture.json"
    terminal_path = attempt_dir / "terminal_failure_receipt.json"
    monkeypatch.setattr(
        r8_runner,
        "RAW_EXECUTION_CAPTURE",
        raw_capture_path,
    )
    monkeypatch.setattr(
        r8_runner,
        "TERMINAL_FAILURE_RECEIPT",
        terminal_path,
    )
    policy = {"result_digest": "a" * 64}
    execution = {"request_results": [{"request_id": "REQ::DELL::ASP::V1"}]}
    execution_sha256 = hashlib.sha256(
        r8_runner.base._canonical_json_bytes(execution)
    ).hexdigest()
    capture = r8_runner._write_raw_execution_capture(
        policy=policy,
        execution=execution,
        execution_sha256=execution_sha256,
        recorded_at="2026-08-27T00:00:00+00:00",
    )
    assert capture["raw_execution"] == execution
    assert capture["raw_execution_sha256"] == execution_sha256
    terminal = r8_runner._write_terminal_failure_receipt(
        policy=policy,
        stage="private_result_compilation",
        exception_type="RuntimeError",
        recorded_at="2026-08-27T00:00:01+00:00",
    )
    assert terminal["exception_type"] == "RuntimeError"
    assert terminal["exception_message_persisted"] is False
    assert terminal["raw_execution_capture"]["sha256"] == _sha(
        raw_capture_path
    )
    serialized = terminal_path.read_text(encoding="utf-8")
    assert "provider response body" not in serialized
    with pytest.raises(
        FileExistsError,
        match="dell_03B_R8_terminal_failure_receipt_exists",
    ):
        r8_runner._write_terminal_failure_receipt(
            policy=policy,
            stage="retry",
            exception_type="RuntimeError",
            recorded_at="2026-08-27T00:00:02+00:00",
        )


def test_r8_clean_git_receipt_binds_exact_parent_tree_and_policy_only_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    implementation_commit = "a" * 40
    implementation_tree = "b" * 40
    authority_commit = "c" * 40
    authority_tree = "d" * 40
    policy = {
        "execution_identity": {
            "branch": r8_runner.BRANCH,
            "implementation_commit": implementation_commit,
            "implementation_tree": implementation_tree,
            "authority_commit_changed_paths": [POLICY_REF],
        }
    }
    outputs = {
        ("status", "--porcelain", "--untracked-files=all"): "",
        ("rev-parse", "--abbrev-ref", "HEAD"): r8_runner.BRANCH,
        ("rev-parse", "HEAD"): authority_commit,
        ("rev-parse", "@{upstream}"): authority_commit,
        ("show", "-s", "--format=%P", "HEAD"): implementation_commit,
        (
            "show",
            "-s",
            "--format=%T",
            implementation_commit,
        ): implementation_tree,
        ("show", "-s", "--format=%T", "HEAD"): authority_tree,
        (
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "HEAD",
        ): POLICY_REF,
    }
    monkeypatch.setattr(r8_runner, "_git", lambda *args: outputs[args])
    receipt = r8_runner._clean_exact_git_receipt(policy)
    assert receipt["authority_parent_exact"] is True
    assert receipt["head_tree"] == authority_tree
    outputs[
        (
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "HEAD",
        )
    ] = f"{POLICY_REF}\nsrc/unexpected.py"
    with pytest.raises(
        RuntimeError,
        match="dell_03B_R8_exact_clean_synced_git_identity_required",
    ):
        r8_runner._clean_exact_git_receipt(policy)


def test_r8_attempt_receipt_is_exclusive_create_and_exact_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "attempt" / "attempt_consumption_receipt.json"
    monkeypatch.setattr(r8_runner, "ATTEMPT_RECEIPT", receipt)
    policy = {"result_digest": "a" * 64}
    git_receipt = {
        "head": "b" * 40,
        "head_tree": "c" * 40,
        "implementation_commit": "d" * 40,
        "implementation_tree": "e" * 40,
    }
    first = r8_runner._write_attempt_consumption_receipt(
        policy=policy,
        git_receipt=git_receipt,
        recorded_at="2026-08-27T00:00:00+00:00",
    )
    assert json.loads(receipt.read_text(encoding="utf-8")) == first
    with pytest.raises(
        FileExistsError,
        match="dell_03B_R8_attempt_already_consumed",
    ):
        r8_runner._write_attempt_consumption_receipt(
            policy=policy,
            git_receipt=git_receipt,
            recorded_at="2026-08-27T00:00:01+00:00",
        )


def test_r8_atomic_pair_rolls_back_if_second_publish_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    private = tmp_path / "private" / "full_result.json"
    public = tmp_path / "public" / "result.json"
    monkeypatch.setattr(r8_runner, "DEFAULT_PRIVATE", private)
    monkeypatch.setattr(r8_runner, "DEFAULT_PUBLIC", public)
    real_link = r8_runner.os.link
    link_calls = 0

    def fail_second_link(source: Path, destination: Path) -> None:
        nonlocal link_calls
        link_calls += 1
        if link_calls == 2:
            raise OSError("synthetic_second_publish_failure")
        real_link(source, destination)

    monkeypatch.setattr(r8_runner.os, "link", fail_second_link)
    with pytest.raises(OSError, match="synthetic_second_publish_failure"):
        r8_runner._publish_atomic_pair(
            private_bytes=b"private",
            public_bytes=b"public",
        )
    assert not private.exists()
    assert not public.exists()
    assert not list(private.parent.glob(".*.tmp"))
    assert not list(public.parent.glob(".*.tmp"))
