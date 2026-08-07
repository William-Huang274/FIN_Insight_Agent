from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs/releases/fin_ia_0_1_3_s2_05_mu_raw_experiment_a_authority_v1_0.json"
ISSUER = ROOT / "scripts/releases/issue_fin_ia_0_1_3_s2_05_mu_raw_admission.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_mu_authority_is_digest_bound_exact_once_and_non_promotable() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    body = {key: value for key, value in decision.items() if key != "decision_digest"}
    assert decision["decision_digest"] == canonical_digest(body)
    authority = decision["authority"]
    assert authority["authorized_case"] == "MU"
    assert authority["maximum_new_admissions"] == 1
    assert authority["maximum_execution_attempts"] == 1
    assert authority["maximum_provider_calls"] == 12
    assert authority["retry_count"] == authority["fallback_count"] == 0
    assert authority["automatic_next_case"] is False
    assert authority["DELL_admission_authorized"] is False
    assert authority["NVDA_admission_authorized"] is False
    assert authority["supervisor_correction_authorized"] is False
    assert authority["business_promotion_authorized"] is False


def test_mu_fairness_guard_keeps_dell_correction_and_hidden_gold_invisible() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    fairness = decision["fairness_guard"]
    assert fairness["same_model_visible_contract_as_DELL"] is True
    assert fairness["model_visible_contract_changed_after_DELL_raw"] is False
    assert fairness["post_hoc_evaluator_changed_model_visible_prompt"] is False
    assert fairness["DELL_correction_visible"] is False
    assert fairness["DELL_raw_output_visible"] is False
    assert fairness["hidden_gold_visible"] is False
    assert fairness["supervisor_prompt_visible"] is False
    assert fairness["MU_model_visible_digest"] == "c11bbfab503026587415f07ff7ba1902b0931e381de28216299a6d39d53f6393"


def test_all_mu_authority_frozen_bindings_match() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    for binding in decision["frozen_bindings"].values():
        assert _sha(ROOT / binding["ref"]) == binding["sha256"]


def test_mu_issuer_targets_only_mu_and_never_reads_correction_runtime() -> None:
    source = ISSUER.read_text(encoding="utf-8")
    assert 'row["case_key"] == "MU"' in source
    assert '"case_key": "MU"' in source
    assert '"MU_RAW"' in source
    assert "fin013_s2_06/DELL" not in source
    assert "hidden_gold_scoring_objects" not in source
    assert "DELL_correction_or_hidden_gold_read" in source
