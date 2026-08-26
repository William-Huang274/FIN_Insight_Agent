from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]

from retrieval.dell_report_internal_chain_ceiling_r7 import (
    ATTEMPT_ID,
    ATTEMPT_RECEIPT_REF,
    AUTHORITY,
    BRANCH,
    EXECUTION_CONTRACT,
    EXPECTED_BOUND_INPUT_IDS,
    EXPECTED_IMPLEMENTATION_PATHS,
    MIN_FREE_BYTES_BEFORE_ATTEMPT,
    POLICY_REF,
    POLICY_SCHEMA_VERSION,
    PRIVATE_REF,
    PRIVATE_RESULT_SCHEMA_VERSION,
    PROGRAM_ID,
    PUBLIC_REF,
    SEMANTIC_CONTRACT,
    DellReportInternalChainCeilingR7Error,
    _typed_material_anchors,
    assess_dell_report_internal_chain_r7_packages,
    build_dell_report_internal_chain_ceiling_r7_public_projection,
    classify_dell_report_internal_chain_r7_package,
    extract_typed_propositions,
    validate_dell_report_internal_chain_ceiling_r7_policy,
)
from retrieval.dell_report_internal_chain_ceiling_r5 import (
    classify_dell_report_internal_chain_r5_package,
)
from retrieval.dell_report_internal_chain_ceiling_r4 import (
    assess_dell_report_internal_chain_r4_packages,
    classify_dell_report_internal_chain_r4_package,
)
from retrieval.query_plan import canonical_digest
from scripts.data_retrieval import (
    run_dell_report_internal_chain_ceiling_r7 as r7_runner,
)


def _metadata(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "source_type": "PUBLIC_WEB",
        "source_tier": "named_counterparty_or_standards_primary",
        "publication_date": "2025-05-27",
    }


def _source(source_id: str, text: str, ticker: str = "NVDA") -> dict:
    return {
        "evidence_id": source_id,
        "text": text,
        "metadata": {},
        **_metadata(ticker),
    }


def _object(
    object_id: str,
    source_id: str,
    text: str,
    *,
    ticker: str = "NVDA",
) -> dict:
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
            **_metadata(ticker),
        },
    }


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA have no partnership for delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA lack a partnership for delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA denied a partnership for delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was not allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was never allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was unavailable to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was not yet allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was denied to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield rate will reach 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield rate is forecast to reach 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield rate is planned to reach 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "N2 pilot line HBM production yield rate is 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM availability was unavailable to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM supply capacity was not allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM supply capacity was unavailable to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM supply capacity was not configured for Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell has not shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell never shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell denied it shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell has not yet shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell said NVIDIA shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell said the customer shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
    ],
)
def test_R7_freezes_every_R4_semantic_attack(
    target_id: str, text: str
) -> None:
    predecessor = classify_dell_report_internal_chain_r4_package(
        target_id=target_id,
        text=text,
        metadata=_metadata("DELL"),
    )
    result = classify_dell_report_internal_chain_r7_package(
        target_id=target_id,
        text=text,
        metadata=_metadata("DELL"),
    )
    assert predecessor["classification"] == "complete_bounded_target_package"
    assert result["classification"] != "complete_bounded_target_package"


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "NVIDIA failed to supply Dell for AI server delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was rejected for Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM supply capacity was rejected for Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield should reach 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield was anticipated to reach 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield was estimated at 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "Prototype-line HBM production yield was 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell disclosed NVIDIA shipped four Dell PowerEdge XE9680 AI "
            "servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Acme reported Dell shipped four Dell PowerEdge XE9680 AI servers "
            "in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell refuted reports it shipped four Dell PowerEdge XE9680 AI "
            "servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "Dell denied quoting $15 for two Dell PowerEdge XE9680 servers.",
        ),
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "Dell did not quote $15 for two Dell PowerEdge XE9680 servers.",
        ),
    ],
)
def test_R7_freezes_fresh_R5_clause_and_polarity_attacks(
    target_id: str, text: str
) -> None:
    predecessor = classify_dell_report_internal_chain_r5_package(
        target_id=target_id,
        text=text,
        metadata=_metadata("DELL"),
    )
    result = classify_dell_report_internal_chain_r7_package(
        target_id=target_id,
        text=text,
        metadata=_metadata("DELL"),
    )
    assert predecessor["classification"] == "complete_bounded_target_package"
    assert result["classification"] != "complete_bounded_target_package"


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA may partner for delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity will be allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity is expected to be available for Dell "
            "in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity is likely available for Dell in Q1 "
            "2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM capacity was available in Q1 2026; PowerEdge systems will "
            "be configured with HBM.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM capacity was available in Q1 2026; PowerEdge systems were "
            "configured without HBM.",
        ),
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "Dell expects to quote $15 for two PowerEdge XE9680 servers.",
        ),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA partnership was dissolved after delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity allocation to Dell was revoked in Q1 "
            "2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was allocated away from Dell in Q1 "
            "2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield was 90% on the prototype line in 2026.",
        ),
    ],
)
def test_R7_rejects_speculative_or_absent_typed_propositions(
    target_id: str, text: str
) -> None:
    result = classify_dell_report_internal_chain_r7_package(
        target_id=target_id,
        text=text,
        metadata=_metadata("DELL"),
    )
    assert result["classification"] != "complete_bounded_target_package"


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA partnered for delivery, and AMD did not supply "
            "Dell.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was allocated to Dell in Q1 2026, but "
            "another component was unavailable.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield was 80%, and next process target is 95%.",
        ),
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "Dell quoted $15 for two Dell PowerEdge XE9680 servers, and AMD "
            "denied a separate price report.",
        ),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA partnered for delivery and no capacity allocation "
            "was disclosed.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was allocated to Dell in Q1 2026 and will "
            "ship later.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "A component was unavailable and Dell secured GPU production "
            "capacity in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "Dell quoted $15 for two Dell PowerEdge XE9680 servers and will "
            "offer support later.",
        ),
    ],
)
def test_R7_clause_scope_preserves_valid_positive_before_unrelated_negative(
    target_id: str, text: str
) -> None:
    result = classify_dell_report_internal_chain_r7_package(
        target_id=target_id,
        text=text,
        metadata=_metadata("DELL"),
    )
    assert result["classification"] == "complete_bounded_target_package"


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA partnered for delivery; no capacity allocation was disclosed.",
        ),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "NVIDIA and Dell are partnering to deliver end-to-end AI "
            "infrastructure.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity, not previously disclosed, was allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield rate was 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield rate was 80%, and will reach 90% in 2027.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM was not constrained and production yield was 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "A future discussion was planned and HBM production yield was "
            "90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM was not constrained, production yield was 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "HBM supply capacity was allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell was not alone when it shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell said it shipped four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
    ],
)
def test_R7_positive_roles_remain_complete(target_id: str, text: str) -> None:
    result = classify_dell_report_internal_chain_r7_package(
        target_id=target_id,
        text=text,
        metadata=_metadata("DELL"),
    )
    assert result["classification"] == "complete_bounded_target_package"


