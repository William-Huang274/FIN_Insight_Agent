from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime import canonical_digest
import sec_agent.research.report_gap_crosswalk as CROSSWALK
from sec_agent.research.report_gap_crosswalk import (
    ReportGapCrosswalkError,
    compile_report_gap_crosswalk,
    validate_crosswalk_projections,
    validate_evaluation_protocol,
    validate_execution_authority_template,
    validate_program_baseline_manifest,
)


pytestmark = pytest.mark.requires_local_data

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/research/materialize_dell_report_gap_crosswalk.py"
SPEC = importlib.util.spec_from_file_location("dell_report_gap_crosswalk_runner", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)

BASELINE_PATH = ROOT / RUNNER.DEFAULT_BASELINE
BASELINE_VERIFICATION_PATH = ROOT / RUNNER.DEFAULT_BASELINE_VERIFICATION
PROTOCOL_PATH = ROOT / RUNNER.DEFAULT_PROTOCOL
AUTHORITY_TEMPLATE_PATH = ROOT / RUNNER.DEFAULT_AUTHORITY_TEMPLATE
PROGRAM_PATH = ROOT / RUNNER.DEFAULT_PROGRAM


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _redigest(value: dict, field: str) -> dict:
    value[field] = canonical_digest(
        {key: item for key, item in value.items() if key != field}
    )
    return value


@pytest.fixture(scope="module")
def local_inputs() -> dict:
    baseline = _json(BASELINE_PATH)
    verification = _json(BASELINE_VERIFICATION_PATH)
    source_bytes: dict[str, bytes] = {}
    git_blob_by_source_ref: dict[str, str] = {}
    git_blob_by_commit_ref: dict[str, str] = {}
    missing: list[str] = []
    bindings = [
        *baseline["input_bindings"].values(),
        *verification["input_bindings"].values(),
    ]
    for binding in bindings:
        path = ROOT / binding["ref"]
        if not path.is_file():
            missing.append(binding["ref"])
        else:
            source_bytes[binding["ref"]] = path.read_bytes()
        if binding["git_tracking"] == "tracked":
            key = f'{binding["git_commit"]}:{binding["ref"]}'
            git_blob_by_source_ref[binding["ref"]] = RUNNER._git_blob_for_source_bytes(
                binding["ref"], source_bytes[binding["ref"]]
            )
            git_blob_by_commit_ref[key] = RUNNER._git_blob_at_commit(
                binding["git_commit"], binding["ref"]
            )
    if missing:
        pytest.skip(f"private baseline inputs absent: {missing}")
    parsed = validate_program_baseline_manifest(
        baseline,
        verification=verification,
        source_bytes_by_ref=source_bytes,
        git_blob_by_source_ref=git_blob_by_source_ref,
        git_blob_by_commit_ref=git_blob_by_commit_ref,
    )
    return {
        "baseline": baseline,
        "verification": verification,
        "source_bytes": source_bytes,
        "git_blob_by_source_ref": git_blob_by_source_ref,
        "git_blob_by_commit_ref": git_blob_by_commit_ref,
        "parsed": parsed,
        "protocol": _json(PROTOCOL_PATH),
        "authority": _json(AUTHORITY_TEMPLATE_PATH),
        "program": _json(PROGRAM_PATH),
    }


def _compile(local_inputs: dict, **mutations: dict) -> dict:
    parsed = local_inputs["parsed"]
    values = {
        "baseline_manifest": local_inputs["baseline"],
        "evaluation_protocol": local_inputs["protocol"],
        "authority_template": local_inputs["authority"],
        "program": local_inputs["program"],
        "pack": parsed["R4_current_pack"],
        "R4_successor_result": parsed["R4_successor_result"],
        "R4_evidence_gate_result": parsed["R4_evidence_gate_result"],
        "dynamic_full_result": parsed["R38_private_full_result"],
        "writer_full_result": parsed["R17_private_full_result"],
        "readiness_public_result": parsed["product_readiness_public"],
        "readiness_private_result": parsed["product_readiness_private"],
        "bridge_public_result": parsed["S2_product_bridge_public"],
        "bridge_private_result": parsed["S2_product_bridge_private"],
    }
    values.update(mutations)
    return compile_report_gap_crosswalk(**values)


