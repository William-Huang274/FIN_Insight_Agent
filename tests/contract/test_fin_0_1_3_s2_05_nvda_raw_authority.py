from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs/releases/fin_ia_0_1_3_s2_05_nvda_raw_experiment_a_authority_v1_0.json"
ISSUER = ROOT / "scripts/releases/issue_fin_ia_0_1_3_s2_05_nvda_raw_admission.py"
DELL_RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s2_05_dell_layered_replacement_exact_live_result_v1_0.json"
MU_RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s2_05_mu_raw_exact_live_and_s2_06_boundary_result_v1_0.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_nvda_authority_is_digest_bound_exact_once_and_non_promotable() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    body = {key: value for key, value in decision.items() if key != "decision_digest"}
    assert decision["decision_digest"] == canonical_digest(body)
    authority = decision["authority"]
    assert authority["authorized_case"] == "NVDA"
    assert authority["maximum_new_admissions"] == 1
    assert authority["maximum_execution_attempts"] == 1
    assert authority["maximum_provider_calls"] == 12
    assert authority["retry_count"] == authority["fallback_count"] == 0
    assert authority["automatic_next_case"] is False
    assert authority["DELL_admission_authorized"] is False
    assert authority["MU_admission_authorized"] is False
    assert authority["supervisor_correction_authorized"] is False
    assert authority["business_promotion_authorized"] is False


def test_nvda_fairness_guard_keeps_prior_cases_and_hidden_gold_invisible() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    fairness = decision["fairness_guard"]
    assert fairness["same_model_visible_contract_as_DELL_and_MU"] is True
    assert fairness["model_visible_contract_changed_after_DELL_and_MU_raw"] is False
    assert fairness["post_hoc_evaluator_changed_model_visible_prompt"] is False
    assert fairness["DELL_or_MU_correction_visible"] is False
    assert fairness["DELL_or_MU_raw_output_visible"] is False
    assert fairness["hidden_gold_visible"] is False
    assert fairness["supervisor_prompt_visible"] is False
    assert fairness["NVDA_model_visible_digest"] == (
        "454227271c5b6c96f95ab17413747d6cc9f395429465e6cac663bdeabdcf81c5"
    )


def test_all_nvda_authority_frozen_bindings_match() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    for binding in decision["frozen_bindings"].values():
        assert _sha(ROOT / binding["ref"]) == binding["sha256"]


def test_nvda_issuer_targets_only_nvda_and_never_reads_correction_runtime() -> None:
    source = ISSUER.read_text(encoding="utf-8")
    assert 'row["case_key"] == "NVDA"' in source
    assert '"case_key": "NVDA"' in source
    assert '"NVDA_RAW"' in source
    assert "fin013_s2_06/DELL" not in source
    assert "fin013_s2_06/MU" not in source
    assert "hidden_gold_scoring_objects" not in source
    assert "DELL_or_MU_correction_raw_or_hidden_gold_read" in source


def test_nvda_issuer_accepts_distinct_dell_and_mu_historical_result_shapes() -> None:
    spec = importlib.util.spec_from_file_location("nvda_raw_issuer", ISSUER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._validate_decision(
        json.loads(DECISION.read_text(encoding="utf-8")),
        json.loads(DELL_RESULT.read_text(encoding="utf-8")),
        json.loads(MU_RESULT.read_text(encoding="utf-8")),
    )