def test_R7_guard_limitation_is_not_added_when_guard_itself_passes() -> None:
    result = classify_dell_report_internal_chain_r7_package(
        target_id="DELL-RSQ-03A-TARGET-UNITS",
        text=(
            "Dell reported that it shipped four Dell PowerEdge servers in "
            "Q1 2026."
        ),
        metadata=_metadata("DELL"),
    )
    assert result["classification"] != "complete_bounded_target_package"
    assert (
        "negative_reported_or_non_Dell_typed_shipper_proposition"
        not in result["limitations"]
    )


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA allegedly partnered for delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA partnership rumor was denied.",
        ),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA partnered for delivery, but the partnership "
            "was later suspended.",
        ),
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "NVIDIA can supply Dell for AI server delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was allocated to HP rather than to "
            "Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity can be allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "Zero GPU production capacity was allocated to Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was allocated to Dell in Q1 2026; "
            "the allocation was later revoked.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield can reach 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production yield was 90%, but the figure was later withdrawn.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "Simulated HBM production yield was 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM supply was constrained. Orange juice production yield "
            "was 90% in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "A Dell customer reported Dell shipped four Dell PowerEdge "
            "XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell disputed reports it shipped four Dell PowerEdge XE9680 "
            "AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "Dell can quote $15 for two Dell PowerEdge XE9680 servers.",
        ),
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "Dell allegedly quoted $15 for two Dell PowerEdge XE9680 servers.",
        ),
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "Dell quoted $15 for two Dell PowerEdge XE9680 servers, but "
            "the quote was later withdrawn.",
        ),
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "HPE quoted $15. Dell offered two PowerEdge XE9680 servers.",
        ),
    ],
)
def test_R7_freezes_fresh_R6_single_proposition_attacks(
    target_id: str, text: str
) -> None:
    result = classify_dell_report_internal_chain_r7_package(
        target_id=target_id,
        text=text,
        metadata=_metadata("DELL"),
    )
    assert result["classification"] != "complete_bounded_target_package"
    assert result["accepted_proposition_id"] is None


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "NVIDIA is Dell's supplier for AI server delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
            "GPU production capacity was earmarked for Dell in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
            "Dell PowerEdge systems incorporated HBM.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "HBM production achieved a 90% yield in 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "Dell sent four Dell PowerEdge XE9680 AI servers in Q1 2026.",
        ),
        (
            "DELL-RSQ-03A-TARGET-ASP",
            "Dell sold two Dell PowerEdge XE9680 servers for $15.",
        ),
    ],
)
def test_R7_restores_fresh_R6_positive_controls(
    target_id: str, text: str
) -> None:
    result = classify_dell_report_internal_chain_r7_package(
        target_id=target_id,
        text=text,
        metadata=_metadata("DELL"),
    )
    assert result["classification"] == "complete_bounded_target_package"
    assert result["accepted_proposition_id"].startswith("PROP::R7::")
    assert len(result["accepted_proposition_digest"]) == 64


def test_R7_supplier_delivery_binds_predicate_object_not_adjacent_hardware() -> None:
    result = classify_dell_report_internal_chain_r7_package(
        target_id="DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        text=(
            "With seamless NVIDIA hardware and software from desktop to data "
            "center, only Dell delivers the consistency and reliability "
            "organizations need."
        ),
        metadata=_metadata("DELL"),
    )
    assert result["classification"] == "partial_context_only"
    assert result["accepted_proposition_id"] is None
    assert (
        "missing_R7_role:supplier_Dell_relationship_or_relevant_product_"
        "delivery_direction"
    ) in result["limitations"]


