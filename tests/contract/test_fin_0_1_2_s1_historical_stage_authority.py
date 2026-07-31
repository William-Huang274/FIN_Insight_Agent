from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sec_agent.runtime_contract_governance import (
    validate_active_test_suite_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
STAGE_PLAN = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_realistic_three_case_"
    "deterministic_vertical_stage_plan_v1_0.json"
)
STAGE_CAPSULE = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_stage_capsule_v1_0.json"
)
PROOF_MANIFEST = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_t03_deterministic_"
    "proof_manifest_v1_0.json"
)
FROZEN_STAGE_PLAN_SHA256 = (
    "a51d241e56417ad6005ca1fecb4495a9b899945d8f50bfb595045934d88a77b7"
)


def test_proof_manifest_and_frozen_stage_authority_are_valid() -> None:
    manifest = json.loads(PROOF_MANIFEST.read_text(encoding="utf-8"))
    validate_active_test_suite_manifest(manifest)
    assert hashlib.sha256(STAGE_PLAN.read_bytes()).hexdigest() == (
        FROZEN_STAGE_PLAN_SHA256
    )
    capsule = json.loads(STAGE_CAPSULE.read_text(encoding="utf-8"))
    assert capsule["immutable_stage_plan"]["sha256"] == (
        FROZEN_STAGE_PLAN_SHA256
    )
    assert not capsule["product_truth"]["DELL_R2"]
    assert not capsule["product_truth"]["MU_R2"]
    assert not capsule["product_truth"]["post_transfer_NVDA_exact_product"]
    assert not capsule["product_truth"]["NVDA_R3"]
