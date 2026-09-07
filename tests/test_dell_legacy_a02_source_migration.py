from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from pydantic import ValidationError
import pytest

from sec_agent.agent_runtime import dell_legacy_a02_source_migration as migration
from sec_agent.agent_runtime.dell_agentic_contracts import (
    ExternalSourceIntent,
    LocalEvidenceIntent,
    ReviewedEvidenceIntent,
)
from sec_agent.agent_runtime.dell_legacy_a02_source_migration import (
    LegacyA02SourceMigrationReceipt,
    migrate_legacy_a02_planner_outcome_bytes,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "dell_a02_planner_parsed_payload.json"
REAL_OUTCOME_PATH = Path(
    r"Z:\FIN_Insight_Agent_qualification\dell_reference_vertical\runtime"
    r"\attempts\20260902-dell-reference-vertical-structured-a02\model-calls"
    r"\planner-f8adf0fc5bf7-5d28981f08f4acc97e3a.outcome.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _receipt() -> LegacyA02SourceMigrationReceipt:
    return migration._migrate_payload(_fixture()["parsed_payload"])


def _leg(receipt: LegacyA02SourceMigrationReceipt, leg_id: str):
    return next(row for row in receipt.intent_legs if row.leg_id == leg_id)


def _selector_projection(legs) -> list[dict]:
    projection = []
    for leg in legs:
        intent = leg.intent
        row = {
            "kind": leg.provider_intent_kind,
            "branch": leg.branch_id,
            "family": leg.semantic_source_family_ref,
            "entities": intent.entity_refs,
            "periods": intent.period_intents,
        }
        if isinstance(intent, ReviewedEvidenceIntent):
            row.update(
                topics=intent.topic_refs,
                evidence_roles=intent.evidence_role_refs,
                minimum_authority=intent.minimum_authority_tier,
            )
        elif isinstance(intent, LocalEvidenceIntent):
            row.update(
                source_roles=intent.source_role_intents,
                surfaces=intent.content_surface_intents,
            )
        else:
            row.update(
                domains=intent.domain_allowlist,
                published_not_before=intent.published_not_before,
                published_not_after=intent.published_not_after,
            )
        projection.append(row)
    return projection


def test_exact_a02_payload_deterministically_projects_17_requests_to_35_legs() -> None:
    first, second = _receipt(), _receipt()

    assert first == second
    assert first.receipt_digest == second.receipt_digest
    assert not hasattr(first, "source_binding_mode")
    assert first.task_count == 9
    assert first.source_request_count == 17
    assert first.fact_request_count == 2
    assert first.provider_intent_leg_count == 35
    assert first.reviewed_leg_count == 17
    assert first.local_leg_count == 17
    assert first.external_leg_count == 1
    assert first.compiler_dispatch_performed is False
    assert first.resume_allowed is first.successor_authorized is False
    assert first.model_calls == first.network_calls == first.provider_calls == 0
    assert all(row.execution_authorized is False for row in first.intent_legs)
    assert sum(
        row.blocking_correction_code == "reviewed_enrichment_required"
        for row in first.intent_legs
    ) == 17
    assert all(
        row.blocking_correction_code is None
        for row in first.intent_legs
        if row.provider_intent_kind != "reviewed_evidence"
    )

    expected_ids = []
    for ordinal in range(1, 16):
        expected_ids.extend(
            [f"A02-E{ordinal:02d}-REVIEWED", f"A02-E{ordinal:02d}-LOCAL"]
        )
    expected_ids.extend(
        [
            "A02-E16-F6-REVIEWED", "A02-E16-F6-LOCAL",
            "A02-E16-F7-REVIEWED", "A02-E16-F7-LOCAL",
            "A02-E17-EXTERNAL",
        ]
    )
    assert [row.leg_id for row in first.intent_legs] == expected_ids


def test_batch_and_typed_branch_audits_recompute_exact_foundation_baseline() -> None:
    audit = _receipt().batch_family_audit

    assert all(isinstance(row, migration._BranchAudit) for row in audit.branch_audits)
    assert audit.required_count == 24
    assert audit.occurrence_count == 18
    assert audit.unique_count == 17
    assert len(audit.missing_keys) == 7
    assert len(audit.duplicate_keys) == 1
    assert len(audit.extra_keys) == 0
    assert audit.missing_keys == (
        "Q1_ISSUER_TRUTH/F1_SEC_ISSUER_FACTS",
        "Q2_DEMAND_QUALITY/F5_PUBLIC_PROCUREMENT",
        "Q3_UNITS_ASP_PVM/F5_PUBLIC_PROCUREMENT",
        "Q4_ARCHITECTURE_RAMP/F4_CUSTOMER_CAPEX_DEPLOYMENT",
        "Q5_SUPPLY_AND_PRICE/F6_COMPUTE_PLATFORM_SUPPLIERS",
        "Q6_MODEL_COMPUTE_DEMAND/F6_COMPUTE_PLATFORM_SUPPLIERS",
        "Q7_EXPORT_CONTROL_CHINA/F6_COMPUTE_PLATFORM_SUPPLIERS",
    )
    assert audit.duplicate_keys == (
        "Q1_ISSUER_TRUTH/F2_DELL_IR_EARNINGS",
    )
    assert audit.extra_keys == ()
    assert audit.complete is False
    assert audit.execution_authorized is False


def test_reviewed_local_independence_and_q8_partition_are_exact() -> None:
    receipt = _receipt()
    request_16_legs = [
        row for row in receipt.intent_legs if row.source_request_ordinal == 16
    ]

    assert [row.provider_intent_kind for row in request_16_legs] == [
        "reviewed_evidence", "local_evidence",
        "reviewed_evidence", "local_evidence",
    ]
    assert [row.semantic_source_family_ref for row in request_16_legs] == [
        "F6_COMPUTE_PLATFORM_SUPPLIERS", "F6_COMPUTE_PLATFORM_SUPPLIERS",
        "F7_MEMORY_FOUNDRY_NETWORK_STORAGE",
        "F7_MEMORY_FOUNDRY_NETWORK_STORAGE",
    ]
    assert request_16_legs[0].intent.entity_refs == ("NVIDIA", "AMD", "INTC")
    assert request_16_legs[1].intent.entity_refs == ("NVIDIA", "AMD", "INTC")
    assert request_16_legs[2].intent.entity_refs == ("MICRON", "TSMC", "AVGO")
    assert request_16_legs[3].intent.entity_refs == ("MICRON", "TSMC", "AVGO")
    assert all(row.intent.entity_refs for row in request_16_legs)
    assert all(
        "multi_family_entity_partition_explicit_not_cartesian"
        in row.migration_notes
        for row in request_16_legs
    )


def test_aliases_are_explicit_only_and_unknown_intc_avgo_are_preserved() -> None:
    receipt = _receipt()

    q4 = _leg(receipt, "A02-E08-LOCAL")
    assert q4.intent.entity_refs == ("NVIDIA", "AMD", "INTC")
    assert "explicit_entity_alias:NVDA->NVIDIA" in q4.migration_notes
    assert "unmapped_entity_alias_preserved:INTC" in q4.migration_notes

    q5 = _leg(receipt, "A02-E09-LOCAL")
    assert q5.intent.entity_refs == ("MICRON", "TSMC", "AVGO", "SK_HYNIX")
    assert "explicit_entity_alias:MU->MICRON" in q5.migration_notes
    assert "explicit_entity_alias:TSM->TSMC" in q5.migration_notes
    assert "unmapped_entity_alias_preserved:AVGO" in q5.migration_notes
    assert "BROADCOM" not in q5.intent.entity_refs


def test_external_leg_has_no_legacy_local_selectors() -> None:
    external = _leg(_receipt(), "A02-E17-EXTERNAL")

    assert isinstance(external.intent, ExternalSourceIntent)
    assert external.intent.semantic_source_family_refs == (
        "F12_INDEPENDENT_COUNTEREVIDENCE",
    )
    assert external.intent.entity_refs == external.intent.period_intents == ()
    assert external.intent.domain_allowlist == ()
    assert external.legacy_capture_limit == 2
    assert (
        "legacy_external_local_selectors_removed:source_roles,retrieval_lanes"
        in external.migration_notes
    )
    dumped = external.intent.model_dump(mode="json")
    assert not {
        "issuer_ids", "fiscal_periods", "source_roles", "route_ids",
        "retrieval_lanes",
    }.intersection(dumped)


def test_query_text_never_changes_selector_projection() -> None:
    request = _fixture()["parsed_payload"]["tasks"][7]["evidence_requests"][1]
    changed = deepcopy(request)
    changed["query"] = "GOOGL F1 export policy words must never alter selectors"

    original_legs = migration._project_request(
        7, "Q8_COMPETITION_VALUE_POOL", 1, 16, request
    )
    changed_legs = migration._project_request(
        7, "Q8_COMPETITION_VALUE_POOL", 1, 16, changed
    )

    assert _selector_projection(original_legs) == _selector_projection(changed_legs)
    assert [row.intent.query for row in original_legs] != [
        row.intent.query for row in changed_legs
    ]
    assert [row.leg_digest for row in original_legs] != [
        row.leg_digest for row in changed_legs
    ]


@pytest.mark.parametrize(
    "override",
    [
        {"task": 6},
        {"branch": "Q7_EXPORT_CONTROL_CHINA"},
        {"index": 0},
        {"ordinal": 15},
    ],
)
def test_private_projector_rejects_wrong_exact_path_binding(override: dict) -> None:
    request = _fixture()["parsed_payload"]["tasks"][7]["evidence_requests"][1]
    kwargs = dict(
        task=7,
        branch="Q8_COMPETITION_VALUE_POOL",
        index=1,
        ordinal=16,
        raw=request,
    )
    kwargs.update(override)
    with pytest.raises(ValueError, match="exact_path_binding_mismatch"):
        migration._project_request(**kwargs)


def test_external_rebinding_and_q8_empty_family_side_are_rejected() -> None:
    payload = _fixture()["parsed_payload"]
    external = payload["tasks"][8]["evidence_requests"][0]
    with pytest.raises(ValueError, match="route_binding_mismatch"):
        migration._project_request(
            7, "Q8_COMPETITION_VALUE_POOL", 1, 16, external
        )

    q8 = deepcopy(payload["tasks"][7]["evidence_requests"][1])
    q8["issuer_ids"] = ["NVDA", "AMD", "INTC"]
    with pytest.raises(ValueError, match="q8_family_entity_partition_empty"):
        migration._project_request(
            7, "Q8_COMPETITION_VALUE_POOL", 1, 16, q8
        )


def test_tampered_full_payload_and_unassigned_q8_entity_are_rejected() -> None:
    payload = _fixture()["parsed_payload"]
    tampered = deepcopy(payload)
    tampered["tasks"][0]["evidence_requests"][0]["route_ids"] = [
        "F1_SEC_ISSUER_FACTS"
    ]
    with pytest.raises(ValueError, match="parsed_payload_not_exact_source"):
        migration._migrate_payload(tampered)

    mixed = deepcopy(payload["tasks"][7]["evidence_requests"][1])
    mixed["issuer_ids"].append("GOOGL")
    with pytest.raises(ValueError, match="multi_family_entity_unassigned"):
        migration._project_request(
            7, "Q8_COMPETITION_VALUE_POOL", 1, 16, mixed
        )


def test_all_receipt_layers_reject_model_copy_tampering_on_revalidation() -> None:
    receipt = _receipt()
    leg = receipt.intent_legs[0]
    q8_leg = _leg(receipt, "A02-E16-F6-REVIEWED")
    external_leg = _leg(receipt, "A02-E17-EXTERNAL")
    branch = receipt.batch_family_audit.branch_audits[0]
    batch = receipt.batch_family_audit

    cases = (
        (
            type(leg),
            leg.model_copy(update={"provider_intent_kind": "external_source"}),
            "leg_cross_kind_mismatch",
        ),
        (
            type(leg),
            leg.model_copy(update={"leg_digest": "0" * 64}),
            "leg_digest_mismatch",
        ),
        (
            type(q8_leg),
            q8_leg.model_copy(
                update={
                    "intent": q8_leg.intent.model_copy(
                        update={"entity_refs": ("MICRON",)}
                    )
                }
            ),
            "q8_entity_family_mismatch",
        ),
        (
            type(external_leg),
            external_leg.model_copy(
                update={
                    "intent": external_leg.intent.model_copy(
                        update={"entity_refs": ("DELL",)}
                    )
                }
            ),
            "external_selector_clearance_mismatch",
        ),
        (
            type(branch),
            branch.model_copy(update={"missing": ()}),
            "branch_audit_derived_mismatch",
        ),
        (
            type(batch),
            batch.model_copy(update={"required_count": 23}),
            "batch_derived_mismatch",
        ),
        (
            LegacyA02SourceMigrationReceipt,
            receipt.model_copy(update={"reviewed_leg_count": 16}),
            "source_receipt_count_mismatch",
        ),
        (
            LegacyA02SourceMigrationReceipt,
            receipt.model_copy(update={"source_artifact_ref": "qualification://wrong"}),
            "source_identity_mismatch",
        ),
    )
    for model_type, tampered, code in cases:
        with pytest.raises(ValidationError, match=code):
            model_type.model_validate(tampered)


def test_json_round_trip_revalidates_every_nested_receipt() -> None:
    receipt = _receipt()
    rebuilt = LegacyA02SourceMigrationReceipt.model_validate(
        receipt.model_dump(mode="json")
    )
    assert rebuilt == receipt
    assert rebuilt.receipt_digest == receipt.receipt_digest


def test_only_raw_outcome_entrypoint_is_public_authority() -> None:
    assert migration.__all__ == (
        "LegacyA02SourceMigrationReceipt",
        "migrate_legacy_a02_planner_outcome_bytes",
    )
    assert "source_binding_mode" not in LegacyA02SourceMigrationReceipt.model_fields


def test_real_immutable_a02_outcome_sha_and_shape_when_available() -> None:
    if not REAL_OUTCOME_PATH.exists():
        pytest.skip("immutable A02 qualification artifact is not mounted")

    raw = REAL_OUTCOME_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == migration.LEGACY_A02_PLANNER_OUTCOME_SHA256

    receipt = migrate_legacy_a02_planner_outcome_bytes(raw)
    assert receipt.provider_intent_leg_count == 35
    assert receipt.batch_family_audit.required_count == 24
    assert receipt.compiler_dispatch_performed is False

    with pytest.raises(ValueError, match="source_artifact_digest_mismatch"):
        migrate_legacy_a02_planner_outcome_bytes(raw + b" ")
