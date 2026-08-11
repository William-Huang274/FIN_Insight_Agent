from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs/releases/fin_ia_0_1_3_s2_05_dell_layered_replacement_exact_live_authority_v1_0.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_authority_is_digest_bound_one_dell_exact_once_and_non_promotable() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    body = {key: value for key, value in decision.items() if key != "decision_digest"}
    assert decision["decision_digest"] == canonical_digest(body)
    authority = decision["authority"]
    assert authority["authorized_case"] == "DELL"
    assert authority["maximum_new_admissions"] == 1
    assert authority["maximum_execution_attempts"] == 1
    assert authority["maximum_provider_calls"] == 12
    assert authority["retry_count"] == authority["fallback_count"] == 0
    assert authority["automatic_second_replacement"] is False
    assert authority["MU_admission_authorized"] is False
    assert authority["NVDA_admission_authorized"] is False
    assert authority["business_promotion_authorized"] is False


def test_all_frozen_bindings_match_the_current_successor_slice() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    for binding in decision["frozen_bindings"].values():
        assert _sha(ROOT / binding["ref"]) == binding["sha256"]


def test_authorized_entrypoint_calls_layered_successor() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    entrypoint = ROOT / decision["frozen_bindings"]["production_entrypoint"]["ref"]
    source = entrypoint.read_text(encoding="utf-8")
    assert "execute_case_layered(" in source
    assert "result = execute_case(" not in source