def test_R7_supplier_readthrough_preserves_typed_downstream_sellthrough() -> None:
    result = classify_dell_report_internal_chain_r7_package(
        target_id="DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        text=(
            "Dell servers with NVIDIA GB200 are shipping at scale for "
            "customers."
        ),
        metadata=_metadata("DELL"),
    )
    assert result["classification"] == "complete_bounded_target_package"
    proposition = next(
        row for row in result["typed_propositions"] if row["accepted"]
    )
    assert proposition["actor"] == "Dell"
    assert proposition["recipient"] == "customer_market"
    assert proposition["product"] == "gb200"


def test_R7_supplier_readthrough_preserves_explicit_partner_enumeration() -> None:
    result = classify_dell_report_internal_chain_r7_package(
        target_id="DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        text=(
            "We expanded the Dell AI factory ecosystem with partners, "
            "including NVIDIA."
        ),
        metadata=_metadata("DELL"),
    )
    assert result["classification"] == "complete_bounded_target_package"
    proposition = next(
        row for row in result["typed_propositions"] if row["accepted"]
    )
    assert proposition["actor"] == "nvidia"
    assert proposition["recipient"] == "Dell"


def test_R7_noun_plan_does_not_create_forward_modality() -> None:
    result = classify_dell_report_internal_chain_r7_package(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        text=(
            "Contract amount for the purchase of hardware and a five-year "
            "maintenance and support services plan is $2,278,577.28."
        ),
        metadata=_metadata("DELL"),
    )
    proposition = result["typed_propositions"][0]
    assert proposition["modality"] == "actual"
    assert result["classification"] == "partial_context_only"
    assert "Dell_seller_or_quoter" in proposition["missing_required_roles"]


def test_R7_capacity_supply_prefilter_is_a_recall_superset() -> None:
    source_id = "SRC::CAPACITY-SUPPLY-PREFILTER"
    result = assess_dell_report_internal_chain_r7_packages(
        target_id="DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
        source_rows=[
            _source(
                source_id,
                "GPU supply was earmarked for Dell in Q1 2026.",
                "DELL",
            )
        ],
        object_rows=[],
    )
    assert result["source_packages"][0]["classification"] == (
        "complete_bounded_target_package"
    )


def test_R7_never_unions_two_incomplete_propositions() -> None:
    text = "HPE quoted $15. Dell offered two PowerEdge XE9680 servers."
    propositions = extract_typed_propositions(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        text=text,
        metadata=_metadata("DELL"),
    )
    assert len(propositions) == 1
    assert propositions[0].accepted is False
    assert "Dell_seller_or_quoter" in propositions[0].missing_required_roles


def test_R7_typed_proposition_is_deterministic_and_role_local() -> None:
    kwargs = {
        "target_id": "DELL-RSQ-03A-TARGET-ASP",
        "text": (
            "Dell sold two Dell PowerEdge XE9680 servers for $15. "
            "HPE support cost was $150."
        ),
        "metadata": _metadata("DELL"),
    }
    first = classify_dell_report_internal_chain_r7_package(**kwargs)
    second = classify_dell_report_internal_chain_r7_package(**kwargs)
    assert first["typed_propositions"] == second["typed_propositions"]
    assert first["accepted_proposition_digest"] == second[
        "accepted_proposition_digest"
    ]
    assert "price.currency_usd:15" in first[
        "accepted_proposition_role_anchors"
    ]
    assert "price.currency_usd:150" not in first[
        "accepted_proposition_role_anchors"
    ]


def test_R7_assigns_positions_before_identical_sentence_deduplication() -> None:
    source_id = "SRC::RAW-POSITION-ASP"
    price = "Dell quoted a configuration price of $15."
    noise = "Administrative sentence."
    configuration = (
        "The two Dell PowerEdge XE9680 AI servers are configured systems."
    )
    source_rows = [
        _source(
            source_id,
            " ".join([price, *([noise] * 20), configuration]),
            "DELL",
        )
    ]
    predecessor = assess_dell_report_internal_chain_r4_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=source_rows,
        object_rows=[],
    )
    result = assess_dell_report_internal_chain_r7_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=source_rows,
        object_rows=[],
    )
    assert predecessor["source_packages"][0]["classification"] == (
        "complete_bounded_target_package"
    )
    assert result["source_packages"][0]["classification"] != (
        "complete_bounded_target_package"
    )


def test_R7_rejects_bounded_adjacency_without_one_complete_proposition() -> None:
    source_id = "SRC::BOUNDED-RAW-POSITION-ASP"
    text = " ".join(
        [
            "Dell quoted a configuration price of $15.",
            *(["Administrative sentence."] * 5),
            "The two Dell PowerEdge XE9680 AI servers are configured systems.",
        ]
    )
    result = assess_dell_report_internal_chain_r7_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, text, "DELL")],
        object_rows=[],
    )
    package = result["source_packages"][0]
    assert package["classification"] == "partial_context_only"
    assert package["window_unit_span"] == 1
    assert package["accepted_proposition_id"] is None
    assert package["accepted_proposition_digest"] is None


