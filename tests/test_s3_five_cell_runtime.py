from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
)
from scripts.research.run_s3_current_research_consumer_zero_call import _services
from sec_agent.research.current_consumer import (
    compile_current_research_deliverable,
    compile_current_research_input,
)
from sec_agent.research.five_cell_runtime import (
    FiveCellResearchError,
    compile_five_cell_analysis_messages,
    compile_five_cell_report,
    compile_five_cell_submission,
    compile_five_cell_synthesis_analysis_messages,
    compile_five_cell_synthesis_submission,
    validate_five_cell_synthesis,
)


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def five_cell_input() -> dict[str, object]:
    evidence_service, retrieval_service = _services()
    permissions = frozenset({"current_product:read"})
    evidence_pack = evidence_service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", permissions)
    )
    controlled = retrieval_service.execute_controlled_plan(
        "DELL",
        _json(
            ROOT
            / "configs/research/evals/"
            "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
        ),
        _json(
            ROOT
            / "tests/fixtures/research/"
            "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
        ),
        ResearchRetrievalPrincipal("current", permissions),
    )
    return compile_current_research_input(
        policy=_json(
            ROOT
            / "configs/research/"
            "fin_ia_0_1_3_s3_current_research_consumer_policy_v1_3.json"
        ),
        evidence_pack=evidence_pack,
        controlled_plan=controlled,
    )


@pytest.fixture(scope="module")
def five_cell_judgment() -> dict[str, object]:
    return _json(
        ROOT
        / "tests/fixtures/research/"
        "fin_ia_0_1_3_s3_dell_current_research_consumer_fake_payload_v1_3.json"
    )


