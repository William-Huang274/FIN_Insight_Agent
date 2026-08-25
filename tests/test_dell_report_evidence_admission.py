from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from retrieval.dell_report_evidence_admission import (
    DellReportEvidenceAdmissionError,
    _validate_predecessor_review_population,
    compile_dell_report_evidence_admission_packet,
    validate_dell_report_evidence_admission_program,
)
from retrieval.query_plan import canonical_digest


pytestmark = pytest.mark.requires_local_data

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "scripts/data_retrieval/materialize_dell_report_evidence_admission_packet.py"
)
SPEC = importlib.util.spec_from_file_location("dell_report_admission_runner", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
PROGRAM_PATH = ROOT / RUNNER.DEFAULT_PROGRAM


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _redigest(value: dict, field: str) -> None:
    value[field] = canonical_digest(
        {key: item for key, item in value.items() if key != field}
    )


@pytest.fixture(scope="module")
def local_inputs() -> dict:
    program = _json(PROGRAM_PATH)
    payloads: dict[str, dict] = {}
    sha256_by_ref: dict[str, str] = {}
    missing: list[str] = []
    for name, binding in program["input_bindings"].items():
        path = ROOT / binding["ref"]
        if not path.is_file():
            missing.append(binding["ref"])
            continue
        raw = path.read_bytes()
        sha256_by_ref[binding["ref"]] = hashlib.sha256(raw).hexdigest()
        if binding.get("digest_field") is not None:
            payloads[name] = json.loads(raw.decode("utf-8"))
    if missing:
        pytest.skip(f"private admission inputs absent: {missing}")
    return {
        "program": program,
        "payloads": payloads,
        "sha256_by_ref": sha256_by_ref,
    }


def _compile(local_inputs: dict, **overrides: object) -> dict:
    values = {
        "program": local_inputs["program"],
        "input_payloads": local_inputs["payloads"],
        "input_sha256_by_ref": local_inputs["sha256_by_ref"],
        "private_output_ref": RUNNER.DEFAULT_PRIVATE_OUTPUT,
        "recorded_at": "2026-08-25T16:00:00+08:00",
        "prepared_from_commit": "TEST_COMMIT",
    }
    values.update(overrides)
    return compile_dell_report_evidence_admission_packet(**values)


def _validate_population(local_inputs: dict, payloads: dict) -> object:
    return _validate_predecessor_review_population(
        readiness_public=payloads["current_readiness_public"],
        readiness_private=payloads["current_readiness_private"],
        expected=local_inputs["program"]["expected_scope"],
    )


def test_real_program_compiles_full_decision_set_and_blocker_subset(
    local_inputs: dict,
) -> None:
    result = _compile(local_inputs)
    private = result["private"]

    assert private["counts"] == {
        "request_count": 8,
        "candidate_review_item_count": 18,
        "all_human_required_item_count": 16,
        "blocked_request_count": 4,
        "blocked_request_human_item_count": 8,
        "bounded_or_direct_material_use_candidate_count": 5,
        "recommend_reject_no_current_material_report_use_count": 10,
        "recommend_rebind_duplicate_to_canonical_candidate_count": 1,
        "qualified_human_decision_count": 0,
    }
    blocker_requests = [
        request
        for request in private["requests"]
        if request["four_request_readiness_blocker_subset"]
    ]
    assert len(blocker_requests) == 4
    assert sum(request["human_item_count"] for request in blocker_requests) == 8
    assert private["scope_reconciliation"]["false_interpretation_rejected"] == (
        "four_requests_each_with_four_human_items"
    )
    assert private["predecessor_review_inventory"]["review_item_count"] == 18
    assert len(private["predecessor_review_inventory"]["items"]) == 18
    assert private["claim_use_recommendation_counts"] == {
        "bounded_or_direct_material_use_candidate_count": 5,
        "recommend_reject_no_current_material_report_use_count": 10,
        "recommend_rebind_duplicate_to_canonical_candidate_count": 1,
    }
    assert private["authority"]["G2_pass"] is False


def test_every_private_item_has_source_period_route_rights_and_report_use(
    local_inputs: dict,
) -> None:
    items = [
        item
        for request in _compile(local_inputs)["private"]["requests"]
        for item in request["items"]
    ]

    assert len(items) == 16
    assert len({item["review_item_ref"] for item in items}) == 16
    assert len({item["predecessor_review_item_digest"] for item in items}) == 16
    for item in items:
        source = item["source_identity"]
        assert source["source_owner_ticker"]
        assert source["research_subject_ticker"] == "DELL"
        assert source["publication_date"]
        assert source["reporting_period_end"]
        assert source["source_type"]
        assert source["source_url"].startswith("https://")
        assert item["bounded_excerpt_private_review_only"]
        assert item["citation_and_redistribution_rights"][
            "public_artifact_excerpt_allowed"
        ] is False
        assert item["retrieval_route"][
            "rank_or_embedding_score_is_admission_reason"
        ] is False
        assert item["advisory_evidence_role"]["advisory_only"] is True
        assert item["requirement_alignment"]["alignment_state"] == (
            "qualified_human_validation_pending"
        )
        assert item["report_claim_use"]["citation_padding_forbidden"] is True
        assert item["report_claim_use"][
            "recommendation_is_not_qualified_human_decision"
        ] is True
        assert item["decision_prefilled"] is False
        assert item["evidence_promotion_authorized"] is False
    by_recommendation = {}
    for item in items:
        recommendation = item["report_claim_use"]["review_recommendation"]
        by_recommendation.setdefault(recommendation, []).append(item)
    rejects = by_recommendation[
        "recommend_reject_no_current_material_report_use"
    ]
    duplicates = by_recommendation[
        "recommend_rebind_duplicate_to_canonical_candidate"
    ]
    candidates_with_use = [
        item for item in items if item["report_claim_use"]["report_claim_refs"]
    ]
    assert len(rejects) == 10
    assert len(duplicates) == 1
    assert len(candidates_with_use) == 5
    assert all(
        not item["report_claim_use"]["report_claim_refs"]
        and not item["report_claim_use"]["report_surface_paths"]
        for item in rejects + duplicates
    )


def test_public_projection_contains_no_excerpt_or_source_url(
    local_inputs: dict,
) -> None:
    public = _compile(local_inputs)["public"]
    rendered = json.dumps(public, ensure_ascii=False).casefold()

    assert len(public["items"]) == 16
    assert "bounded_excerpt" not in rendered
    assert "source_url" not in rendered
    assert "https://" not in rendered
    assert all(item["decision_state"] == "qualified_human_pending" for item in public["items"])


def test_program_rejects_four_request_sixteen_item_false_scope(
    local_inputs: dict,
) -> None:
    program = deepcopy(local_inputs["program"])
    program["expected_scope"]["blocked_request_human_item_count"] = 16
    _redigest(program, "program_digest")

    with pytest.raises(
        DellReportEvidenceAdmissionError,
        match="dell_report_admission_expected_scope_invalid",
    ):
        validate_dell_report_evidence_admission_program(program)


def test_nested_human_flag_mutation_fails_actual_request_recount(
    local_inputs: dict,
) -> None:
    payloads = deepcopy(local_inputs["payloads"])
    packet = payloads["current_readiness_private"]["candidate_review_packet"]
    item = packet["requests"][0]["review_items"][1]
    assert item["human_review_required"] is True
    item["human_review_required"] = False
    _redigest(item, "review_item_digest")
    _redigest(packet["requests"][0], "request_review_digest")
    _redigest(packet, "review_packet_digest")

    with pytest.raises(
        DellReportEvidenceAdmissionError,
        match="dell_report_admission_item_inventory_contract_drift",
    ):
        _validate_population(local_inputs, payloads)


def test_nested_item_delete_without_count_reseal_fails_request_recount(
    local_inputs: dict,
) -> None:
    payloads = deepcopy(local_inputs["payloads"])
    packet = payloads["current_readiness_private"]["candidate_review_packet"]
    packet["requests"][0]["review_items"].pop()

    with pytest.raises(
        DellReportEvidenceAdmissionError,
        match="dell_report_admission_request_item_count_invalid",
    ):
        _validate_population(local_inputs, payloads)


def test_synchronized_nonhuman_delete_still_fails_exact_inventory(
    local_inputs: dict,
) -> None:
    payloads = deepcopy(local_inputs["payloads"])
    public_summary = payloads["current_readiness_public"][
        "candidate_review_packet_summary"
    ]
    packet = payloads["current_readiness_private"]["candidate_review_packet"]
    request = next(
        row
        for row in packet["requests"]
        if row["request_id"] == "REQ::fb06661b946711fc3b334146"
    )
    deleted = request["review_items"].pop(0)
    assert deleted["human_review_required"] is False
    request["review_item_count"] = 2
    for issue_class in deleted["issue_classes"]:
        request["issue_class_counts"][issue_class] -= 1
        if request["issue_class_counts"][issue_class] == 0:
            del request["issue_class_counts"][issue_class]
        packet["issue_class_counts"][issue_class] -= 1
        if packet["issue_class_counts"][issue_class] == 0:
            del packet["issue_class_counts"][issue_class]
    packet["review_item_count"] = 17
    _redigest(request, "request_review_digest")
    _redigest(packet, "review_packet_digest")
    public_summary["review_item_count"] = 17
    public_summary["issue_class_counts"] = deepcopy(packet["issue_class_counts"])
    public_summary["review_packet_digest"] = packet["review_packet_digest"]

    with pytest.raises(
        DellReportEvidenceAdmissionError,
        match="dell_report_admission_request_item_set_drift",
    ):
        _validate_population(local_inputs, payloads)


def test_synchronized_nonhuman_identity_mutation_fails_exact_inventory(
    local_inputs: dict,
) -> None:
    payloads = deepcopy(local_inputs["payloads"])
    packet = payloads["current_readiness_private"]["candidate_review_packet"]
    request = next(
        row
        for row in packet["requests"]
        if row["request_id"] == "REQ::fb06661b946711fc3b334146"
    )
    item = request["review_items"][0]
    assert item["human_review_required"] is False
    item["review_item_ref"] = "CANDOBJ::MUTATED_NONHUMAN"
    _redigest(item, "review_item_digest")
    _redigest(request, "request_review_digest")
    _redigest(packet, "review_packet_digest")

    with pytest.raises(
        DellReportEvidenceAdmissionError,
        match="dell_report_admission_request_item_set_drift",
    ):
        _validate_population(local_inputs, payloads)


def test_ninth_zero_human_request_fails_exact_request_set(
    local_inputs: dict,
) -> None:
    payloads = deepcopy(local_inputs["payloads"])
    public_request = deepcopy(payloads["current_readiness_public"]["requests"][0])
    private_readiness_request = deepcopy(
        payloads["current_readiness_private"]["pack_readiness"]["requests"][0]
    )
    packet = payloads["current_readiness_private"]["candidate_review_packet"]
    packet_request = deepcopy(packet["requests"][0])
    new_id = "REQ::NINTH_ZERO_HUMAN"
    public_request["request_id"] = new_id
    private_readiness_request["request_id"] = new_id
    packet_request["request_id"] = new_id
    packet_request["review_items"] = []
    packet_request["review_item_count"] = 0
    packet_request["human_review_required_count"] = 0
    packet_request["issue_class_counts"] = {}
    _redigest(packet_request, "request_review_digest")
    payloads["current_readiness_public"]["requests"].append(public_request)
    payloads["current_readiness_private"]["pack_readiness"]["requests"].append(
        private_readiness_request
    )
    packet["requests"].append(packet_request)
    packet["request_count"] = 9
    _redigest(packet, "review_packet_digest")
    payloads["current_readiness_public"]["candidate_review_packet_summary"][
        "review_packet_digest"
    ] = packet["review_packet_digest"]

    with pytest.raises(
        DellReportEvidenceAdmissionError,
        match="dell_report_admission_request_sets_differ",
    ):
        _validate_population(local_inputs, payloads)


def test_policy_item_digest_and_claim_semantics_fail_closed(
    local_inputs: dict,
) -> None:
    bad_digest = deepcopy(local_inputs["program"])
    bad_digest["item_claim_use_policies"][0]["review_item_digest"] = "f" * 64
    _redigest(bad_digest, "program_digest")
    with pytest.raises(
        DellReportEvidenceAdmissionError,
        match="dell_report_admission_policy_item_identity_not_frozen",
    ):
        _compile(local_inputs, program=bad_digest)

    bad_claim = deepcopy(local_inputs["program"])
    bad_claim["item_claim_use_policies"][0]["report_claim_refs"] = [
        "WPCLAIM::DOES_NOT_EXIST"
    ]
    _redigest(bad_claim, "program_digest")
    with pytest.raises(
        DellReportEvidenceAdmissionError,
        match="dell_report_admission_policy_semantics_drift",
    ):
        _compile(local_inputs, program=bad_claim)


@pytest.mark.parametrize(
    ("review_item_ref", "wrong_claim_ref"),
    [
        (
            "CANDOBJ::E56F86F06307372B2F18FA97",
            "WPCLAIM::1075BD357D0BD279E58F",
        ),
        (
            "CANDOBJ::51BFECDF1794E6CE42A7B2CE",
            "WPCLAIM::0E1B77AE079F812F2C65",
        ),
        (
            "CANDOBJ::C20F9F784D691747A36DADC3",
            "WPCLAIM::75D965BE6E71E9B90737",
        ),
        (
            "CANDOBJ::8EDA130D7FDA0F0B66BA53B5",
            "WPCLAIM::2ED97A04C2264BA689D4",
        ),
        (
            "CANDOBJ::9A29D551F01388C5C785FF82",
            "WPCLAIM::05DBE34A9E501DA6588A",
        ),
        (
            "CANDOBJ::D7769F8FD29DE6807D0B57F6",
            "WPCLAIM::62D1CEB2B807786057DB",
        ),
        (
            "CANDOBJ::C250AD7345231BD7C1DF0CBB",
            "WPCLAIM::8B09D8AAC24EE52BD74B",
        ),
    ],
)
def test_period_basis_and_cross_company_claim_padding_is_frozen_out(
    local_inputs: dict,
    review_item_ref: str,
    wrong_claim_ref: str,
) -> None:
    program = deepcopy(local_inputs["program"])
    policy = next(
        row
        for row in program["item_claim_use_policies"]
        if row["review_item_ref"] == review_item_ref
    )
    policy["report_claim_refs"] = [wrong_claim_ref]
    policy["report_surface_paths"] = ["trusted_report.confidence"]
    _redigest(program, "program_digest")

    with pytest.raises(
        DellReportEvidenceAdmissionError,
        match="dell_report_admission_policy_semantics_drift",
    ):
        _compile(local_inputs, program=program)


def test_reject_and_duplicate_recommendations_have_no_claim_or_citation_surface(
    local_inputs: dict,
) -> None:
    items = {
        item["review_item_ref"]: item
        for request in _compile(local_inputs)["private"]["requests"]
        for item in request["items"]
    }
    financing = items["CANDOBJ::E56F86F06307372B2F18FA97"][
        "report_claim_use"
    ]
    duplicate = items["CANDOBJ::040A820BE15FD0CEAF83C0AD"][
        "report_claim_use"
    ]
    counter = items["CANDOBJ::0B13DC6BFDAF674340B451BC"][
        "report_claim_use"
    ]

    assert financing["review_recommendation"] == (
        "recommend_reject_no_current_material_report_use"
    )
    assert financing["report_claim_refs"] == []
    assert financing["report_surface_paths"] == []
    assert duplicate["review_recommendation"] == (
        "recommend_rebind_duplicate_to_canonical_candidate"
    )
    assert duplicate["duplicate_of_review_item_ref"] == (
        "CANDOBJ::0B13DC6BFDAF674340B451BC"
    )
    assert duplicate["report_claim_refs"] == []
    assert counter["report_claim_refs"] == [
        "WPCLAIM::B1BDD811CE1DF55EE55E",
        "WPCLAIM::E3BFD59CC60F05B1BD7C",
        "WPCLAIM::FC2C8B1EA97D7EF82311",
    ]


def test_resigned_input_binding_or_failure_lineage_drift_is_rejected(
    local_inputs: dict,
) -> None:
    bad_binding = deepcopy(local_inputs["program"])
    bad_binding["input_bindings"]["R1_failed_audit"]["sha256"] = "f" * 64
    _redigest(bad_binding, "program_digest")
    with pytest.raises(
        DellReportEvidenceAdmissionError,
        match="dell_report_admission_input_binding_contract_drift",
    ):
        validate_dell_report_evidence_admission_program(bad_binding)

    bad_lineage = deepcopy(local_inputs["program"])
    bad_lineage["successor_lineage"]["predecessor_verdict"] = "PASS"
    _redigest(bad_lineage, "program_digest")
    with pytest.raises(
        DellReportEvidenceAdmissionError,
        match="dell_report_admission_successor_lineage_drift",
    ):
        validate_dell_report_evidence_admission_program(bad_lineage)


def test_input_sha_drift_fails_before_packet_use(local_inputs: dict) -> None:
    sha256_by_ref = deepcopy(local_inputs["sha256_by_ref"])
    ref = local_inputs["program"]["input_bindings"]["current_readiness_private"][
        "ref"
    ]
    sha256_by_ref[ref] = "0" * 64

    with pytest.raises(
        DellReportEvidenceAdmissionError,
        match="dell_report_admission_input_sha256_mismatch:current_readiness_private",
    ):
        _compile(local_inputs, input_sha256_by_ref=sha256_by_ref)


def test_materializer_builds_self_bound_zero_call_outputs(local_inputs: dict) -> None:
    compiled = RUNNER.compile_materialization(
        program_path=PROGRAM_PATH,
        private_output_path=ROOT / RUNNER.DEFAULT_PRIVATE_OUTPUT,
        recorded_at="2026-08-25T16:00:00+08:00",
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
    assert len(public["private_full_result_sha256"]) == 64
    assert public["execution"]["network_calls"] == 0
    assert public["execution"]["model_calls"] == 0
    assert public["execution"]["embedding_calls"] == 0
    assert public["execution"]["reranker_calls"] == 0


def test_materializer_rejects_dirty_worktree_and_output_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(
        RUNNER.DellReportEvidenceAdmissionMaterializationError,
        match="dell_report_admission_clean_worktree_required",
    ):
        RUNNER._require_clean_worktree("?? unexpected.txt")

    monkeypatch.setattr(RUNNER, "ROOT", tmp_path)
    existing = tmp_path / "already.json"
    existing.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        FileExistsError,
        match="dell_report_admission_output_exists:already.json",
    ):
        RUNNER._write_new(existing, {"value": 1})