def test_R7_typed_anchors_exclude_product_code_digits() -> None:
    anchors = _typed_material_anchors(
        "NVIDIA H100 and Dell XE9680 systems were discussed in Q1 FY2026."
    )
    assert "product_code:h100" in anchors
    assert "product_code:xe9680" in anchors
    assert "number:100" not in anchors
    assert "number:9680" not in anchors
    assert "quarter:1" in anchors
    assert "fiscal_year:2026" in anchors


@pytest.mark.parametrize(
    ("variants", "expected"),
    [
        (
            ("H100", "H-100", "H/100", "H 100", "H‑100"),
            "product_code:h100",
        ),
        (
            ("XE9680", "XE-9680", "XE/9680", "XE 9680"),
            "product_code:xe9680",
        ),
    ],
)
def test_R7_product_code_separator_variants_share_one_canonical_anchor(
    variants: tuple[str, ...], expected: str
) -> None:
    for variant in variants:
        anchors = _typed_material_anchors(variant)
        assert anchors == [expected]


def test_R7_two_and_four_digit_fiscal_years_share_one_anchor() -> None:
    assert _typed_material_anchors("FY26") == ["fiscal_year:2026"]
    assert _typed_material_anchors("FY2026") == ["fiscal_year:2026"]
    assert _typed_material_anchors("fiscal year 2026") == [
        "fiscal_year:2026"
    ]


@pytest.mark.parametrize(
    "variant",
    ("H100s", "H-100s", "H−100", "H_100"),
)
def test_R7_plural_unicode_and_underscore_product_variants(
    variant: str,
) -> None:
    assert _typed_material_anchors(variant) == ["product_code:h100"]


def test_R7_unknown_product_like_separator_consumes_internal_number() -> None:
    anchors = _typed_material_anchors("H/800")
    assert anchors == ["product_code:unknown_h800"]
    assert "number:800" not in anchors


@pytest.mark.parametrize("variant", ("FY'26", "FY’26", "FY2026"))
def test_R7_fiscal_apostrophe_variants_are_canonical(variant: str) -> None:
    assert _typed_material_anchors(variant) == ["fiscal_year:2026"]


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        ("USD$15", {"currency_usd:15"}),
        ("15 dollars", {"currency_usd:15"}),
        ("$15m", {"currency_usd:15", "magnitude:million"}),
        ("about $15", {"currency_usd:15", "qualifier:about"}),
        ("at most $15", {"currency_usd:15", "qualifier:at_most"}),
    ],
)
def test_R7_currency_magnitude_and_qualifier_grammar(
    variant: str, expected: set[str]
) -> None:
    assert set(_typed_material_anchors(variant)) == expected


def test_R7_natural_article_before_count_is_not_A100_product_code() -> None:
    anchors = _typed_material_anchors("Dell shipped a 100 server order.")
    assert "product_code:a100" not in anchors
    assert "number:100" in anchors


def test_R7_numeric_anchor_15_is_not_covered_by_150() -> None:
    source_id = "SRC::EXACT-NUMERIC-ANCHOR"
    source_text = (
        "Dell quoted a configuration price of $15 for one Dell PowerEdge "
        "XE9680 AI server."
    )
    compiled_text = (
        "Dell quoted a configuration price of $150 for one Dell PowerEdge "
        "XE9680 AI server."
    )
    result = assess_dell_report_internal_chain_r7_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, source_text, "DELL")],
        object_rows=[
            _object("COBJ::ANCHOR-150", source_id, compiled_text, ticker="DELL")
        ],
    )
    assert result["coverage_gap_canonical_family_claim_count"] == 1
    assert "price.currency_usd:15" in result["coverage_gaps"][0][
        "material_anchors"
    ]


def test_R7_exact_typed_anchor_is_covered() -> None:
    source_id = "SRC::EXACT-TYPED-COVERAGE"
    text = (
        "Dell quoted a configuration price of $15 for one Dell PowerEdge "
        "XE9680 AI server."
    )
    result = assess_dell_report_internal_chain_r7_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, text, "DELL")],
        object_rows=[_object("COBJ::ANCHOR-15", source_id, text, ticker="DELL")],
    )
    assert result["coverage_gap_canonical_family_claim_count"] == 0


def test_R7_supplier_entity_cannot_be_covered_by_other_supplier() -> None:
    source_id = "SRC::ROLE-BOUND-SUPPLIER"
    result = assess_dell_report_internal_chain_r7_packages(
        target_id="DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        source_rows=[
            _source(
                source_id,
                "Dell and NVIDIA partnered for AI infrastructure delivery.",
                "DELL",
            )
        ],
        object_rows=[
            _object(
                "COBJ::ROLE-BOUND-SUPPLIER",
                source_id,
                "Dell and Micron partnered for AI infrastructure delivery.",
                ticker="DELL",
            )
        ],
    )
    assert result["coverage_gap_canonical_family_claim_count"] == 1
    anchors = set(result["coverage_gaps"][0]["material_anchors"])
    assert "actor:nvidia" in anchors
    assert "counterparty:dell" in anchors
    assert "predicate:supplier_relationship" in anchors


