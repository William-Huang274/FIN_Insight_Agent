from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from retrieval.source_use_policy import (
    SourceUsePolicy,
    SourceUsePolicyError,
    evaluate_source_claim_use,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_source_strength_and_claim_use_policy_v1_0.json"
)


def _policy() -> SourceUsePolicy:
    return SourceUsePolicy.from_mapping(
        json.loads(POLICY.read_text(encoding="utf-8"))
    )


def test_primary_issuer_source_can_enter_exact_fact_gate() -> None:
    result = evaluate_source_claim_use(
        policy=_policy(),
        source_class="issuer_regulator_or_government_primary",
        claim_use="target_company_exact_numeric_fact",
        original_capture_bound=True,
        speaker_bound=True,
        subject_bound=True,
    )

    assert result["evidence_promotion_allowed"] is True
    assert result["disposition"] == "admit_as_exact_or_speaker_attributed_candidate"


def test_counterparty_source_cannot_become_target_exact_numeric_fact() -> None:
    result = evaluate_source_claim_use(
        policy=_policy(),
        source_class="named_counterparty_or_standards_primary",
        claim_use="target_company_exact_numeric_fact",
        original_capture_bound=True,
        speaker_bound=True,
        subject_bound=True,
    )

    assert result["evidence_promotion_allowed"] is False
    assert "target_company_exact_numeric_fact_forbidden" in result["blockers"]


def test_trusted_secondary_requires_corroboration_and_stays_contextual() -> None:
    blocked = evaluate_source_claim_use(
        policy=_policy(),
        source_class=(
            "trusted_media_industry_association_or_public_analyst_context"
        ),
        claim_use="bounded_target_context",
        original_capture_bound=True,
        speaker_bound=True,
        subject_bound=True,
        independent_source_count=1,
    )
    admitted = evaluate_source_claim_use(
        policy=_policy(),
        source_class=(
            "trusted_media_industry_association_or_public_analyst_context"
        ),
        claim_use="bounded_target_context",
        original_capture_bound=True,
        speaker_bound=True,
        subject_bound=True,
        independent_source_count=2,
    )

    assert blocked["evidence_promotion_allowed"] is False
    assert "independent_corroboration_below_policy_minimum" in blocked["blockers"]
    assert admitted["disposition"] == "admit_as_bounded_context_candidate"


def test_search_result_is_only_a_locator() -> None:
    result = evaluate_source_claim_use(
        policy=_policy(),
        source_class="search_rss_gdelt_or_common_crawl_discovery",
        claim_use="discovery_locator",
        original_capture_bound=False,
        speaker_bound=False,
        subject_bound=False,
    )

    assert result["evidence_promotion_allowed"] is False
    assert result["disposition"] == (
        "locator_only_fetch_original_before_evidence_gate"
    )


def test_discovery_locator_cannot_silently_gain_analysis_or_citation_rights() -> None:
    result = evaluate_source_claim_use(
        policy=_policy(),
        source_class="search_rss_gdelt_or_common_crawl_discovery",
        claim_use="discovery_locator",
        original_capture_bound=False,
        speaker_bound=False,
        subject_bound=False,
        requested_rights=("internal_analysis", "citation"),
    )

    assert result["evidence_promotion_allowed"] is False
    assert result["rights"] == {
        "discovery": "allowed",
        "internal_analysis": "metadata_and_locator_only",
        "citation": "forbidden",
        "redistribution": "forbidden",
    }
    assert result["blockers"] == [
        "citation_right_forbidden_for_source_class",
        "internal_analysis_right_forbidden_for_source_class",
    ]


def test_primary_source_citation_does_not_imply_full_redistribution() -> None:
    result = evaluate_source_claim_use(
        policy=_policy(),
        source_class="issuer_regulator_or_government_primary",
        claim_use="target_company_exact_fact",
        original_capture_bound=True,
        speaker_bound=True,
        subject_bound=True,
        requested_rights=("internal_analysis", "citation", "redistribution"),
    )

    assert result["evidence_promotion_allowed"] is True
    assert result["right_conditions"] == {
        "redistribution": "bounded_excerpt_and_attribution_only"
    }


def test_primary_industry_forecast_context_stays_bounded() -> None:
    result = evaluate_source_claim_use(
        policy=_policy(),
        source_class="official_market_or_industry_primary",
        claim_use="bounded_market_context",
        original_capture_bound=True,
        speaker_bound=True,
        subject_bound=True,
        independent_source_count=1,
    )

    assert result["evidence_promotion_allowed"] is True
    assert result["disposition"] == "admit_as_bounded_context_candidate"


def test_licensed_source_fails_closed_without_entitlement() -> None:
    result = evaluate_source_claim_use(
        policy=_policy(),
        source_class="licensed_structured_or_user_entitled",
        claim_use="market_exact_fact",
        original_capture_bound=True,
        speaker_bound=True,
        subject_bound=True,
        license_entitled=False,
    )

    assert result["evidence_promotion_allowed"] is False
    assert "license_entitlement_missing" in result["blockers"]


def test_policy_rejects_missing_source_strength_control() -> None:
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    payload["policy"]["source_strength_is_not_claim_truth"] = False

    with pytest.raises(SourceUsePolicyError, match="source_use_policy_shape_invalid"):
        SourceUsePolicy.from_mapping(payload)


def test_policy_rejects_exact_numeric_permission_drift() -> None:
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    mutated = deepcopy(payload)
    mutated["source_classes"][1][
        "target_company_exact_numeric_fact_allowed"
    ] = True

    with pytest.raises(
        SourceUsePolicyError,
        match="source_use_policy_numeric_permission_inconsistent",
    ):
        SourceUsePolicy.from_mapping(mutated)