@pytest.fixture(scope="module")
def validated_judgment(
    five_cell_input: dict[str, object],
    five_cell_judgment: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    deliverable = compile_current_research_deliverable(
        research_input=five_cell_input,
        judgment_output=five_cell_judgment,
    )
    trusted = {
        "schema_version": "fin_ia_current_research_judgment_v1_2",
        "research_input_digest": five_cell_input["research_input_digest"],
        "cells": [
            {
                key: deepcopy(value)
                for key, value in row.items()
                if key
                not in {
                    "title_zh",
                    "evidence_uses_rendered",
                    "numeric_facts",
                    "numeric_relations",
                    "remaining_gaps",
                }
            }
            for row in deliverable["cells"]
        ],
    }
    trusted["judgment_output_digest"] = deliverable["judgment_output_digest"]
    return trusted, deliverable


def _synthesis_payload(
    judgment: dict[str, object],
) -> dict[str, object]:
    cells = judgment["cells"]
    assert isinstance(cells, list)
    evidence = []
    numeric = []
    relations = []
    gaps = []
    for row in cells:
        evidence.extend(use["evidence_ref"] for use in row["evidence_uses"])
        numeric.extend(row["numeric_refs"])
        relations.extend(row["numeric_relation_refs"])
        gaps.extend(row["remaining_gap_refs"])
    return {
        "overall_judgment": "mixed",
        "confidence_basis": "mixed_source_strength",
        "inference_authority": "bounded_inference",
        "executive_thesis": "戴尔人工智能服务器需求获得直接支持，但利润与现金转化仍缺少产品层桥接。",
        "cross_cell_mechanism": "需求与经营规模提供转化条件，产品组合、供应约束和营运资金共同限制价值沉淀。",
        "strongest_counterargument": "订单与积压可能包含提前采购，集团改善也可能来自其他业务和成本因素。",
        "key_cell_ids": [row["cell_id"] for row in cells],
        "cell_links": [
            {
                "from_cell_id": "CELL::demand_quality",
                "to_cell_id": "CELL::operating_performance",
                "relation": "supports",
                "explanation": "订单与积压为经营规模提供需求背景，但不能单独证明利润贡献。",
            },
            {
                "from_cell_id": "CELL::cash_conversion",
                "to_cell_id": "CELL::value_capture",
                "relation": "limits",
                "explanation": "集团现金改善不能替代产品收入到利润和现金的直接桥接。",
            },
        ],
        "evidence_refs": list(dict.fromkeys(evidence))[:6],
        "numeric_refs": list(dict.fromkeys(numeric))[:6],
        "numeric_relation_refs": list(dict.fromkeys(relations))[:4],
        "remaining_gap_refs": list(dict.fromkeys(gaps))[:5],
        "what_would_change": {
            "observable": "产品收入、成本、利润与营运资金形成可复算且连续的桥接",
            "direction": "resolve_gap",
            "time_horizon": "后续连续披露期",
            "evidence_route": "公司申报材料、官方业绩说明与可复算产品财务桥",
            "threshold_numeric_ref": "",
        },
    }


def test_five_cell_analysis_and_submission_are_cell_local(
    five_cell_input: dict[str, object],
) -> None:
    messages = compile_five_cell_analysis_messages(
        research_input=five_cell_input,
        cell_id="CELL::cash_conversion",
    )
    assert len(messages) == 2
    assert "not a Tool Call" in messages[0]["content"]
    assert "CELL::cash_conversion" in messages[1]["content"]
    assert "CELL::demand_quality" not in messages[1]["content"]

    submission, tool = compile_five_cell_submission(
        research_input=five_cell_input,
        cell_id="CELL::cash_conversion",
        analysis_draft="现金转换需要同时检查利润、营运资金和资本开支，并保留产品归因缺口。",
    )
    assert [row["role"] for row in submission] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert tool["function"]["name"] == "submit_research_judgment"
    assert tool["function"]["strict"] is True


def test_five_cell_synthesis_uses_only_validated_cell_refs(
    five_cell_input: dict[str, object],
    validated_judgment: tuple[dict[str, object], dict[str, object]],
) -> None:
    judgment, deliverable = validated_judgment
    payload = _synthesis_payload(judgment)
    synthesis = validate_five_cell_synthesis(
        payload,
        research_input=five_cell_input,
        judgment_output=judgment,
    )
    assert synthesis["schema_version"] == "fin_ia_five_cell_synthesis_v1_0"
    assert len(synthesis["key_cell_ids"]) == 5

    analysis = compile_five_cell_synthesis_analysis_messages(
        research_input=five_cell_input,
        judgment_output=judgment,
        structured_deliverable=deliverable,
    )
    submission, tool = compile_five_cell_synthesis_submission(
        research_input=five_cell_input,
        judgment_output=judgment,
        structured_deliverable=deliverable,
        analysis_draft="五个研究单元共同表明需求有直接支撑，但价值与现金转化仍受桥接缺口限制。",
    )
    assert len(analysis) == 2
    assert len(submission) == 4
    assert tool["function"]["name"] == "submit_five_cell_synthesis"

    report = compile_five_cell_report(
        research_input=five_cell_input,
        structured_deliverable=deliverable,
        synthesis=synthesis,
    )
    assert report["status"] == "five_cell_internal_research_report_compiled"
    assert len(report["cells"]) == 5
    assert report["rendering_authority"][
        "harness_generated_research_conclusion"
    ] is False


def test_five_cell_synthesis_fails_closed_on_free_number_or_unselected_ref(
    five_cell_input: dict[str, object],
    validated_judgment: tuple[dict[str, object], dict[str, object]],
) -> None:
    judgment, _ = validated_judgment
    payload = _synthesis_payload(judgment)
    payload["executive_thesis"] = "需求增长百分之百支持利润改善。"
    with pytest.raises(FiveCellResearchError) as exc:
        validate_five_cell_synthesis(
            payload,
            research_input=five_cell_input,
            judgment_output=judgment,
        )
    assert exc.value.code == "five_cell_synthesis_thesis_invalid"

    payload = _synthesis_payload(judgment)
    payload["evidence_refs"].append("EV::NOT_SELECTED")
    with pytest.raises(FiveCellResearchError) as exc:
        validate_five_cell_synthesis(
            payload,
            research_input=five_cell_input,
            judgment_output=judgment,
        )
    assert exc.value.code == "five_cell_synthesis_evidence_refs_invalid"


def test_five_cell_synthesis_rejects_self_links_and_missing_cell_coverage(
    five_cell_input: dict[str, object],
    validated_judgment: tuple[dict[str, object], dict[str, object]],
) -> None:
    judgment, _ = validated_judgment
    payload = _synthesis_payload(judgment)
    payload["cell_links"][0]["to_cell_id"] = "CELL::demand_quality"
    with pytest.raises(FiveCellResearchError) as exc:
        validate_five_cell_synthesis(
            payload,
            research_input=five_cell_input,
            judgment_output=judgment,
        )
    assert exc.value.code == "five_cell_synthesis_links_invalid"

    payload = _synthesis_payload(judgment)
    payload["key_cell_ids"] = payload["key_cell_ids"][:-1]
    with pytest.raises(FiveCellResearchError) as exc:
        validate_five_cell_synthesis(
            payload,
            research_input=five_cell_input,
            judgment_output=judgment,
        )
    assert exc.value.code == "five_cell_synthesis_cell_coverage_invalid"