def test_baseline_manifest_binds_exact_predecessors_and_forbids_calls(
    local_inputs: dict,
) -> None:
    baseline = local_inputs["baseline"]

    assert set(local_inputs["parsed"]) == {
        key
        for key, binding in baseline["input_bindings"].items()
        if binding["content_type"] == "application/json"
    } | {
        "R4_successor_result",
        "R4_evidence_gate_result",
        "R1_failed_public_result",
    }
    assert baseline["frozen_counts"]["pack_residual_gaps"] == 14
    assert baseline["frozen_counts"]["dynamic_unit_gap_refs"] == 9
    assert baseline["frozen_counts"]["writer_gap_groups"] == 4
    assert baseline["frozen_counts"]["writer_gap_refs"] == 10
    assert set(baseline["future_model_node_authorities"].values()) == {
        "not_authorized"
    }
    assert baseline["frozen_R17_report_quality_baseline"][
        "formal_eight_dimension_score"
    ] is None
    assert baseline["frozen_R17_report_quality_baseline"][
        "author_diagnostic_score_reusable"
    ] is False


def test_baseline_manifest_rejects_byte_mutation_and_missing_private_input(
    local_inputs: dict,
) -> None:
    source_bytes = dict(local_inputs["source_bytes"])
    pack_ref = local_inputs["baseline"]["input_bindings"]["R4_current_pack"]["ref"]
    source_bytes[pack_ref] += b"\n"
    with pytest.raises(
        ReportGapCrosswalkError,
        match="baseline_input_sha256_mismatch:R4_current_pack",
    ):
        validate_program_baseline_manifest(
            local_inputs["baseline"],
            verification=local_inputs["verification"],
            source_bytes_by_ref=source_bytes,
            git_blob_by_source_ref=local_inputs["git_blob_by_source_ref"],
            git_blob_by_commit_ref=local_inputs["git_blob_by_commit_ref"],
        )

    source_bytes = dict(local_inputs["source_bytes"])
    del source_bytes[pack_ref]
    with pytest.raises(
        ReportGapCrosswalkError,
        match="baseline_input_missing:R4_current_pack",
    ):
        validate_program_baseline_manifest(
            local_inputs["baseline"],
            verification=local_inputs["verification"],
            source_bytes_by_ref=source_bytes,
            git_blob_by_source_ref=local_inputs["git_blob_by_source_ref"],
            git_blob_by_commit_ref=local_inputs["git_blob_by_commit_ref"],
        )


def test_baseline_recomputes_actual_counts_and_rejects_55_to_54_mutation(
    local_inputs: dict,
) -> None:
    parsed = deepcopy(local_inputs["parsed"])
    pack = deepcopy(parsed["R4_current_pack"])
    pack["evidence_items"].pop()
    pack["observed_counts"]["accepted_evidence_items"] = 54
    parsed["R4_current_pack"] = pack

    with pytest.raises(
        ReportGapCrosswalkError,
        match="baseline_R4_coverage_recompute_mismatch",
    ):
        CROSSWALK._recompute_baseline_counts(parsed)


def test_baseline_rejects_forged_tracked_git_identity(local_inputs: dict) -> None:
    baseline = deepcopy(local_inputs["baseline"])
    binding = baseline["input_bindings"]["R17_public_candidate"]
    binding["git_blob"] = "0" * 40
    binding["git_commit"] = "1" * 40
    _redigest(baseline, "manifest_digest")

    with pytest.raises(
        ReportGapCrosswalkError,
        match="baseline_input_git_blob_bytes_mismatch:R17_public_candidate",
    ):
        validate_program_baseline_manifest(
            baseline,
            verification=local_inputs["verification"],
            source_bytes_by_ref=local_inputs["source_bytes"],
            git_blob_by_source_ref=local_inputs["git_blob_by_source_ref"],
            git_blob_by_commit_ref=local_inputs["git_blob_by_commit_ref"],
        )


def test_quality_and_execution_authority_protocols_are_preregistered(
    local_inputs: dict,
) -> None:
    validate_evaluation_protocol(local_inputs["protocol"], local_inputs["baseline"])
    validate_execution_authority_template(
        local_inputs["authority"], local_inputs["baseline"]
    )

    protocol = local_inputs["protocol"]
    assert protocol["eight_dimension_thresholds"]["total_minimum"] == 24
    assert protocol["formal_scoring_prerequisites"][
        "missing_component_disposition"
    ] == "not_assessable"
    assert protocol["frozen_R17_baseline"]["severity_counts"] == {
        "P0": 0,
        "P1": 1,
        "P2": 2,
        "P3": 1,
    }
    assert all(
        node["authority_status"] == "not_authorized"
        and node["attempt_id"] is None
        for node in local_inputs["authority"]["node_templates"].values()
    )


