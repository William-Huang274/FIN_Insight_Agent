from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.s2_context_yield_program import (
    compile_context_yield_program,
    load_context_yield_policy,
)
from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


POLICY = ROOT / "configs" / "runtime" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_context_yield_policy_v1_0.json"
)
S2_DECISION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_01_"
    "research_question_method_contract_translation_v1_0.json"
)
S2_NATURAL_RESULT = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_02_"
    "three_family_natural_canary_result_v1_0.json"
)
OUTPUT = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_"
    "context_yield_and_capacity_zero_call_v1_0.json"
)
PREVIOUS_ACTIVE = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_02_active_test_suite_successor_v1_1.json"
)
ACTIVE = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_active_test_suite_successor_v1_0.json"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    program = compile_context_yield_program(
        policy=load_context_yield_policy(POLICY),
        s2_decision=_load(S2_DECISION),
        natural_result=_load(S2_NATURAL_RESULT),
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(program, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    previous = _load(PREVIOUS_ACTIVE)
    active_body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s2_03_active_test_suite_successor_v1_0",
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S2-03-ACTIVE-SUITE-R12",
        "status": "current_S2_03_zero_call_engineering_pass_natural_reproof_pending",
        "decision_ref": OUTPUT.relative_to(ROOT).as_posix(),
        "decision_sha256": __import__("hashlib").sha256(OUTPUT.read_bytes()).hexdigest(),
        "selected_test_files": [
            *previous["selected_test_files"],
            "tests/contract/test_fin_0_1_3_repair_closeout_s2_03_context_yield_and_capacity.py",
            "tests/contract/test_fin_0_1_3_repair_closeout_s2_03_context_yield_canary_runtime.py",
        ],
        "historical_event_time_deselections": previous[
            "historical_event_time_deselections"
        ],
        "observed_result": "191 passed / 1 historical event-time assertion deselected",
        "stage_boundary": {
            "S1": "pass_closed",
            "S2_01": "engineering_pass",
            "S2_02": "pass_closed",
            "S2_03_zero_call": "engineering_pass",
            "S2_03_natural_reproof": "pending_maximum_one_call",
            "S3_to_S5": "not_started",
            "full_chain_authorized": False,
            "release": False,
        },
    }
    _write(ACTIVE, {**active_body, "suite_digest": canonical_digest(active_body)})
    print(OUTPUT)
    print(ACTIVE)
    print(json.dumps(program["capacity"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