def test_R7_product_and_fiscal_year_variants_are_semantically_covered() -> None:
    source_id = "SRC::CANONICAL-PRODUCT-FY"
    source_text = (
        "Dell quoted a configuration price of $15 for one Dell PowerEdge "
        "XE/9680 AI server in FY26."
    )
    compiled_text = (
        "Dell quoted a configuration price of $15 for one Dell PowerEdge "
        "XE9680 AI server in FY2026."
    )
    result = assess_dell_report_internal_chain_r7_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, source_text, "DELL")],
        object_rows=[
            _object(
                "COBJ::CANONICAL-PRODUCT-FY",
                source_id,
                compiled_text,
                ticker="DELL",
            )
        ],
    )
    assert result["coverage_gap_canonical_family_claim_count"] == 0


def test_R7_material_anchors_exclude_unrelated_next_process_target() -> None:
    source_id = "SRC::TYPED-PROPOSITION-ANCHORS"
    source_text = (
        "HBM production yield was 80%, and next process target is 95% in "
        "2027."
    )
    compiled_text = "HBM production yield was 80%."
    result = assess_dell_report_internal_chain_r7_packages(
        target_id="DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
        source_rows=[_source(source_id, source_text, "NVDA")],
        object_rows=[
            _object(
                "COBJ::TYPED-PROPOSITION-ANCHORS",
                source_id,
                compiled_text,
                ticker="NVDA",
            )
        ],
    )
    assert result["coverage_gap_canonical_family_claim_count"] == 0


def test_R7_unrelated_exact_price_does_not_cover_changed_proposition_price() -> None:
    source_id = "SRC::ROLE-BOUND-PRICE"
    source_text = (
        "Dell sold two Dell PowerEdge XE9680 servers for $15."
    )
    compiled_text = (
        "Dell sold two Dell PowerEdge XE9680 servers for $150. "
        "Support cost was $15."
    )
    result = assess_dell_report_internal_chain_r7_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, source_text, "DELL")],
        object_rows=[
            _object(
                "COBJ::ROLE-BOUND-PRICE",
                source_id,
                compiled_text,
                ticker="DELL",
            )
        ],
    )
    assert result["coverage_gap_canonical_family_claim_count"] == 1
    assert set(result["coverage_gaps"][0]["material_anchors"]) == {
        "actor:dell",
        "object:xe9680",
        "predicate:price_quote_or_sale",
        "price.currency_usd:15",
        "product_code:xe9680",
        "quantity.physical_server:2",
    }


def test_R7_unrelated_third_party_product_and_count_do_not_cover_Dell_role() -> None:
    source_id = "SRC::ROLE-BOUND-PRODUCT"
    source_text = (
        "Dell sold two Dell PowerEdge H100 servers for $15."
    )
    compiled_text = (
        "Dell sold two Dell PowerEdge B200 servers for $15. "
        "HP deployed 100 unrelated systems."
    )
    result = assess_dell_report_internal_chain_r7_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, source_text, "DELL")],
        object_rows=[
            _object(
                "COBJ::ROLE-BOUND-PRODUCT",
                source_id,
                compiled_text,
                ticker="DELL",
            )
        ],
    )
    assert result["coverage_gap_canonical_family_claim_count"] == 1
    assert "product_code:h100" in result["coverage_gaps"][0][
        "material_anchors"
    ]


def test_R7_fiscal_apostrophe_and_four_digit_period_cover_same_role() -> None:
    source_id = "SRC::ROLE-BOUND-FISCAL"
    source_text = (
        "Dell sold two Dell PowerEdge XE9680 servers for $15 in FY'26."
    )
    compiled_text = (
        "Dell sold two Dell PowerEdge XE9680 servers for $15 in FY2026."
    )
    result = assess_dell_report_internal_chain_r7_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, source_text, "DELL")],
        object_rows=[
            _object(
                "COBJ::ROLE-BOUND-FISCAL",
                source_id,
                compiled_text,
                ticker="DELL",
            )
        ],
    )
    assert result["coverage_gap_canonical_family_claim_count"] == 0


def _R7_projection_fixture() -> dict:
    path = (
        ROOT
        / "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_"
        "candidate_ceiling/dell-rsq-03b-internal-chain-r6/full_result.json"
    )
    private = json.loads(path.read_text(encoding="utf-8"))
    private["schema_version"] = PRIVATE_RESULT_SCHEMA_VERSION
    private["attempt_id"] = ATTEMPT_ID
    private["status"] = (
        "dell_03B_R7_single_proposition_role_anchor_public_content_ceiling_executed"
    )
    authority = dict(private["authority"])
    authority["03B_R7_execution_consumed"] = authority.pop(
        "03B_R6_execution_consumed"
    )
    private["authority"] = authority
    bindings = dict(private["input_bindings"])
    for binding_id in (
        "R6_public",
        "R6_private",
        "R6_attempt_receipt",
        "R6_fresh_audit",
        "R7_policy",
    ):
        bindings[binding_id] = {
            "ref": f"configs/test/{binding_id}.json",
            "sha256": "a" * 64,
            "result_digest": "b" * 64,
        }
    bindings["git_identity"] = dict(bindings["git_identity"])
    bindings["git_identity"]["authority_commit_changed_paths"] = [
        POLICY_REF
    ]
    private["input_bindings"] = bindings
    body = dict(private)
    body.pop("result_digest")
    private["result_digest"] = canonical_digest(body)
    return private