def test_quality_protocol_rejects_model_self_scoring_and_missing_report_surface(
    local_inputs: dict,
) -> None:
    protocol = deepcopy(local_inputs["protocol"])
    protocol["scoring_authority"]["model_self_score_formal"] = True
    _redigest(protocol, "protocol_digest")
    with pytest.raises(
        ReportGapCrosswalkError,
        match="evaluation_protocol_scoring_authority_granted",
    ):
        validate_evaluation_protocol(protocol, local_inputs["baseline"])

    protocol = deepcopy(local_inputs["protocol"])
    protocol["formal_scoring_prerequisites"]["required_packet_components"].remove(
        "reader_citation_appendix"
    )
    _redigest(protocol, "protocol_digest")
    with pytest.raises(
        ReportGapCrosswalkError,
        match="evaluation_protocol_prerequisite_contract_invalid",
    ):
        validate_evaluation_protocol(protocol, local_inputs["baseline"])


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("research_as_of", "evaluation_protocol_identity_invalid"),
        ("dimension_identity", "evaluation_protocol_threshold_contract_invalid"),
        ("reason_ref_schema", "evaluation_protocol_reason_ref_schema_invalid"),
        ("P1_blocks", "evaluation_protocol_severity_set_invalid"),
        (
            "immutable_target",
            "evaluation_protocol_immutable_target_contract_invalid",
        ),
    ],
)
def test_quality_protocol_frozen_surfaces_fail_closed(
    local_inputs: dict, mutation: str, error: str
) -> None:
    protocol = deepcopy(local_inputs["protocol"])
    if mutation == "research_as_of":
        protocol["research_as_of"] = "2026-08-07"
    elif mutation == "dimension_identity":
        protocol["eight_dimension_thresholds"]["dimensions"] = [
            f"fake_dimension_{index}" for index in range(8)
        ]
    elif mutation == "reason_ref_schema":
        protocol["reason_ref_schema"]["required_per_finding"].remove("reason_refs")
    elif mutation == "P1_blocks":
        protocol["finding_severity_contract"]["P1"]["blocks"] = []
    else:
        protocol["immutable_target_contract"]["R17_must_remain_immutable"] = False
    _redigest(protocol, "protocol_digest")

    with pytest.raises(ReportGapCrosswalkError, match=error):
        validate_evaluation_protocol(protocol, local_inputs["baseline"])


def test_crosswalk_compiles_exact_14_9_4_10_without_closing_a_gap(
    local_inputs: dict,
) -> None:
    result = _compile(local_inputs)
    audit = result["audit_projection"]

    assert audit["counts"] == {
        "pack_gaps": 14,
        "dynamic_unit_gaps": 9,
        "writer_groups": 4,
        "writer_gap_refs": 10,
        "S2_bridge_gaps": 4,
        "pack_gaps_not_selected_by_unit": 5,
        "pack_gaps_not_referenced_by_writer": 4,
    }
    assert audit["authority"]["gap_closed_count"] == 0
    assert audit["authority"]["proved_information_boundary_count"] == 0
    assert not any(row["closed"] for row in audit["pack_gap_entries"])
    assert {
        row["gap_id"]
        for row in audit["pack_gap_entries"]
        if row["research_disposition"] == "narrowed"
    } == {
        "dell-gap-pricing-asp",
        "dell-gap-pricing-units",
        "dell-gap-supplier-capacity-readthrough",
    }
    assert {
        row["gap_id"]
        for row in audit["pack_gap_entries"]
        if row["unit_selection_state"] == "not_selected_by_unit"
    } == set(local_inputs["program"]["expected_pack_gaps_not_selected_by_unit"])
    assert all(
        (
            row["unit_selection_state"] == "selected_by_unit"
            and row["technical_chain_state"] == "technical_chain_closed"
        )
        or (
            row["unit_selection_state"] == "not_selected_by_unit"
            and row["technical_chain_state"] == "technical_chain_not_evaluated"
        )
        for row in audit["pack_gap_entries"]
    )


def test_crosswalk_keeps_S2_product_profit_independent_and_PVM_null_visible(
    local_inputs: dict,
) -> None:
    result = _compile(local_inputs)
    audit_rows = result["audit_projection"]["S2_bridge_gap_entries"]
    profit = next(
        row
        for row in audit_rows
        if row["gap_id"] == "dell-gap-product-profit-attribution"
    )
    assert profit["pack_gap_id"] is None
    assert profit["current_value_state"] == "null_until_authorized_inputs"

    reader_rows = result["reader_visible_projection"]["S2_bridge_register"]
    pvm = next(row for row in reader_rows if row["label_en"] == "Price-volume-mix bridge")
    assert pvm["current_value_state"] == "null_until_authorized_inputs"


