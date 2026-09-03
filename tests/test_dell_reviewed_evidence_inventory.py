from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from sec_agent.agent_runtime.dell_agentic_contracts import canonical_digest
from sec_agent.agent_runtime import dell_reviewed_evidence_inventory as inventory
from sec_agent.research_foundation.contracts import (
    bind_dell_research_method,
    load_dell_reference_vertical_foundation,
)
from sec_agent.research_foundation.data_ports import (
    CurrentReviewedEvidenceReader,
    reviewed_evidence_id,
)


REAL_INPUTS_AVAILABLE = all(
    path.is_file()
    for path in (
        inventory.DEFAULT_CONFIG_PATH,
        inventory.DEFAULT_BASE_PACK_PATH,
        inventory.DEFAULT_OVERLAY_PATH,
        inventory.DEFAULT_PHYSICAL_CATALOG_PATH,
    )
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_resigned_config(tmp_path: Path, mutate) -> tuple[Path, str, str]:
    payload = _load_json(inventory.DEFAULT_CONFIG_PATH)
    mutate(payload)
    payload.pop("enrichment_digest", None)
    enrichment_digest = canonical_digest(payload)
    payload["enrichment_digest"] = enrichment_digest
    path = tmp_path / "reviewed-enrichment.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    config_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, config_sha256, enrichment_digest


def _load_trusted_resigned_config(
    config_path: Path,
    config_sha256: str,
    enrichment_digest: str,
):
    return inventory.load_reviewed_evidence_enrichment_candidate(
        config_path=config_path,
        expected_config_sha256=config_sha256,
        expected_enrichment_digest=enrichment_digest,
    )


def test_checked_in_candidate_is_self_signed_and_digest_keyed() -> None:
    payload = _load_json(inventory.DEFAULT_CONFIG_PATH)
    claimed = payload.pop("enrichment_digest")

    assert claimed == inventory.DEFAULT_EXPECTED_ENRICHMENT_DIGEST
    assert claimed == "365a65744a58d03092dd16aedffcc0e78df9a20a8ed63c546529afa1a04e78e3"
    assert canonical_digest(payload) == claimed
    assert hashlib.sha256(inventory.DEFAULT_CONFIG_PATH.read_bytes()).hexdigest() == (
        inventory.DEFAULT_EXPECTED_CONFIG_SHA256
    )
    assert len(payload["item_enrichments"]) == 61
    assert all(
        len(digest) == 64
        and set(digest).issubset(set("0123456789abcdef"))
        for digest in payload["item_enrichments"]
    )


def test_checked_in_candidate_contains_no_answer_payload_fields() -> None:
    payload = _load_json(inventory.DEFAULT_CONFIG_PATH)
    prohibited_keys = {
        "claim_text",
        "source_text",
        "reviewed_source_excerpt",
        "query",
        "expected_answer",
        "numeric_value",
    }

    def walk(value) -> None:
        if isinstance(value, dict):
            assert prohibited_keys.isdisjoint(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)


@pytest.mark.skipif(not REAL_INPUTS_AVAILABLE, reason="exact Dell 55+6 inputs unavailable")
class TestRealReviewedEvidenceEnrichment:
    def test_real_55_plus_6_projection_and_authority_boundary(self) -> None:
        projection = inventory.load_reviewed_evidence_enrichment_candidate()

        assert len(projection.rows) == projection.item_count == 61
        assert projection.mechanical_mapping_count == 43
        assert projection.f12_rule_candidate_count == 13
        assert projection.item_level_ambiguity_count == 5
        assert projection.answer_free is True
        assert projection.owner_review_required is True
        assert projection.execution_authority is False
        assert projection.executable_reviewed_evidence_index_authorized is False
        assert projection.base_pack_payload_digest == (
            "1654b68f3621d613768ba2a7d701ceda712a096ffeb5ab9e9b9078b3189e2a98"
        )
        assert projection.overlay_projection_digest == (
            "ecee0e2f0d3d602b10093f67861100504e5ba264b47d5d2019e23bd82fa1aff5"
        )
        assert projection.composite_identity_digest == (
            "188f0eda28a025d6ae13cf9327187d9edf2fc1a83d4920cc3af20ce6646e12a6"
        )
        assert projection.legacy_active_projection_digest == (
            "c91d5c588f2ed2142c0bb7f079614f758cb8a92fc9149126d418cdbbafa87e7d"
        )
        assert projection.entity_domain_conflict_count == 1

    def test_real_classification_and_family_distribution(self) -> None:
        projection = inventory.load_reviewed_evidence_enrichment_candidate()

        assert Counter(row.provenance_mapping_state for row in projection.rows) == {
            "mechanical_metadata_mapping": 43,
            "f12_independent_source_rule_candidate_owner_review_required": 13,
            "item_level_family_ambiguity_owner_review_required": 5,
        }
        assert Counter(row.source_family_ref for row in projection.rows) == {
            "F1_SEC_ISSUER_FACTS": 10,
            "F2_DELL_IR_EARNINGS": 14,
            "F3_DELL_PRODUCT_SUPPORT": 2,
            "F4_CUSTOMER_CAPEX_DEPLOYMENT": 1,
            "F5_PUBLIC_PROCUREMENT": 2,
            "F6_COMPUTE_PLATFORM_SUPPLIERS": 9,
            "F7_MEMORY_FOUNDRY_NETWORK_STORAGE": 5,
            "F12_INDEPENDENT_COUNTEREVIDENCE": 13,
            None: 5,
        }

    def test_ambiguity_rows_remain_unresolved(self) -> None:
        projection = inventory.load_reviewed_evidence_enrichment_candidate()
        rows = {
            row.evidence_item_digest: row
            for row in projection.rows
            if row.provenance_mapping_state
            == "item_level_family_ambiguity_owner_review_required"
        }

        assert set(rows) == {
            "3b054965c17526b1a94c279f7502344468179b740134041829d36d7eae4f5299",
            "80363b20916fa87a2ce1a4445797d70cd3ef478a604c700edc4c48cd7d65aa9f",
            "35cac7ce4798806923fb460db40089602b0489efb832cb4f35e9b5be27f4188a",
            "b9e41b6799ac41ee3440bdfe2124e27f8e4092b6398b10d894c61a9c8e854d21",
            "d0b73d9640d6d9f267d3c8eb8475a14b431f5de32933dce1d2b0bf5dac6d6473",
        }
        assert all(row.source_family_ref is None for row in rows.values())
        assert all(row.route_relation == "unresolved" for row in rows.values())
        assert all(
            not row.proposed_minimum_route_eligible_branch_ids
            for row in rows.values()
        )
        assert all(row.authority_tier_candidate is None for row in rows.values())

    def test_topic_selector_and_minimum_route_are_not_conflated(self) -> None:
        projection = inventory.load_reviewed_evidence_enrichment_candidate()
        rows = {row.evidence_item_digest: row for row in projection.rows}

        broad_dell_release = rows[
            "2dcdc6d95ba36cf5f19b9f2ead9424e081fd187b75db14211e57369a643a155b"
        ]
        assert "Q9_COUNTEREVIDENCE_WWC" in broad_dell_release.coverage_obligation_ids
        assert broad_dell_release.proposed_minimum_route_eligible_branch_ids == (
            "Q1_ISSUER_TRUTH",
            "Q2_DEMAND_QUALITY",
            "Q3_UNITS_ASP_PVM",
            "Q5_SUPPLY_AND_PRICE",
        )

        supplemental_filing = rows[
            "33c0f9af6b184fc3e02d9ce60ea5a4c5ad389f91b2631a4a5b5bab233ccea5b6"
        ]
        assert supplemental_filing.source_family_ref == "F1_SEC_ISSUER_FACTS"
        assert supplemental_filing.coverage_obligation_ids == (
            "Q2_DEMAND_QUALITY",
            "Q3_UNITS_ASP_PVM",
            "Q6_MODEL_COMPUTE_DEMAND",
        )
        assert supplemental_filing.route_relation == "supplemental_only"
        assert not supplemental_filing.proposed_minimum_route_eligible_branch_ids

    def test_f12_rule_candidate_is_not_blanket_q9_coverage(self) -> None:
        projection = inventory.load_reviewed_evidence_enrichment_candidate()
        f12 = [
            row
            for row in projection.rows
            if row.provenance_mapping_state
            == "f12_independent_source_rule_candidate_owner_review_required"
        ]

        assert Counter(row.route_relation for row in f12) == {
            "minimum_route_eligible": 3,
            "supplemental_only": 10,
        }
        assert {
            row.evidence_item_digest
            for row in f12
            if row.route_relation == "minimum_route_eligible"
        } == {
            "df8403b5692d28dfcdb7eb90e37b2831ac7848f40cd66accaece671569856e85",
            "c7b7425c2fa43dd832a18d7d3ffc842500dc3b85b03c61599acd103d17ef35b5",
            "d7c8de3c524043378a879e3a71f11d0e638d6adeacc607bf508112be2aec4cc4",
        }
        assert all(
            row.proposed_minimum_route_eligible_branch_ids
            == ("Q9_COUNTEREVIDENCE_WWC",)
            for row in f12
            if row.route_relation == "minimum_route_eligible"
        )

    def test_projection_preserves_owner_subject_and_authority_metadata(self) -> None:
        projection = inventory.load_reviewed_evidence_enrichment_candidate()
        rows = {row.evidence_item_digest: row for row in projection.rows}
        supplier = rows[
            "9b05477354785b107d379ae69551304da3d09bcd5ceb56979d4fe621589a26a5"
        ]

        assert supplier.evidence_owner_id == "NVDA"
        assert supplier.canonical_evidence_owner_id == "NVIDIA"
        assert supplier.research_subject_ids == ("DELL",)
        assert {"DELL", "NVDA", "NVIDIA", "Nvidia"}.issubset(
            supplier.entity_ids
        )
        assert supplier.entity_resolution_state == "resolved_alias_and_domain"
        assert supplier.disposition == "accepted_bounded_context_evidence"
        assert supplier.causal_attribution_authorized is False
        assert supplier.writer_citable is True
        assert supplier.authority_scope_refs == ("platform_and_supplier_state",)
        assert supplier.source_evidence_role == "counterparty_or_ecosystem_readthrough"

    def test_canonical_selectors_use_reviewed_catalog_aliases(self) -> None:
        projection = inventory.load_reviewed_evidence_enrichment_candidate()

        for canonical_selector, raw_owner in {
            "NVIDIA": "NVDA",
            "MICROSOFT": "MSFT",
            "MICRON": "MU",
            "TSMC": "TSM",
        }.items():
            assert any(
                canonical_selector in row.entity_ids
                and row.evidence_owner_id == raw_owner
                for row in projection.rows
            )

    def test_micron_sec_domain_conflict_remains_explicitly_unresolved(self) -> None:
        projection = inventory.load_reviewed_evidence_enrichment_candidate()
        micron = next(
            row
            for row in projection.rows
            if row.evidence_item_digest
            == "30a99d1a9de9a6dd7b30e20c2223e6e73d0c75096d039b2e5e8fba6e1972c261"
        )

        assert micron.evidence_owner_id == "MU"
        assert micron.canonical_evidence_owner_id == "MICRON"
        assert micron.source_domain == "www.sec.gov"
        assert "www.sec.gov" not in micron.canonical_domain_refs
        assert micron.entity_resolution_state == (
            "unresolved_alias_domain_conflict_owner_review_required"
        )
        assert projection.execution_authority is False

    def test_projection_is_deterministic_and_rows_are_content_free(self) -> None:
        first = inventory.load_reviewed_evidence_enrichment_candidate()
        second = inventory.load_reviewed_evidence_enrichment_candidate()

        assert first.projection_digest == second.projection_digest
        prohibited = {
            "claim_text",
            "source_text",
            "reviewed_source_excerpt",
            "query",
            "expected_answer",
            "numeric_value",
        }
        assert all(
            prohibited.isdisjoint(row.model_dump(mode="python"))
            for row in first.rows
        )

    def test_owner_decision_projects_56_executable_and_5_audit_only_rows(self) -> None:
        projection = inventory.load_reviewed_evidence_enrichment_candidate()
        index = inventory.load_executable_reviewed_evidence_index_v1_2()
        excluded = {
            row.evidence_item_digest
            for row in projection.rows
            if row.provenance_mapping_state
            == "item_level_family_ambiguity_owner_review_required"
        }

        assert projection.item_count == 61
        assert index.indexed_item_count == 56
        assert excluded.isdisjoint(row.item_digest for row in index.rows)
        assert all(row.metadata_state == "complete" for row in index.rows)
        serialized = json.dumps(index.model_dump(mode="json"))
        assert "D:/" not in serialized
        assert "Z:/" not in serialized

    def test_owner_composite_reader_includes_overlay_and_excludes_ambiguity(self) -> None:
        projection = inventory.load_reviewed_evidence_enrichment_candidate()
        excluded = {
            row.evidence_item_digest
            for row in projection.rows
            if row.provenance_mapping_state
            == "item_level_family_ambiguity_owner_review_required"
        }
        case = inventory.load_owner_approved_reviewed_case()
        index = inventory.load_executable_reviewed_evidence_index_v1_2()
        overlay = _load_json(inventory.DEFAULT_OVERLAY_PATH)
        overlay_digests = {
            row["evidence_item_digest"] for row in overlay["evidence_items"]
        }
        case_by_digest = {
            row["evidence_item_digest"]: row for row in case["evidence_items"]
        }
        assert case["item_count"] == 56
        assert overlay_digests.issubset(case_by_digest)
        assert case["projection_digest"] == index.source_pack_digest
        assert {
            reviewed_evidence_id(
                case_key="DELL",
                target_id=row["target_id"],
                evidence_item_digest=row["evidence_item_digest"],
            )
            for row in case["evidence_items"]
        } == {row.evidence_id for row in index.rows}

        scope = bind_dell_research_method(
            load_dell_reference_vertical_foundation(),
            ("Q1_ISSUER_TRUTH",),
            research_as_of=datetime(2026, 9, 2, tzinfo=timezone.utc),
            data_snapshot_id="owner-data-gate-composite-test",
            execution_attempt_id="owner-data-gate-composite-test-a01",
        ).run_scope
        reader = CurrentReviewedEvidenceReader(case_reader=lambda _key: case)
        overlay_ids = tuple(
            row.evidence_id
            for row in index.rows
            if row.item_digest in overlay_digests
        )
        read = reader(
            evidence_ids=overlay_ids,
            branch_id="Q1_ISSUER_TRUTH",
            run_scope=scope,
        )
        assert len(read.evidence) == 6
        assert not read.missing_evidence_ids
        assert read.source_pack_projection_digest == index.source_pack_digest

        ambiguous = next(
            row
            for row in projection.rows
            if row.evidence_item_digest in excluded
        )
        ambiguous_id = reviewed_evidence_id(
            case_key="DELL",
            target_id=ambiguous.target_id,
            evidence_item_digest=ambiguous.evidence_item_digest,
        )
        missing = reader(
            evidence_ids=(ambiguous_id,),
            branch_id="Q1_ISSUER_TRUTH",
            run_scope=scope,
        )
        assert missing.missing_evidence_ids == (ambiguous_id,)
        assert not missing.evidence

    def test_base_pack_byte_change_fails_before_projection(self, tmp_path: Path) -> None:
        changed = tmp_path / "pack.json"
        changed.write_bytes(inventory.DEFAULT_BASE_PACK_PATH.read_bytes() + b"\n")

        with pytest.raises(
            inventory.ReviewedEvidenceEnrichmentError,
            match="base_pack_sha256_mismatch",
        ):
            inventory.load_reviewed_evidence_enrichment_candidate(
                base_pack_path=changed
            )


def test_resigned_config_cannot_self_grant_execution_authority(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["authority"]["execution_authority"] = True

    config_path, config_sha256, enrichment_digest = _write_resigned_config(
        tmp_path, mutate
    )
    with pytest.raises(
        inventory.ReviewedEvidenceEnrichmentError,
        match="reviewed_enrichment_authority_invalid",
    ):
        _load_trusted_resigned_config(
            config_path, config_sha256, enrichment_digest
        )


def test_resigned_config_is_not_trusted_without_external_anchors(tmp_path: Path) -> None:
    config_path, _, _ = _write_resigned_config(
        tmp_path,
        lambda payload: payload.update({"recorded_at": "2026-09-03T12:00:00+08:00"}),
    )

    with pytest.raises(
        inventory.ReviewedEvidenceEnrichmentError,
        match="reviewed_enrichment_config_sha256_mismatch",
    ):
        inventory.load_reviewed_evidence_enrichment_candidate(config_path=config_path)


def test_resigned_config_rejects_recursive_answer_like_field(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        first = next(iter(payload["item_enrichments"].values()))
        first["claim_text"] = "forbidden"

    config_path, config_sha256, enrichment_digest = _write_resigned_config(
        tmp_path, mutate
    )
    with pytest.raises(
        inventory.ReviewedEvidenceEnrichmentError,
        match="answer_like_field_forbidden",
    ):
        _load_trusted_resigned_config(
            config_path, config_sha256, enrichment_digest
        )


def test_resigned_config_rejects_recursive_unknown_field(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        first = next(iter(payload["item_enrichments"].values()))
        first["audit_note"] = "extra fields are not part of the candidate schema"

    trusted = _write_resigned_config(tmp_path, mutate)
    with pytest.raises(
        inventory.ReviewedEvidenceEnrichmentError,
        match="reviewed_enrichment_entry_shape_invalid",
    ):
        _load_trusted_resigned_config(*trusted)


@pytest.mark.skipif(not REAL_INPUTS_AVAILABLE, reason="exact Dell 55+6 inputs unavailable")
def test_resigned_config_rejects_forged_fy2099_period(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["item_enrichments"][
            "024224e83105ed3cd13e5b4a1e6b68a39c541c044b1f4d2875c7d146ea34f721"
        ]["period_refs"] = ["FY2099"]

    trusted = _write_resigned_config(tmp_path, mutate)
    with pytest.raises(
        inventory.ReviewedEvidenceEnrichmentError,
        match="reviewed_enrichment_period_refs_mismatch",
    ):
        _load_trusted_resigned_config(*trusted)


def test_resigned_config_rejects_f12_primary_tier(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["item_enrichments"][
            "df8403b5692d28dfcdb7eb90e37b2831ac7848f40cd66accaece671569856e85"
        ]["authority_tier_candidate"] = "primary"

    trusted = _write_resigned_config(tmp_path, mutate)
    with pytest.raises(
        inventory.ReviewedEvidenceEnrichmentError,
        match="reviewed_enrichment_resolved_candidate_invalid",
    ):
        _load_trusted_resigned_config(*trusted)


@pytest.mark.skipif(not REAL_INPUTS_AVAILABLE, reason="exact Dell 55+6 inputs unavailable")
def test_resigned_config_rejects_zeroed_composite_binding(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["input_bindings"]["composite"]["composite_digest"] = "0" * 64

    trusted = _write_resigned_config(tmp_path, mutate)
    with pytest.raises(
        inventory.ReviewedEvidenceEnrichmentError,
        match="reviewed_enrichment_composite_digest_mismatch",
    ):
        _load_trusted_resigned_config(*trusted)


@pytest.mark.skipif(not REAL_INPUTS_AVAILABLE, reason="exact Dell 55+6 inputs unavailable")
def test_resigned_config_rejects_mechanical_family_class_swap(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        first = payload["item_enrichments"][
            "3610185a120188dcb02376a61871fff20281aa80da84339ea5e76da6c4f57310"
        ]
        second = payload["item_enrichments"][
            "1c73d00cf86b8dc40ce60e6f7dec980cca729fa7bf4de543b0a23094732bd54f"
        ]
        for field in (
            "source_family_ref",
            "candidate_source_family_refs",
            "authority_scope_refs",
        ):
            first[field], second[field] = second[field], first[field]

    trusted = _write_resigned_config(tmp_path, mutate)
    with pytest.raises(
        inventory.ReviewedEvidenceEnrichmentError,
        match="reviewed_enrichment_mechanical_family_mismatch",
    ):
        _load_trusted_resigned_config(*trusted)


@pytest.mark.skipif(not REAL_INPUTS_AVAILABLE, reason="exact Dell 55+6 inputs unavailable")
def test_resigned_config_rejects_unbound_domain_exception(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["classification_contract"]["owner_review_domain_conflicts"][0][
            "observed_domain"
        ] = "example.invalid"

    trusted = _write_resigned_config(tmp_path, mutate)
    with pytest.raises(
        inventory.ReviewedEvidenceEnrichmentError,
        match="reviewed_enrichment_domain_conflict_binding_mismatch",
    ):
        _load_trusted_resigned_config(*trusted)


def test_metadata_projector_has_no_content_field_access() -> None:
    source = inspect.getsource(inventory._safe_live_metadata)

    assert '"source_text"' not in source
    assert '"reviewed_source_excerpt"' not in source
    assert '"claim_text"' not in source
    assert '"query"' not in source
