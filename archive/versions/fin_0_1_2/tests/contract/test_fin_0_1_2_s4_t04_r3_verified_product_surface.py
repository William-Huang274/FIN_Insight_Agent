from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s3_t04_product_surface import (  # noqa: E402
    S3T04ProductSurfaceError,
    validate_verified_product_surface,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


RESULT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_r3_"
    "verified_product_surface_and_read_only_assessment_v1_0.json"
)


def _result() -> dict:
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_R3_product_surface_is_content_addressed_and_honestly_bounded() -> None:
    result = _result()
    assert result["record_digest"] == canonical_digest(
        {key: value for key, value in result.items() if key != "record_digest"}
    )
    surface = validate_verified_product_surface(result["product_surface"])
    preview = surface["final_delivery_preview"]
    text = json.dumps(preview, ensure_ascii=False)
    assert surface["status"] == "delivery_and_fixture_qualification_pass"
    assert surface["owner_acceptance_eligible"] is True
    assert surface["fixture_evidence_qualification"][
        "qualified_authority_cells"
    ] == 3
    assert "__company_total__" not in text
    assert "FY2025-FY" not in text
    assert "USD 130497000000 USD" not in text
    assert not any(
        limitation.startswith("Issuer disclosure")
        for limitation in preview["limitations_zh_cn"]
    )
    assert result["read_only_assessment"]["formal_paired_assessment"] == (
        "not_performed"
    )
    assert result["acceptance_boundary"][
        "current_source_grounded_NVDA_R2"
    ] is False


def test_final_preview_mutation_breaks_local_verifier_binding() -> None:
    surface = deepcopy(_result()["product_surface"])
    surface["final_delivery_preview"]["executive_summary_zh_cn"] += "篡改"
    with pytest.raises(
        S3T04ProductSurfaceError,
        match="s3_t04_final_delivery_preview_digest_mismatch|"
        "s3_t04_product_surface_result_digest_mismatch",
    ):
        validate_verified_product_surface(surface)
