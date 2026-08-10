from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s2_fixed_pack_research import (  # noqa: E402
    load_fixed_pack_contract,
    load_fixed_pack_profile,
    materialize_six_case_model_inputs,
)


CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json"
)
PROFILE_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json"
)
DEFAULT_ARTIFACT_ROOT = ROOT / (
    "data/workbench_private/fin_0_1_3_s2_fixed_pack_research/zero-call-r1/objects"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_fixed_pack_model_input_compilation_result_v1_0.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    contract = load_fixed_pack_contract(CONTRACT_PATH, repo_root=ROOT)
    profile = load_fixed_pack_profile(PROFILE_PATH)
    result = materialize_six_case_model_inputs(
        contract=contract,
        profile=profile,
        repo_root=ROOT,
        artifact_root=args.artifact_root,
        output_path=args.output,
    )
    print(result["status"])
    print(result["result_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