def _redigest(value: dict) -> dict:
    body = dict(value)
    body.pop("result_digest", None)
    value["result_digest"] = canonical_digest(body)
    return value


def test_R7_public_projection_uses_recursive_explicit_allowlist() -> None:
    public = build_dell_report_internal_chain_ceiling_r7_public_projection(
        private_result=_R7_projection_fixture(),
        private_ref=PRIVATE_REF,
        private_sha256="c" * 64,
    )
    assert public["attempt_id"] == ATTEMPT_ID
    assert "raw_execution_receipt" not in public
    for row in public["target_results"]:
        assert not any(key.startswith("private_") for key in row)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("private_secret_payload", "SENSITIVE EXCERPT"),
        ("source_locator", "www.example.invalid/private"),
    ],
)
def test_R7_public_projection_rejects_unknown_target_field(
    field: str, value: str
) -> None:
    private = _R7_projection_fixture()
    private["target_results"][0][field] = value
    _redigest(private)
    with pytest.raises(
        DellReportInternalChainCeilingR7Error,
        match="target_unknown_or_missing_key",
    ):
        build_dell_report_internal_chain_ceiling_r7_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


def test_R7_public_projection_rejects_unknown_nested_public_field() -> None:
    private = _R7_projection_fixture()
    private["target_results"][0]["candidate_ceiling"][
        "private_secret_payload"
    ] = "SENSITIVE EXCERPT"
    _redigest(private)
    with pytest.raises(
        DellReportInternalChainCeilingR7Error,
        match="candidate_ceiling_unknown_or_missing_key",
    ):
        build_dell_report_internal_chain_ceiling_r7_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_proposition", "See www.example.invalid/private"),
        ("target_proposition", "See https://example.invalid/private"),
        ("target_proposition", "See s3://private-bucket/raw.json"),
        ("target_proposition", "See /private/source/raw.json"),
    ],
)
def test_R7_public_projection_rejects_locator_in_allowed_text_field(
    field: str, value: str
) -> None:
    private = _R7_projection_fixture()
    private["target_results"][0][field] = value
    _redigest(private)
    with pytest.raises(
        DellReportInternalChainCeilingR7Error,
        match="URL_or_absolute_locator",
    ):
        build_dell_report_internal_chain_ceiling_r7_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


def test_R7_public_projection_rejects_absolute_local_path() -> None:
    private = _R7_projection_fixture()
    private["known_boundary"] = r"Private source at D:\secret\raw.txt"
    _redigest(private)
    with pytest.raises(
        DellReportInternalChainCeilingR7Error,
        match="URL_or_absolute_locator",
    ):
        build_dell_report_internal_chain_ceiling_r7_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


def test_R7_public_projection_rejects_binding_digest_payload() -> None:
    private = _R7_projection_fixture()
    private["input_bindings"]["R6_public"]["sha256"] = "SENSITIVE"
    _redigest(private)
    with pytest.raises(
        DellReportInternalChainCeilingR7Error,
        match="binding_value_invalid",
    ):
        build_dell_report_internal_chain_ceiling_r7_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


def test_R7_public_projection_rejects_downstream_authority_drift() -> None:
    private = _R7_projection_fixture()
    private["authority"]["evidence_promotion_authorized"] = True
    _redigest(private)
    with pytest.raises(
        DellReportInternalChainCeilingR7Error,
        match="authority_value_invalid",
    ):
        build_dell_report_internal_chain_ceiling_r7_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (
            "api_" + "key = " + "token_" + "live_production_" + "A1b2C3d4E5f6",
            "credential_assignment",
        ),
        (
            "opaque Ab3Def5Gh7Jk9Lm2Np4Qr6St8Uv0Wx1Yz",
            "secret_like_high_entropy",
        ),
        (
            "See h%74tps%3A%2F%2Fexample.invalid%2Fprivate",
            "URL_or_absolute_locator",
        ),
        (
            "See ..\\..\\private\\raw.txt",
            "relative_parent_traversal",
        ),
        (
            "See ../../private/raw.txt",
            "relative_parent_traversal",
        ),
    ],
)
def test_R7_public_projection_rejects_allowed_narrative_content_attacks(
    payload: str, error: str
) -> None:
    private = _R7_projection_fixture()
    private["target_results"][0]["target_proposition"] = payload
    _redigest(private)
    with pytest.raises(DellReportInternalChainCeilingR7Error, match=error):
        build_dell_report_internal_chain_ceiling_r7_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


def test_R7_public_projection_rejects_secret_like_binding_ref() -> None:
    private = _R7_projection_fixture()
    secret_segment = "sk" + "-proj-" + "A1b2C3d4E5f6G7h8J9k0"
    private["input_bindings"]["R6_public"]["ref"] = (
        f"configs/test/{secret_segment}.json"
    )
    _redigest(private)
    with pytest.raises(
        DellReportInternalChainCeilingR7Error,
        match="secret_like_token",
    ):
        build_dell_report_internal_chain_ceiling_r7_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


def test_R7_public_projection_rejects_secret_like_request_identifier() -> None:
    private = _R7_projection_fixture()
    private["target_results"][0]["request_ids"] = [
        "token_" + "live_production_" + "A1b2C3d4E5f6"
    ]
    _redigest(private)
    with pytest.raises(
        DellReportInternalChainCeilingR7Error,
        match="request_id_grammar",
    ):
        build_dell_report_internal_chain_ceiling_r7_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


