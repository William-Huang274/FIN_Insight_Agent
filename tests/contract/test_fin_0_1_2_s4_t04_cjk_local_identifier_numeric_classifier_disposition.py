from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests/contract")]

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    CaseNumericAuthorityPolicy,
    S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentExecutor,
)
from fin_0_1_2_realistic_fixture_support import (
    load_mu_realistic_input_and_admission,
)


def _policy() -> CaseNumericAuthorityPolicy:
    input_pack, _ = load_mu_realistic_input_and_admission()
    return CaseNumericAuthorityPolicy.from_cell_input(
        S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
            input_pack.cell_inputs[1],
            policy_ref=S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
        )
    )


@pytest.mark.parametrize(
    "text",
    (
        "C001（证据方向支持）与C002（反证机制削弱）存在冲突。",
        "C001有事实支持，C002有反证事实支持。",
        "瓶颈反证中C005有事实支持，C006有事实支持。",
        "第 2 项引用 Claim_17 与 fact#004 进行本地关联。",
        "中文C001有；C001，C001。",
    ),
)
def test_schema_local_identifiers_are_nonterminal_across_CJK_boundaries(
    text: str,
) -> None:
    policy = _policy()
    output = {"statement": text}
    matches = policy.provider_narrative_matches(output)
    assert policy.first_provider_narrative_violation(output) is None
    assert matches
    assert {row.semantic_class for row in matches} == {
        "request_local_identifier"
    }
    assert all(row.terminal is False for row in matches)


@pytest.mark.parametrize(
    ("text", "semantic_class"),
    (
        ("XC001 不是本地独立 ID", "material_numeric_value"),
        ("C001_suffix 不是本地独立 ID", "material_numeric_value"),
        ("C001对应毛利率84.6%", "percentage"),
        ("C002对应金额$4.1B", "financial_amount"),
        ("C005需要120 days库存", "measurement"),
        ("C006参考2026-08-04", "unknown_reporting_period_label"),
    ),
)
def test_identifier_allowance_does_not_hide_real_or_embedded_numeric_tokens(
    text: str,
    semantic_class: str,
) -> None:
    violation = _policy().first_provider_narrative_violation(
        {"statement": text}
    )
    assert violation is not None
    assert semantic_class in violation.semantic_classes
