from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s4_t05_current_case_product_surface import (  # noqa: E402
    S4T05CurrentCaseProductSurfaceError,
    materialize_current_case_verified_product_surface,
    validate_current_case_pair_readiness,
    validate_current_case_verified_product_surface,
)
from apps.workbench.backend.application.fin_0_1_2_s3_t04_product_surface import (  # noqa: E402
    S3T04ProductSurfaceError,
)
from scripts.releases.materialize_fin_ia_0_1_2_s4_t05_c_mu_verified_product_surface_and_paired_readiness import (  # noqa: E402
    BASELINE_RESULT,
    DEFAULT_OUTPUT,
    EXACT_RESULT,
    EXPECTED_RESULT_SHA256,
    materialize,
)
from scripts.releases.materialize_fin_ia_0_1_2_s4_t05_c_mu_agent_exact_live_result_and_assessment import (  # noqa: E402
    AGENT_INPUT,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_mu_surface_materializes_without_rerunning_exact_live() -> None:
    before = hashlib.sha256(EXACT_RESULT.read_bytes()).hexdigest()
    baseline, record = materialize()
    assert record == _load(DEFAULT_OUTPUT)
    assert baseline == _load(BASELINE_RESULT)
    assert before == EXPECTED_RESULT_SHA256
    assert hashlib.sha256(EXACT_RESULT.read_bytes()).hexdigest() == before
    assert record["paired_readiness"]["status"] == (
        "ready_for_formal_paired_assessment"
    )
    assert record["acceptance_boundary"]["MU_current_R2"] is False
    assert record["observed_counts"]["new_model_calls"] == 0
    assert record["observed_counts"]["exact_live_reruns"] == 0


def test_mu_preview_is_normalized_localized_and_digest_bound() -> None:
    record = _load(DEFAULT_OUTPUT)
    surface = validate_current_case_verified_product_surface(
        record["product_surface"], expected_case_ticker="MU"
    )
    preview = surface["final_delivery_preview"]
    verifier = surface["final_delivery_verification"]
    text = json.dumps(preview, ensure_ascii=False, sort_keys=True)
    assert "__company_total__" not in text
    assert "FY2025-FY" not in text
    assert re.search(r"\b(USD|EUR|CNY)\s+[0-9,.]+\s+\1\b", text) is None
    assert not any(
        row.startswith("Issuer disclosure")
        for row in preview["limitations_zh_cn"]
    )
    assert preview["case_ticker"] == "MU"
    assert verifier["bound_case_ticker"] == "MU"
    assert verifier["final_delivery_preview_digest"] == preview[
        "final_delivery_preview_digest"
    ]
    assert surface["fixture_evidence_qualification"][
        "qualified_evidence_cells"
    ] == 3
    assert surface["fixture_evidence_qualification"][
        "qualified_authority_cells"
    ] == 3


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("input_company", "case_or_input_identity_mismatch"),
        ("manifest_case", "case_or_input_identity_mismatch"),
        ("workpaper_case", "artifact_case_identity_mismatch"),
        ("numeric_case", "numeric_case_identity_mismatch"),
        ("artifact_input_digest", "artifact_input_digest_mismatch"),
        ("runtime_case", "runtime_case_identity_mismatch"),
    ],
)
def test_mu_cross_case_and_lineage_mutations_fail_closed(
    mutation: str, error: str
) -> None:
    exact = _load(EXACT_RESULT)
    input_pack = _load(AGENT_INPUT)
    artifacts = {row["artifact_type"]: row["payload"] for row in exact["artifacts"]}
    if mutation == "input_company":
        input_pack["company"] = "DELL"
    elif mutation == "manifest_case":
        artifacts["bounded_agent_manifest"]["case_ticker"] = "NVDA"
    elif mutation == "workpaper_case":
        artifacts["bounded_agent_workpaper"]["entity_label"] = "DELL"
    elif mutation == "numeric_case":
        artifacts["bounded_agent_numeric"]["case_numeric_authority_projections"][
            1
        ]["rows"][0]["entity_ref"] = "NVDA"
    elif mutation == "artifact_input_digest":
        artifacts["bounded_agent_evidence"]["input_digest"] = "mutated"
    elif mutation == "runtime_case":
        artifacts["bounded_agent_report"]["s4_case_runtime"][
            "case_ticker"
        ] = "DELL"
    with pytest.raises(S4T05CurrentCaseProductSurfaceError, match=error):
        materialize_current_case_verified_product_surface(
            execution_result=exact,
            input_pack=input_pack,
            expected_case_ticker="MU",
        )


def test_mu_preview_and_verifier_mutations_break_binding() -> None:
    surface = deepcopy(_load(DEFAULT_OUTPUT)["product_surface"])
    surface["final_delivery_preview"]["sections"][0]["claims"][0][
        "rendered_text_zh_cn"
    ] += "突变"
    with pytest.raises(S3T04ProductSurfaceError, match="result_digest_mismatch"):
        validate_current_case_verified_product_surface(
            surface, expected_case_ticker="MU"
        )

    surface = deepcopy(_load(DEFAULT_OUTPUT)["product_surface"])
    preview = surface["final_delivery_preview"]
    preview_body = {
        key: value
        for key, value in preview.items()
        if key != "final_delivery_preview_digest"
    }
    preview["case_ticker"] = "DELL"
    preview_body["case_ticker"] = "DELL"
    preview["final_delivery_preview_digest"] = canonical_digest(preview_body)
    surface["result_digest"] = canonical_digest(
        {key: value for key, value in surface.items() if key != "result_digest"}
    )
    with pytest.raises(S3T04ProductSurfaceError, match="preview_digest_mismatch"):
        validate_current_case_verified_product_surface(
            surface, expected_case_ticker="MU"
        )


def test_mu_pair_mutation_cannot_become_ready() -> None:
    baseline, record = materialize()
    changed = deepcopy(baseline)
    changed["input_head_digest"] = "mutated"
    changed["result_digest"] = canonical_digest(
        {key: value for key, value in changed.items() if key != "result_digest"}
    )
    with pytest.raises(
        S4T05CurrentCaseProductSurfaceError, match="pair_input_binding_mismatch"
    ):
        validate_current_case_pair_readiness(
            exact_result=_load(EXACT_RESULT),
            baseline_result=changed,
            surface_result=record["product_surface"],
            expected_case_ticker="MU",
        )
