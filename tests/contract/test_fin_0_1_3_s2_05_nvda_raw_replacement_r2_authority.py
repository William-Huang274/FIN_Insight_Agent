from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs/releases/fin_ia_0_1_3_s2_05_nvda_raw_replacement_r2_authority_v1_0.json"
ISSUER = ROOT / "scripts/releases/issue_fin_ia_0_1_3_s2_05_nvda_raw_replacement_r2_admission.py"
R1_RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s2_05_nvda_raw_r1_terminal_and_numeric_scale_disposition_v1_0.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_nvda_r2_authority_is_digest_bound_exact_once_and_non_promotable() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    body = {key: value for key, value in decision.items() if key != "decision_digest"}
    assert decision["decision_digest"] == canonical_digest(body)
    authority = decision["authority"]
    assert authority["authorized_case"] == "NVDA"
    assert authority["replacement_ordinal"] == "R2"
    assert authority["maximum_new_admissions"] == 1
    assert authority["maximum_execution_attempts"] == 1
    assert authority["maximum_provider_calls"] == 12
    assert authority["retry_count"] == authority["fallback_count"] == 0
    assert authority["automatic_replacement_or_rerun"] is False
    assert authority["supervisor_correction_authorized"] is False
    assert authority["business_promotion_authorized"] is False


def test_nvda_r2_preserves_blind_contract_and_prior_failure() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    fairness = decision["fairness_guard"]
    replacement = decision["replacement_basis"]
    assert fairness["model_visible_contract_changed_after_R1"] is False
    assert fairness["only_local_change"] == "typed_numeric_scale_equivalent_surface_compiler"
    assert fairness["prior_case_raw_or_correction_visible"] is False
    assert fairness["hidden_gold_visible"] is False
    assert replacement["prior_raw_mutations"] == 0
    assert replacement["prior_admission_reuse_forbidden"] is True
    assert replacement["immutable_lead_replay"] == "pass"


def test_nvda_r2_preserves_execution_time_evaluator_hash_after_post_run_v1_4() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    for name, binding in decision["frozen_bindings"].items():
        if name == "layered_evaluator_repaired":
            continue
        assert _sha(ROOT / binding["ref"]) == binding["sha256"]
    assert decision["frozen_bindings"]["layered_evaluator_repaired"]["sha256"] == (
        "0d3361d87550c4d2a409475d2afc5fdc6ef9065cbb6feb5e06ebd406a71adc80"
    )


def test_nvda_r2_issuer_validates_immutable_r1_and_new_authority() -> None:
    spec = importlib.util.spec_from_file_location("nvda_raw_r2_issuer", ISSUER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._validate_decision(
        json.loads(DECISION.read_text(encoding="utf-8")),
        json.loads(R1_RESULT.read_text(encoding="utf-8")),
    )


def test_nvda_r2_issuer_has_fresh_root_and_no_forbidden_inputs() -> None:
    source = ISSUER.read_text(encoding="utf-8")
    assert 'row["case_key"] == "NVDA"' in source
    assert '"NVDA_RAW_REPLACEMENT_R2"' in source
    assert "NVDA_RAW_REPLACEMENT_R2" not in (
        ROOT / "scripts/releases/issue_fin_ia_0_1_3_s2_05_nvda_raw_admission.py"
    ).read_text(encoding="utf-8")
    assert "hidden_gold_scoring_objects" not in source
    assert "prior_case_raw_correction_or_hidden_gold_read" in source
