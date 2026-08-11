from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_residual_gap_external_readjudication import (  # noqa: E402
    load_inputs,
    readjudicate_external_capture,
    write_readjudication_result,
)


DEFAULT_EXTERNAL = ROOT / "configs/releases/fin_ia_0_1_3_s1_residual_gap_external_live_result_v1_0.json"
DEFAULT_LOCAL_PACK = ROOT / "configs/releases/fin_ia_0_1_3_s1_six_case_local_evidence_pack_result_v1_0.json"
DEFAULT_PLAN = ROOT / "configs/releases/fin_ia_0_1_3_s1_residual_gap_external_priority_plan_v1_0.json"
DEFAULT_PRIVATE_ROOT = ROOT / ".codex_runtime/fin013_s1_residual_gap_external_live/r1/objects"
DEFAULT_OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_s1_residual_gap_external_readjudication_v1_0.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external-result", type=Path, default=DEFAULT_EXTERNAL)
    parser.add_argument("--local-pack-result", type=Path, default=DEFAULT_LOCAL_PACK)
    parser.add_argument("--priority-plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--private-object-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    external, local_pack, plan = load_inputs(
        external_result_path=args.external_result,
        local_pack_result_path=args.local_pack_result,
        priority_plan_path=args.priority_plan,
    )
    result = readjudicate_external_capture(
        external_result=external,
        local_pack_result=local_pack,
        priority_plan=plan,
        private_object_root=args.private_object_root,
    )
    write_readjudication_result(result, args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "result_digest": result["result_digest"],
                "observed_counts": result["observed_counts"],
                "successor_pack_decision": result["successor_pack_decision"]["mode"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
