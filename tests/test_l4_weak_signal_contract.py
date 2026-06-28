from __future__ import annotations

from pathlib import Path

import pytest

from sec_agent.l4_weak_signal import (
    classify_l4_source,
    dedupe_weak_signal_leads,
    evaluate_l4_promotion_attempt,
    is_weak_signal_expired,
    load_l4_runtime_objects,
    make_weak_signal_exclusion_note,
    make_weak_signal_lead,
    validate_l4_not_promoted_to_claim_cards,
    validate_memo_l4_usage,
    weak_signal_to_targeted_repair_plan,
    write_l4_runtime_objects,
)


def test_classifier_routes_verified_official_social_to_l2_not_l4() -> None:
    result = classify_l4_source(
        source_id="official_social_accounts",
        source_url="https://x.com/nvidia",
        source_class="official_social_account",
        verified_account=True,
    )

    assert result["source_layer_id"] == "L2"
    assert result["is_l4"] is False
    assert result["weak_signal_allowed"] is False
    assert result["claim_card_allowed"] is True


def test_classifier_keeps_commercial_tracker_as_gap_not_l4_proxy() -> None:
    result = classify_l4_source(source_id="commercial_market_data_and_consensus")

    assert result["source_layer_id"] == "commercial_gap"
    assert result["is_l4"] is False
    assert result["route"] == "commercial_gap_ledger"
    assert result["claim_card_allowed"] is False

    with pytest.raises(ValueError, match="commercial_gap_source"):
        make_weak_signal_lead(source_id="commercial_market_data_and_consensus", extracted_hint="IDC share says X")


def test_unverified_forum_lead_is_ttl_deduped_and_repair_only() -> None:
    lead = make_weak_signal_lead(
        source_id="unverified_self_media_forums",
        source_url="https://reddit.com/r/hardware/comments/example",
        observed_at="2026-06-17T00:00:00Z",
        ticker_candidates=["NVDA"],
        product_candidates=["Blackwell GPU"],
        extracted_hint="Forum chatter says Blackwell GPU supply is allocated to a cloud customer; check official product and customer routes.",
        ttl_days=7,
    )
    duplicate = make_weak_signal_lead(
        source_id="unverified_self_media_forums",
        source_url="https://reddit.com/r/hardware/comments/example?utm=1",
        observed_at="2026-06-18T00:00:00Z",
        ticker_candidates=["NVDA"],
        product_candidates=["Blackwell GPU"],
        extracted_hint="Forum chatter says Blackwell GPU supply is allocated to a cloud customer; check official product and customer routes.",
        ttl_days=7,
    )

    deduped = dedupe_weak_signal_leads([lead, duplicate])
    plan = weak_signal_to_targeted_repair_plan(deduped[0])

    assert len(deduped) == 1
    assert deduped[0].observed_at == "2026-06-18T00:00:00Z"
    assert deduped[0].source_layer_id == "L4"
    assert deduped[0].exact_value_authority is False
    assert "sales" in deduped[0].disallowed_claim_scopes
    assert plan["source_lead_only"] is True
    assert "official_product_surface" in plan["repair_routes"]
    assert "L2" in plan["target_layers"]
    assert is_weak_signal_expired(deduped[0], now="2026-06-24T00:00:01Z") is False
    assert is_weak_signal_expired(deduped[0], now="2026-06-25T00:00:01Z") is True


def test_l4_promotion_gate_rejects_direct_l4_and_accepts_parser_backed_l2() -> None:
    lead = make_weak_signal_lead(
        source_id="generic_search_snippet",
        source_url="https://search.example/snippet",
        observed_at="2026-06-17T00:00:00Z",
        ticker_candidates=["ASML"],
        product_candidates=["EUV lithography"],
        extracted_hint="Snippet suggests a new EUV product page; repair against company IR/product pages.",
    )
    l4_row = {
        "source_layer_id": "L4",
        "source_id": "generic_search_snippet",
        "evidence_ref": "snippet:asml:euv",
        "structured_context_type": "search_snippet",
        "ticker": "ASML",
        "product_or_segment": "EUV lithography",
    }
    l2_row = {
        "source_layer_id": "L2",
        "source_id": "company_product_pages",
        "source_class": "company_product_page",
        "evidence_ref": "company_product_pages:ASML:EUV",
        "bounded_structured_context": True,
        "ticker": "ASML",
        "product_or_segment": "EUV lithography",
        "issuer_binding_status": "company_domain_bound",
        "product_binding_status": "product_mentioned_in_snapshot",
        "exact_value_authority": False,
    }

    direct = evaluate_l4_promotion_attempt(lead, promoted_row=l4_row, fetch_result="fetched")
    promoted = evaluate_l4_promotion_attempt(lead, promoted_row=l2_row, fetch_result="fetched")

    assert direct.promotion_status == "blocked"
    assert direct.promotion_reason == "l4_direct_promotion_forbidden"
    assert promoted.promotion_status == "promoted"
    assert promoted.target_layer == "L2"
    assert promoted.promoted_evidence_ref == "company_product_pages:ASML:EUV"