def test_crosswalk_three_projections_share_content_digest_without_leakage(
    local_inputs: dict,
) -> None:
    result = _compile(local_inputs)
    validate_crosswalk_projections(result)
    digest = result["crosswalk_content_digest"]
    assert result["audit_projection"]["crosswalk_content_digest"] == digest
    assert result["model_visible_projection"]["crosswalk_content_digest"] == digest
    assert result["reader_visible_projection"]["crosswalk_content_digest"] == digest
    reader_text = json.dumps(result["reader_visible_projection"], ensure_ascii=False)
    model_text = json.dumps(result["model_visible_projection"], ensure_ascii=False)
    assert "GAP::" not in reader_text
    assert "EV::" not in reader_text
    assert "data/workbench_private" not in reader_text
    assert "data/workbench_private" not in model_text


def test_crosswalk_digest_is_order_independent(local_inputs: dict) -> None:
    baseline = _compile(local_inputs)
    pack = deepcopy(local_inputs["parsed"]["R4_current_pack"])
    pack["residual_gaps"].reverse()
    dynamic = deepcopy(local_inputs["parsed"]["R38_private_full_result"])
    dynamic["workpaper_context"]["cell_analysis_view"]["cell"][
        "residual_gap_cards"
    ].reverse()
    writer = deepcopy(local_inputs["parsed"]["R17_private_full_result"])
    writer["candidate_draft"]["remaining_gaps"].reverse()
    bridge = deepcopy(local_inputs["parsed"]["S2_product_bridge_private"])
    bridge["product_value_bridge"]["bridge_gap_receipts"].reverse()

    reordered = _compile(
        local_inputs,
        pack=pack,
        dynamic_full_result=dynamic,
        writer_full_result=writer,
        bridge_private_result=bridge,
    )
    assert reordered["crosswalk_content_digest"] == baseline["crosswalk_content_digest"]


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("false_14_to_4", "crosswalk_pack_gap_count_invalid"),
        ("same_facet_conflict", "crosswalk_pack_facet_ambiguous"),
        ("unknown_writer_ref", "crosswalk_writer_unknown_gap_ref"),
        ("cross_ticker", "crosswalk_case_identity_mismatch"),
        ("bridge_masquerade", "crosswalk_bridge_gap_duplicate_or_invalid"),
        ("closed_without_receipt", "crosswalk_gap_policy_false_closure"),
    ],
)
def test_crosswalk_mutations_fail_closed(
    local_inputs: dict, mutation: str, error: str
) -> None:
    values: dict[str, dict] = {}
    if mutation in {"false_14_to_4", "same_facet_conflict"}:
        pack = deepcopy(local_inputs["parsed"]["R4_current_pack"])
        if mutation == "false_14_to_4":
            pack["residual_gaps"] = pack["residual_gaps"][:4]
        else:
            pack["residual_gaps"][1]["facet_id"] = pack["residual_gaps"][0][
                "facet_id"
            ]
        values["pack"] = pack
    elif mutation == "unknown_writer_ref":
        writer = deepcopy(local_inputs["parsed"]["R17_private_full_result"])
        writer["candidate_draft"]["remaining_gaps"][0]["gap_refs"][0] = (
            "GAP::UNKNOWN"
        )
        values["writer_full_result"] = writer
    elif mutation == "cross_ticker":
        writer = deepcopy(local_inputs["parsed"]["R17_private_full_result"])
        writer["case_key"] = "MU"
        values["writer_full_result"] = writer
    elif mutation == "bridge_masquerade":
        bridge = deepcopy(local_inputs["parsed"]["S2_product_bridge_private"])
        target = next(
            row
            for row in bridge["product_value_bridge"]["bridge_gap_receipts"]
            if row["gap_id"] == "dell-gap-product-profit-attribution"
        )
        target["gap_id"] = "dell-gap-price-volume-mix-bridge"
        values["bridge_private_result"] = bridge
    else:
        program = deepcopy(local_inputs["program"])
        program["gap_policies"][0]["research_disposition"] = "closed"
        _redigest(program, "program_digest")
        values["program"] = program

    with pytest.raises(ReportGapCrosswalkError, match=error):
        _compile(local_inputs, **values)


