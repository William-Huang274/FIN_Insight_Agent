from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from retrieval.dell_report_property_oracle_r14 import (
    build_author_property_manifest_r14,
    build_author_property_receipt_r14,
    validate_author_property_manifest_r14,
    validate_author_property_receipt_r14,
)
from retrieval.dell_report_r14_common import (
    DellReportR14ContractError,
    with_result_digest,
)
from retrieval.dell_report_r14_contracts import (
    TARGET_IDS,
    load_and_validate_r14_contracts,
)


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_r14_requirement_manifest_v1_0.json"
)


@pytest.fixture(scope="module")
def requirement() -> dict:
    return json.loads(REQUIREMENT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bundle():
    return load_and_validate_r14_contracts(root=ROOT)


def test_r14_author_property_manifest_covers_all_frozen_positive_controls(
    requirement,
) -> None:
    manifest = build_author_property_manifest_r14(
        requirement_manifest=requirement,
        author_seed="R14-AUTHOR-PROPERTY-SEED-20260829",
    )
    positive_ids = {
        row["control_id"]
        for row in manifest["case_rows"]
        if row["positive_control"]
    }

    assert positive_ids == set(requirement["positive_controls"])
    assert manifest["positive_control_count"] == len(
        requirement["positive_controls"]
    )
    assert manifest["case_count"] > manifest["positive_control_count"]


def test_r14_property_manifest_has_positive_and_negative_controls_for_all_six_targets(
    requirement,
) -> None:
    manifest = build_author_property_manifest_r14(
        requirement_manifest=requirement,
        author_seed="R14-AUTHOR-PROPERTY-SEED-20260829",
    )
    positive_targets = {
        row["target_id"] for row in manifest["case_rows"] if row["positive_control"]
    }
    negative_targets = {
        row["target_id"]
        for row in manifest["case_rows"]
        if not row["positive_control"] and row["expected_outcome"] == "P"
    }

    assert positive_targets == set(TARGET_IDS)
    assert negative_targets == set(TARGET_IDS)


def test_r14_author_property_suite_asserts_classification_and_topology(
    requirement, bundle
) -> None:
    manifest = build_author_property_manifest_r14(
        requirement_manifest=requirement,
        author_seed="R14-AUTHOR-PROPERTY-SEED-20260829",
    )
    receipt = build_author_property_receipt_r14(
        manifest=manifest,
        requirement_manifest=requirement,
        bundle=bundle,
        implementation_commit="1" * 40,
        implementation_tree="2" * 40,
    )

    assert receipt["status"] == "PASS"
    assert receipt["failed_count"] == 0
    assert all(row["classification_pass"] for row in receipt["result_rows"])
    assert all(row["topology_pass"] for row in receipt["result_rows"])
    assert not receipt["minimal_counterexample_digests"]


def test_r14_property_denominator_or_result_cannot_be_resigned(
    requirement, bundle
) -> None:
    manifest = build_author_property_manifest_r14(
        requirement_manifest=requirement,
        author_seed="R14-AUTHOR-PROPERTY-SEED-20260829",
    )
    dropped = deepcopy(manifest)
    dropped["case_rows"] = dropped["case_rows"][:-1]
    dropped["case_count"] -= 1
    dropped = with_result_digest(dropped)
    with pytest.raises(
        DellReportR14ContractError, match="R14_property_manifest_denominator_invalid"
    ):
        validate_author_property_manifest_r14(
            dropped, requirement_manifest=requirement
        )

    receipt = build_author_property_receipt_r14(
        manifest=manifest,
        requirement_manifest=requirement,
        bundle=bundle,
        implementation_commit="1" * 40,
        implementation_tree="2" * 40,
    )
    forged = deepcopy(receipt)
    forged["result_rows"][0]["passed"] = False
    forged = with_result_digest(forged)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_property_receipt_row_digest_invalid",
    ):
        validate_author_property_receipt_r14(forged, manifest=manifest)


def test_r14_property_manifest_and_receipt_reject_resigned_semantic_changes(
    requirement, bundle
) -> None:
    manifest = build_author_property_manifest_r14(
        requirement_manifest=requirement,
        author_seed="R14-AUTHOR-PROPERTY-SEED-20260829",
    )
    forged_manifest = deepcopy(manifest)
    forged_manifest["case_rows"][0]["expected_outcome"] = "N"
    row_body = dict(forged_manifest["case_rows"][0])
    row_body.pop("row_digest")
    forged_manifest["case_rows"][0]["row_digest"] = with_result_digest(
        row_body
    )["result_digest"]
    forged_manifest = with_result_digest(forged_manifest)
    with pytest.raises(
        DellReportR14ContractError, match="R14_property_manifest_denominator_invalid"
    ):
        validate_author_property_manifest_r14(
            forged_manifest, requirement_manifest=requirement
        )

    receipt = build_author_property_receipt_r14(
        manifest=manifest,
        requirement_manifest=requirement,
        bundle=bundle,
        implementation_commit="1" * 40,
        implementation_tree="2" * 40,
    )
    forged_receipt = deepcopy(receipt)
    forged_receipt["result_rows"][0]["passed"] = False
    forged_receipt["result_rows"][0]["classification_pass"] = False
    row_body = dict(forged_receipt["result_rows"][0])
    row_body.pop("row_digest")
    forged_receipt["result_rows"][0]["row_digest"] = with_result_digest(
        row_body
    )["result_digest"]
    forged_receipt["failed_count"] = 1
    forged_receipt["passed_count"] -= 1
    forged_receipt["status"] = "FAIL"
    forged_receipt = with_result_digest(forged_receipt)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_property_receipt_row_semantics_invalid",
    ):
        validate_author_property_receipt_r14(forged_receipt, manifest=manifest)
