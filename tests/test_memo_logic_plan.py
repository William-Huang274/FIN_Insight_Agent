from __future__ import annotations

from sec_agent.memo_logic_plan import build_memo_logic_plan
from sec_agent.memo_llm import _compact_memo_logic_plan


def test_memo_logic_plan_carries_answer_first_evidence_to_thesis_bridge() -> None:
    plan = build_memo_logic_plan(
        judgment_state={
            "dimension_judgments": [
                {
                    "dimension_id": "fundamentals",
                    "title": "Fundamentals",
                    "claim_ids": ["claim_revenue_quality"],
                    "evidence_refs": ["ev_revenue", "ev_margin"],
                    "summary": "Revenue quality improved but margin bridge still matters.",
                },
                {
                    "dimension_id": "risk_and_counterevidence",
                    "title": "Risk And Counterevidence",
                    "claim_ids": [],
                    "evidence_refs": [],
                },
            ]
        },
        lead_review_checkpoint={
            "dimension_reviews": [
                {"dimension": "fundamentals", "status": "sufficient"},
                {"dimension": "risk_and_counterevidence", "status": "bounded_gap", "gap_ids": ["gap_price_in"]},
            ],
            "memo_directive": {
                "memo_stance": "The memo should lead with the operating thesis, then explain what would change it.",
                "gap_budget_policy": {"max_body_gap_sentences": 2},
            },
        },
    )

    assert plan["validation"]["status"] == "pass"
    assert plan["answer_first_outline"]["thesis_statement"].startswith("The memo should lead")
    assert plan["answer_first_outline"]["decision_changing_evidence_refs"] == ["ev_revenue", "ev_margin"]
    bridge = {row["dimension_id"]: row for row in plan["evidence_to_thesis_bridge"]}
    assert bridge["fundamentals"]["thesis_role"] == "supporting_thesis"
    assert bridge["fundamentals"]["evidence_refs"] == ["ev_revenue", "ev_margin"]
    assert bridge["risk_and_counterevidence"]["thesis_role"] == "boundary_or_counter_thesis"
    assert bridge["risk_and_counterevidence"]["gap_refs"] == ["gap_price_in"]

    compact = _compact_memo_logic_plan(plan)
    assert compact["answer_first_outline"]["decision_changing_evidence_refs"] == ["ev_revenue", "ev_margin"]
    assert compact["evidence_to_thesis_bridge"][0]["claim_ids"] == ["claim_revenue_quality"]