def test_R7_public_projection_accepts_financial_narrative_and_canonical_refs() -> None:
    private = _R7_projection_fixture()
    private["target_results"][0]["target_proposition"] = (
        "Dell PowerEdge XE9680 的 FY2026 bounded price 约为 $15，"
        "仍不是 company-wide ASP。"
    )
    _redigest(private)
    public = build_dell_report_internal_chain_ceiling_r7_public_projection(
        private_result=private,
        private_ref=PRIVATE_REF,
        private_sha256="c" * 64,
    )
    assert public["target_results"][0]["target_proposition"].endswith(
        "company-wide ASP。"
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _R7_policy_inputs() -> tuple[dict, dict[str, dict]]:
    refs = {
        "R1_policy": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_0.json",
        "R3_policy": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_2.json",
        "R3_public": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_2.json",
        "R3_private": "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r3/full_result.json",
        "R3_fresh_audit": "configs/audits/fin_ia_0_1_3_commit_28158e04_dell_03b_r3_fresh_audit_fail_v1_0.json",
        "R4_policy": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_3.json",
        "R4_public": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_3.json",
        "R4_private": "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r4/full_result.json",
        "R4_fresh_audit": "configs/audits/fin_ia_0_1_3_commit_3629272c_dell_03b_r4_fresh_dual_audit_fail_v1_0.json",
        "R4_audit_correction": "configs/audits/fin_ia_0_1_3_dell_03b_r4_audit_public_digest_correction_v1_0.json",
        "R5_policy": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_4.json",
        "R5_public": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_4.json",
        "R5_private": "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r5/full_result.json",
        "R5_attempt_receipt": "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r5/attempt_consumption_receipt.json",
        "R5_fresh_audit": "configs/audits/fin_ia_0_1_3_commit_8fe2caaf_dell_03b_r5_fresh_dual_audit_fail_v1_0.json",
        "R6_policy": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_5.json",
        "R6_public": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_5.json",
        "R6_private": "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r6/full_result.json",
        "R6_attempt_receipt": "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r6/attempt_consumption_receipt.json",
        "R6_fresh_audit": "configs/audits/fin_ia_0_1_3_commit_9ca3c830_dell_03b_r6_fresh_dual_audit_fail_v1_0.json",
        "R39_repair_result": "configs/retrieval/fin_ia_0_1_3_s1_abbreviation_claim_repair_successor_result_v1_0.json",
        "R39_embedding_result": "configs/retrieval/fin_ia_0_1_3_s1c_qwen_embedding_cache_successor_result_v1_3.json",
        "R39_route_policy": "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_6.json",
        "R39_hybrid_policy": "configs/retrieval/fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_9.json",
        "runtime_registry": "configs/runtime/fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json",
        "runtime_binding_receipt": "configs/runtime/fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_15.json",
        "residual_program": "configs/retrieval/fin_ia_0_1_3_s1_dell_report_residual_source_ladder_program_v1_1.json",
        "execution_program": "configs/retrieval/fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_3.json",
        "dell_product_readiness": "configs/retrieval/fin_ia_0_1_3_s1_dell_current_product_readiness_result_v1_7.json",
    }
    assert set(refs) == EXPECTED_BOUND_INPUT_IDS
    values = {
        key: json.loads((ROOT / ref).read_text(encoding="utf-8"))
        for key, ref in refs.items()
    }
    policy = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "status": (
            "same_stage_R7_execution_authorized_after_fresh_R6_audit_failure"
        ),
        "program_id": PROGRAM_ID,
        "attempt_id": ATTEMPT_ID,
        "recorded_at": "2026-08-26",
        "execution_contract": deepcopy(EXECUTION_CONTRACT),
        "semantic_contract": deepcopy(SEMANTIC_CONTRACT),
        "output_contract": {
            "policy_ref": POLICY_REF,
            "private_result_ref": PRIVATE_REF,
            "public_result_ref": PUBLIC_REF,
            "attempt_consumption_receipt_ref": ATTEMPT_RECEIPT_REF,
            "alternate_output_paths_authorized": False,
            "private_public_same_path_authorized": False,
            "exclusive_create_required": True,
            "atomic_pair_with_rollback_required": True,
            "same_attempt_retry_authorized": False,
            "minimum_free_bytes_before_attempt": MIN_FREE_BYTES_BEFORE_ATTEMPT,
        },
        "bound_inputs": {
            key: {"ref": ref, "sha256": _sha(ROOT / ref)}
            for key, ref in refs.items()
        },
        "execution_identity": {
            "branch": BRANCH,
            "implementation_commit": "a" * 40,
            "implementation_tree": "b" * 40,
            "authority_commit_changed_paths": [POLICY_REF],
            "authority_commit_parent_must_equal_implementation_commit": True,
            "HEAD_must_equal_upstream": True,
        },
        "implementation_bindings": [
            {"path": path, "sha256": "c" * 64}
            for path in sorted(EXPECTED_IMPLEMENTATION_PATHS)
        ],
        "TokenBudgetBasis": {
            "node_purpose": "one exact R7 local candidate-chain audit",
            "input_scale": "five requests, 1,888 sources, 34,199 objects",
            "required_outputs": "raw positions, typed coverage and routes",
            "schema_burden": "R6 failure, R39 runtime and zero authority",
            "materiality_quality_risk": "false adjacency, anchors or roles",
            "comparable_run_evidence": "immutable R6 plus failed fresh audit",
            "reasoning_profile": "one local 0.6B batch and deterministic R7",
            "stop_and_truncation": "any identity or authority drift stops",
        },
        "authority": deepcopy(AUTHORITY),
    }
    policy["result_digest"] = canonical_digest(policy)
    return policy, values