def test_projection_mutations_reject_private_leakage_and_hidden_PVM(
    local_inputs: dict,
) -> None:
    result = _compile(local_inputs)
    leaked = deepcopy(result)
    leaked["model_visible_projection"]["gap_boundaries"][0][
        "next_legal_action"
    ] = "data/workbench_private/secret.json"
    with pytest.raises(
        ReportGapCrosswalkError,
        match="crosswalk_model_projection_private_leakage",
    ):
        validate_crosswalk_projections(leaked)

    hidden = deepcopy(result)
    hidden["reader_visible_projection"]["S2_bridge_register"] = [
        row
        for row in hidden["reader_visible_projection"]["S2_bridge_register"]
        if row["label_en"] != "Price-volume-mix bridge"
    ]
    with pytest.raises(
        ReportGapCrosswalkError,
        match="crosswalk_reader_PVM_null_boundary_hidden",
    ):
        validate_crosswalk_projections(hidden)

    hidden_profit = deepcopy(result)
    hidden_profit["reader_visible_projection"]["S2_bridge_register"] = [
        row
        for row in hidden_profit["reader_visible_projection"]["S2_bridge_register"]
        if row["label_en"] != "AI-server product-profit attribution"
    ]
    with pytest.raises(
        ReportGapCrosswalkError,
        match="crosswalk_reader_product_profit_null_boundary_hidden",
    ):
        validate_crosswalk_projections(hidden_profit)


def test_projection_rejects_illegal_axis_value_and_digest_string_only_drift(
    local_inputs: dict,
) -> None:
    result = _compile(local_inputs)
    illegal = deepcopy(result)
    target = next(
        row
        for row in illegal["audit_projection"]["pack_gap_entries"]
        if row["unit_selection_state"] == "not_selected_by_unit"
    )
    target["technical_chain_state"] = "not_selected_by_unit"
    with pytest.raises(
        ReportGapCrosswalkError,
        match="crosswalk_audit_state_enum_invalid",
    ):
        validate_crosswalk_projections(illegal)

    drift = deepcopy(result)
    drift["audit_projection"]["pack_gap_entries"][0]["why_it_matters_en"] = (
        "Semantically drifted audit text."
    )
    audit = drift["audit_projection"]
    content = {
        "schema_version": CROSSWALK.CROSSWALK_CONTENT_SCHEMA_VERSION,
        "case_key": audit["case_key"],
        "research_as_of": audit["research_as_of"],
        "counts": audit["counts"],
        "pack_gap_entries": audit["pack_gap_entries"],
        "writer_groups": audit["writer_groups"],
        "S2_bridge_gap_entries": audit["S2_bridge_gap_entries"],
    }
    digest = canonical_digest(content)
    drift["crosswalk_content_digest"] = digest
    for projection_key in (
        "audit_projection",
        "model_visible_projection",
        "reader_visible_projection",
    ):
        drift[projection_key]["crosswalk_content_digest"] = digest
    with pytest.raises(
        ReportGapCrosswalkError,
        match="crosswalk_reader_projection_not_deterministic",
    ):
        validate_crosswalk_projections(drift)


def test_materializer_rejects_dirty_worktree_and_output_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(
        RUNNER.DellReportGapCrosswalkMaterializationError,
        match="report_gap_crosswalk_clean_worktree_required",
    ):
        RUNNER._require_clean_worktree("?? unexpected.txt")

    monkeypatch.setattr(RUNNER, "ROOT", tmp_path)
    existing = tmp_path / "already.json"
    existing.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        FileExistsError,
        match="report_gap_crosswalk_output_exists:already.json",
    ):
        RUNNER._write_new(existing, {"value": 1})


def test_materializer_builds_self_bound_zero_call_outputs(local_inputs: dict) -> None:
    compiled = RUNNER.compile_materialization(
        baseline_path=BASELINE_PATH,
        baseline_verification_path=BASELINE_VERIFICATION_PATH,
        protocol_path=PROTOCOL_PATH,
        authority_template_path=AUTHORITY_TEMPLATE_PATH,
        program_path=PROGRAM_PATH,
        private_output_path=ROOT / RUNNER.DEFAULT_PRIVATE_OUTPUT,
        recorded_at="2026-08-25T12:00:00+08:00",
        prepared_from_commit="TEST_COMMIT",
    )
    private = compiled["private"]
    public = compiled["public"]
    assert private["full_result_digest"] == canonical_digest(
        {key: value for key, value in private.items() if key != "full_result_digest"}
    )
    assert public["result_digest"] == canonical_digest(
        {key: value for key, value in public.items() if key != "result_digest"}
    )
    assert public["execution"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "embedding_calls": 0,
        "reranker_calls": 0,
        "candidate_promotions": 0,
        "evidence_promotions": 0,
        "gap_closures": 0,
    }
    assert public["acceptance"]["crosswalk_deterministic_contract_pass"] is True
    assert public["acceptance"]["independent_review_pass"] is False
    assert public["acceptance"]["G1_pass"] is False
