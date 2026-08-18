from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPOSITION = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_hidden_reference_disclosure_disposition_v1_0.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_disclosed_hidden_references_are_preserved_but_not_qualification_eligible() -> None:
    value = json.loads(DISPOSITION.read_text(encoding="utf-8"))
    assert value["status"] == "existing_hidden_references_ineligible_for_blind_qualification"
    assert value["incident"]["candidate_or_result_execution_performed"] is False
    assert value["incident"]["code_or_threshold_tuned_from_hidden_labels"] is False
    for binding in value["contaminated_assets"]:
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert _sha256(path) == binding["sha256"]
        assert binding["qualification_eligible"] is False
    assert value["authority"]["existing_test_frozen_execution_authorized"] is False
    assert value["authority"]["existing_holdout_execution_authorized"] is False


def test_ordinary_search_and_successor_storage_contract_exclude_hidden_labels() -> None:
    ignore = (ROOT / ".rgignore").read_text(encoding="utf-8")
    assert "eval_sets/fin_0_1_3_s1/references/test_frozen/" in ignore
    assert "eval_sets/fin_0_1_3_s1/references/holdout_heterogeneous/" in ignore
    value = json.loads(DISPOSITION.read_text(encoding="utf-8"))
    successor = value["successor_isolation_contract"]
    assert successor["new_hidden_labels_must_be_git_tracked"] is False
    assert successor["independent_adjudication_required"] is True
    assert successor["implementing_agent_must_not_receive_expected_outcomes_before_candidate_freeze"] is True
