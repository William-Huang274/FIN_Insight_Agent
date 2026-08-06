from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for value in (ROOT, ROOT / "src"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from sec_agent.s2_shared_benchmark_evidence import (  # noqa: E402
    compile_shared_benchmark_evidence_freeze,
)


OUTPUT_DIR = ROOT / "eval_sets" / "fin_0_1_3_same_evidence_v1"
OUTPUTS = {
    "visible_pack": OUTPUT_DIR / "model_visible" / "shared_benchmark_evidence_pack_v1.json",
    "blind_inputs": OUTPUT_DIR / "model_visible" / "experiment_a_blind_inputs_v1.json",
    "hidden_scoring": OUTPUT_DIR / "evaluator_only" / "hidden_gold_scoring_objects_v1.json",
    "manifest": ROOT / "configs" / "releases" / "fin_ia_0_1_3_s2_04_shared_benchmark_evidence_freeze_v1_0.json",
}


def main() -> None:
    bundle = compile_shared_benchmark_evidence_freeze()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for key, path in OUTPUTS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(bundle[key], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"status": "materialized", "outputs": {key: str(path) for key, path in OUTPUTS.items()}, "counts": bundle["manifest"]["observed_counts"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
