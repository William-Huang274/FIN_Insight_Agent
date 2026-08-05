from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "releases")]

from materialize_fin_ia_0_1_2_s4_t05_c_mu_current_evidence_and_agent_input import (  # noqa: E402
    LIVE_RESULT_REF,
    T05CMUMaterializationError,
    build_materialization,
    compile_outputs,
    load_and_validate_terminal,
)


def test_current_mu_search_compiles_exact_evidence_and_agent_input() -> None:
    pack, agent, result = build_materialization(
        recorded_at="2026-08-05T06:20:00Z",
        live_result_path=ROOT / LIVE_RESULT_REF,
    )
    assert [len(pack["evidence_rows"]), len(pack["numeric_rows"]), len(pack["typed_gaps"])] == [15, 3, 3]
    assert agent["company"] == "MU"
    assert agent["case_id"].startswith("fin012-s4-t05-mu-current-evidence-")
    assert result["evidence_gate"]["rejected_candidate_promoted"] is False
    assert result["known_quality_boundary"]["generic_AI_segment_gap_code_used_for_MU_HBM_scope"] is True


def test_cross_case_terminal_and_numeric_mutation_fail_closed(tmp_path: Path) -> None:
    terminal, digest, _ = load_and_validate_terminal(ROOT / LIVE_RESULT_REF)
    wrong = copy.deepcopy(terminal)
    wrong["case_key"] = "DELL"
    path = tmp_path / "terminal.json"
    path.write_text(json.dumps(wrong), encoding="utf-8")
    live = json.loads((ROOT / LIVE_RESULT_REF).read_text(encoding="utf-8"))
    live["terminal"]["runtime_object_ref"] = path.as_posix()
    live_path = tmp_path / "live.json"
    live_path.write_text(json.dumps(live), encoding="utf-8")
    with pytest.raises(T05CMUMaterializationError):
        load_and_validate_terminal(live_path)

    pack, agent = compile_outputs(terminal, terminal_digest=digest)
    mutated = copy.deepcopy(pack)
    mutated["numeric_rows"][0]["value"] = "999999"
    with pytest.raises(Exception):
        from apps.workbench.backend.application.fin_0_1_2_s4_t05_three_case_transfer import validate_transfer_evidence_pack
        validate_transfer_evidence_pack(mutated, case_key="MU")
    assert agent["company"] == "MU"