def test_l4_promotion_gate_rejects_l3_exact_authority_and_unbound_rows() -> None:
    lead = make_weak_signal_lead(
        source_id="unverified_self_media_forums",
        source_url="https://reddit.com/r/investing/comments/example",
        observed_at="2026-06-17T00:00:00Z",
        ticker_candidates=["DELL"],
        product_candidates=["AI server"],
        extracted_hint="Forum says AI server inventory is down; check channel offer pages.",
    )
    l3_exact_row = {
        "source_layer_id": "L3",
        "source_id": "channel_pricing_quotations",
        "evidence_ref": "channel:DELL:ai_server",
        "bounded_structured_context": True,
        "ticker": "DELL",
        "product_or_segment": "AI server",
        "exact_value_authority": True,
    }
    unbound_row = {
        "source_layer_id": "L3",
        "source_id": "channel_pricing_quotations",
        "evidence_ref": "channel:HPQ:laptop",
        "bounded_structured_context": True,
        "ticker": "HPQ",
        "product_or_segment": "laptop",
        "exact_value_authority": False,
    }

    exact_attempt = evaluate_l4_promotion_attempt(lead, promoted_row=l3_exact_row, fetch_result="fetched")
    unbound_attempt = evaluate_l4_promotion_attempt(lead, promoted_row=unbound_row, fetch_result="fetched")

    assert exact_attempt.promotion_status == "blocked"
    assert exact_attempt.promotion_reason == "l2_l3_exact_authority_promotion_forbidden"
    assert unbound_attempt.promotion_status == "entity_unresolved"


def test_l4_claimcard_and_memo_usage_are_fail_closed() -> None:
    lead = make_weak_signal_lead(
        source_id="yahoo_chart",
        source_url="https://finance.yahoo.com/quote/NVDA",
        observed_at="2026-06-17T00:00:00Z",
        ticker_candidates=["NVDA"],
        extracted_hint="Price spike after product launch rumor.",
    )
    claim_cards = [
        {
            "claim_id": "bad_l4_claim",
            "claim": "NVDA product launch is commercially successful.",
            "source_layer_id": "L4",
            "source_id": "yahoo_chart",
            "weak_signal_lead_id": lead.lead_id,
            "exact_value_authority": True,
        }
    ]

    claim_validation = validate_l4_not_promoted_to_claim_cards(claim_cards, l4_lead_ids=[lead.lead_id])
    memo_validation = validate_memo_l4_usage({"memo_claims": claim_cards})

    assert claim_validation["status"] == "fail"
    assert {error["type"] for error in claim_validation["errors"]} == {
        "l4_claim_card_forbidden",
        "l4_exact_authority_forbidden",
    }
    assert memo_validation["status"] == "fail"


def test_l4_runtime_store_writes_leads_exclusions_and_attempts(tmp_path: Path) -> None:
    lead = make_weak_signal_lead(
        source_id="common_crawl_index",
        source_url="https://example.com/product",
        observed_at="2026-06-17T00:00:00Z",
        ticker_candidates=["AMD"],
        product_candidates=["ROCm"],
        extracted_hint="Common Crawl found a product page candidate.",
    )
    note = make_weak_signal_exclusion_note(
        lead=lead,
        exclusion_reason="official_product_route_not_found",
        checked_routes=["official_product_surface"],
        why_not_promoted="No parser-backed official product row was found.",
    )
    attempt = evaluate_l4_promotion_attempt(lead, promoted_row=None, target_layer="L2")
    output_path = tmp_path / "l4_objects.jsonl"

    summary = write_l4_runtime_objects(
        leads=[lead],
        exclusion_notes=[note],
        promotion_attempts=[attempt],
        output_path=output_path,
    )
    loaded = load_l4_runtime_objects(output_path)

    assert summary["weak_signal_lead_count"] == 1
    assert summary["exclusion_note_count"] == 1
    assert summary["promotion_attempt_count"] == 1
    assert loaded["weak_signal_leads"][0]["lead_id"] == lead.lead_id
    assert loaded["exclusion_notes"][0]["lead_id"] == lead.lead_id
    assert loaded["promotion_attempts"][0]["promotion_status"] == "not_found"
