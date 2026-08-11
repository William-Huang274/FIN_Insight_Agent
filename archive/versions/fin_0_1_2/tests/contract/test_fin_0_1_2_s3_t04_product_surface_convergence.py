from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s3_t04_product_surface import (  # noqa: E402
    S3T04ProductSurfaceError,
    materialize_verified_product_surface,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from scripts.releases import (  # noqa: E402
    run_fin_ia_0_1_2_s3_t03_nvda_replacement_controlled_successor as replacement,
)


RESULT = (
    ROOT
    / ".codex_runtime/fin012-s3-t03-nvda-replacement-r2/execution-result.json"
)
SURFACE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t04_product_surface_"
    "convergence_and_evidence_density_block_v1_0.json"
)


@lru_cache(maxsize=1)
def _cached_input_pack() -> dict:
    base = replacement._activate_issued_binding()
    target = base.load_target()
    admission = base.load_admission(target)
    with tempfile.TemporaryDirectory(
        prefix="fin012-s3-t04-product-surface-test-"
    ) as temp:
        prepared = base.prepare_exact_input(Path(temp), target, admission)
    return prepared.input_pack.model_dump(mode="json")


def _input_pack() -> dict:
    return deepcopy(_cached_input_pack())


def _result() -> dict:
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_final_delivery_surface_fixes_renderer_and_binds_local_verifier() -> None:
    before = hashlib.sha256(RESULT.read_bytes()).hexdigest()
    result = materialize_verified_product_surface(
        execution_result=_result(),
        input_pack=_input_pack(),
    )
    assert result["status"] == (
        "delivery_surface_pass_fixture_evidence_density_block"
    )
    preview = result["final_delivery_preview"]
    text = json.dumps(preview, ensure_ascii=False)
    assert "__company_total__" not in text
    assert "FY2025-FY" not in text
    assert "USD 130497000000 USD" not in text
    assert "NVDA 公司整体 FY2025 营收 = USD 130,497,000,000" in text
    assert "证据方向支持当前单元判断" not in text
    assert "不足以单独证明该判断的因果机制" in text
    verifier = result["final_delivery_verification"]
    assert verifier["status"] == "pass"
    assert verifier["checks"][
        "numeric_only_support_not_overstated_as_evidence"
    ] == "pass"
    assert verifier["final_delivery_preview_digest"] == preview[
        "final_delivery_preview_digest"
    ]
    assert hashlib.sha256(RESULT.read_bytes()).hexdigest() == before


def test_all_WWC_thresholds_come_from_frozen_case_contract() -> None:
    result = materialize_verified_product_surface(
        execution_result=_result(),
        input_pack=_input_pack(),
    )
    tasks = [
        task
        for section in result["final_delivery_preview"]["sections"]
        for task in section["what_would_change"]
    ]
    assert len(tasks) == 7
    assert all(
        task["decision_rule"]["threshold_source"]
        == "frozen_runtime_branch.what_would_change"
        for task in tasks
    )
    assert not any(
        "绑定权威观察"
        in task["decision_rule"]["threshold_or_observation"]
        for task in tasks
    )


def test_candidate_metadata_is_not_silently_promoted_to_fix_coverage() -> None:
    result = materialize_verified_product_surface(
        execution_result=_result(),
        input_pack=_input_pack(),
    )
    qualification = result["fixture_evidence_qualification"]
    assert qualification["qualified_evidence_cells"] == 0
    assert qualification["status"] == (
        "blocked_requires_promoted_evidence_not_candidate_metadata"
    )
    assert result["owner_acceptance_eligible"] is False


def test_unqualified_candidate_promotion_fails_closed() -> None:
    input_pack = _input_pack()
    demand = input_pack["cell_inputs"][0]
    candidate_ref = demand["authority_refs"]["candidate_refs_not_evidence"][0]
    demand["authority_refs"]["accepted_evidence_refs"] = [candidate_ref]
    with pytest.raises(
        S3T04ProductSurfaceError,
        match="s3_t04_unqualified_evidence_promotion_detected|"
        "s3_t04_candidate_promoted_without_evidence_gate",
    ):
        materialize_verified_product_surface(
            execution_result=_result(),
            input_pack=input_pack,
        )


def test_numeric_authority_mutation_cannot_be_hidden_by_delivery_renderer() -> None:
    execution = deepcopy(_result())
    numeric = next(
        row["payload"]
        for row in execution["artifacts"]
        if row["artifact_type"] == "bounded_agent_numeric"
    )
    value_projection = numeric["case_numeric_authority_projections"][1]
    value_projection["rows"][1]["exact_value"] = "62.43"
    with pytest.raises(
        S3T04ProductSurfaceError,
        match="s3_t04_source_numeric_rendering_not_authority_bound",
    ):
        materialize_verified_product_surface(
            execution_result=execution,
            input_pack=_input_pack(),
        )


def test_durable_surface_result_is_content_addressed_and_honestly_blocked() -> None:
    result = json.loads(SURFACE_RESULT.read_text(encoding="utf-8"))
    assert result["result_digest"] == canonical_digest(
        {key: value for key, value in result.items() if key != "result_digest"}
    )
    assert result["final_delivery_verification"][
        "final_delivery_preview_digest"
    ] == result["final_delivery_preview"]["final_delivery_preview_digest"]
    assert result["owner_acceptance_eligible"] is False
