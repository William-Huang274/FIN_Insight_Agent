from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_08_external_combined_recovery_assessment import (  # noqa: E402
    assess_external_combined_recovery_live,
)


DEFAULT_RESULT = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_external_combined_live_result_v1_1.json"
)
DEFAULT_RUNTIME = ROOT / ".codex_runtime/fin013_s1_08/external_combined/live-r2"
DEFAULT_VISIBLE = (
    ROOT
    / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
)
DEFAULT_HIDDEN = (
    ROOT
    / "eval_sets/fin_0_1_3_same_evidence_v1/evaluator_only/hidden_gold_scoring_objects_v1.json"
)
DEFAULT_FIRECRAWL = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_assessment_v1_0.json"
)
DEFAULT_TENCENT = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_assessment_v1_0.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_external_combined_recovery_assessment_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--visible", type=Path, default=DEFAULT_VISIBLE)
    parser.add_argument("--hidden", type=Path, default=DEFAULT_HIDDEN)
    parser.add_argument("--firecrawl", type=Path, default=DEFAULT_FIRECRAWL)
    parser.add_argument("--tencent", type=Path, default=DEFAULT_TENCENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("external_combined_recovery_assessment_already_exists")
    assessment = assess_external_combined_recovery_live(
        result=_load(args.result),
        runtime_root=args.runtime_root,
        visible_pack=_load(args.visible),
        hidden_scoring=_load(args.hidden),
        historical_firecrawl_assessment=_load(args.firecrawl),
        historical_tencent_assessment=_load(args.tencent),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(assessment, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": assessment["status"],
                "assessment_digest": assessment["assessment_digest"],
                "runtime_recovery_pass": assessment["runtime_recovery"]["pass"],
                "selected_required_slots": assessment["official_candidate_quality"][
                    "selected_required_slots"
                ],
                "required_external_slots": assessment["official_candidate_quality"][
                    "required_external_slots"
                ],
                "hidden_target_in_pool_recall": assessment[
                    "evaluator_only_candidate_ceiling"
                ]["summary"]["target_in_pool_recall"],
                "next_scope": assessment["stage_disposition"]["next_scope"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