def _validate_policy(policy: dict, values: dict[str, dict]) -> dict:
    return validate_dell_report_internal_chain_ceiling_r7_policy(
        policy,
        r1_policy=values["R1_policy"],
        r3_policy=values["R3_policy"],
        r3_public=values["R3_public"],
        r3_private=values["R3_private"],
        r3_fresh_audit=values["R3_fresh_audit"],
        r4_policy=values["R4_policy"],
        r4_public=values["R4_public"],
        r4_private=values["R4_private"],
        r4_fresh_audit=values["R4_fresh_audit"],
        r4_audit_correction=values["R4_audit_correction"],
        r5_policy=values["R5_policy"],
        r5_public=values["R5_public"],
        r5_private=values["R5_private"],
        r5_attempt_receipt=values["R5_attempt_receipt"],
        r5_fresh_audit=values["R5_fresh_audit"],
        r6_policy=values["R6_policy"],
        r6_public=values["R6_public"],
        r6_private=values["R6_private"],
        r6_attempt_receipt=values["R6_attempt_receipt"],
        r6_fresh_audit=values["R6_fresh_audit"],
        r39_repair_result=values["R39_repair_result"],
        r39_embedding_result=values["R39_embedding_result"],
        r39_route_policy=values["R39_route_policy"],
        r39_hybrid_policy=values["R39_hybrid_policy"],
        runtime_registry=values["runtime_registry"],
        runtime_binding_receipt=values["runtime_binding_receipt"],
        residual_program=values["residual_program"],
        execution_program=values["execution_program"],
        dell_product_readiness=values["dell_product_readiness"],
    )


def test_R7_policy_binds_immutable_R4_failure_and_R39_runtime() -> None:
    policy, values = _R7_policy_inputs()
    legacy = _validate_policy(policy, values)
    assert len(legacy["target_contracts"]) == 6


def test_R7_policy_rejects_missing_R4_root_cause() -> None:
    policy, values = _R7_policy_inputs()
    drift = deepcopy(values)
    audit = deepcopy(values["R4_fresh_audit"])
    audit["material_findings"] = [
        row
        for row in audit["material_findings"]
        if row.get("root_cause_id")
        != "RC-S1-077-DELL-03B-dedup-before-position-and-substring-anchor-equivalence"
    ]
    body = dict(audit)
    body.pop("result_digest")
    audit["result_digest"] = canonical_digest(body)
    drift["R4_fresh_audit"] = audit
    with pytest.raises(ValueError, match="required_root_causes"):
        _validate_policy(policy, drift)


@pytest.mark.parametrize(
    ("section", "field"),
    (
        ("original_audit", "sha256"),
        ("corrected_binding", "R4_public_sha256"),
    ),
)
def test_R7_policy_rejects_correction_SHA_not_cross_bound_to_policy(
    section: str, field: str
) -> None:
    policy, values = _R7_policy_inputs()
    drift = deepcopy(values)
    correction = deepcopy(values["R4_audit_correction"])
    correction[section][field] = "0" * 64
    body = dict(correction)
    body.pop("result_digest")
    correction["result_digest"] = canonical_digest(body)
    drift["R4_audit_correction"] = correction
    with pytest.raises(ValueError, match="R4_audit_correction_invalid"):
        _validate_policy(policy, drift)


def test_R7_policy_rejects_missing_R6_root_cause() -> None:
    policy, values = _R7_policy_inputs()
    drift = deepcopy(values)
    audit = deepcopy(values["R6_fresh_audit"])
    audit["material_findings"] = [
        row
        for row in audit["material_findings"]
        if row.get("root_cause_id")
        != "RC-S1-080-DELL-03B-typed-anchor-product-code-and-fiscal-year-normalization"
    ]
    body = dict(audit)
    body.pop("result_digest")
    audit["result_digest"] = canonical_digest(body)
    drift["R6_fresh_audit"] = audit
    with pytest.raises(
        DellReportInternalChainCeilingR7Error,
        match="required_root_causes",
    ):
        _validate_policy(policy, drift)


def test_R7_disk_capacity_gate_runs_before_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        r7_runner.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=1000, used=900, free=100),
    )
    with pytest.raises(RuntimeError, match="minimum_free_disk_capacity"):
        r7_runner._require_output_disk_capacity()

    monkeypatch.setattr(
        r7_runner.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(
            total=MIN_FREE_BYTES_BEFORE_ATTEMPT * 2,
            used=MIN_FREE_BYTES_BEFORE_ATTEMPT,
            free=MIN_FREE_BYTES_BEFORE_ATTEMPT,
        ),
    )
    receipt = r7_runner._require_output_disk_capacity()
    assert receipt["minimum_free_bytes"] == MIN_FREE_BYTES_BEFORE_ATTEMPT
