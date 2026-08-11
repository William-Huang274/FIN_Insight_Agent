from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.s1_08_agentic_search_quality_program import (  # noqa: E402
    compile_s1_08_entry_audit,
    load_s1_08_policy,
)


POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_agentic_search_quality_evaluation_policy_v1_0.json"
FREEZE = ROOT / "configs/releases/fin_ia_0_1_3_s2_04_shared_benchmark_evidence_freeze_v1_0.json"
VISIBLE = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
HIDDEN = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/evaluator_only/hidden_gold_scoring_objects_v1.json"
GOVERNED = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"
SOURCE_RUNTIME = ROOT / "configs/releases/fin_ia_0_1_3_s1_07_current_source_canary_result_v1_3.json"
OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_agentic_search_entry_and_candidate_ceiling_audit_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    result = compile_s1_08_entry_audit(
        policy=load_s1_08_policy(POLICY),
        freeze=_load(FREEZE),
        visible_pack=_load(VISIBLE),
        hidden_scoring=_load(HIDDEN),
        governed_pack_result=_load(GOVERNED),
        source_runtime_result=_load(SOURCE_RUNTIME),
    )
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
