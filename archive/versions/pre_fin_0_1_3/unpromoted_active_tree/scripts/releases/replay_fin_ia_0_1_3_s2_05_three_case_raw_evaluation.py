from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s2_same_evidence_experiment_runtime import (  # noqa: E402
    SECTION_IDS,
    load_frozen_blind_inputs,
    load_runtime_policy,
)
from sec_agent.s2_same_evidence_layered_evaluation import evaluate_raw_chain  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay immutable complete S2-05 raw captures through the current evaluator"
    )
    parser.add_argument(
        "--case-run",
        action="append",
        required=True,
        metavar="CASE=RUN_ROOT",
        help="Case key and immutable run root; repeat for each case",
    )
    args = parser.parse_args()

    policy = load_runtime_policy(ROOT)
    cases = {
        str(row["case_key"]): row
        for row in load_frozen_blind_inputs(ROOT, policy)["cases"]
    }
    results: dict[str, Any] = {}
    for item in args.case_run:
        case_key, separator, raw_path = item.partition("=")
        if not separator or case_key not in cases:
            raise RuntimeError("experiment_a_replay_case_run_invalid")
        run_root = Path(raw_path).resolve()
        outputs, capture_count = _load_outputs(run_root, case_key)
        evaluation = evaluate_raw_chain(
            outputs,
            case_input=cases[case_key],
            policy=policy,
            section_ids=SECTION_IDS,
        )
        counts = {
            severity: sum(
                1 for row in evaluation["findings"] if row["severity"] == severity
            )
            for severity in ("L1", "L2", "L3", "L4")
        }
        results[case_key] = {
            "run_root": run_root.relative_to(ROOT).as_posix(),
            "capture_count": capture_count,
            "raw_output_digest": canonical_digest(outputs),
            "evaluator_schema_version": evaluation["schema_version"],
            "raw_chain_complete": evaluation["raw_chain_complete"],
            "material_failure": evaluation["material_failure"],
            "finding_count": evaluation["finding_count"],
            "severity_counts": counts,
            "finding_codes": [row["code"] for row in evaluation["findings"]],
            "evaluation_digest": canonical_digest(evaluation),
        }
    body = {
        "schema_version": "fin_ia_0_1_3_s2_05_three_case_raw_evaluator_replay_v1_0",
        "model_provider_network_calls": [0, 0, 0],
        "raw_mutations": 0,
        "results": results,
    }
    print(json.dumps({**body, "replay_digest": canonical_digest(body)}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _load_outputs(run_root: Path, case_key: str) -> tuple[dict[str, Any], int]:
    captures = sorted((run_root / "raw_model_only" / "captures").glob("*.json"))
    outputs: dict[str, Any] = {"specialists": []}
    for path in captures:
        capture = json.loads(path.read_text(encoding="utf-8"))
        if capture.get("case_key") != case_key:
            raise RuntimeError("experiment_a_replay_cross_case_capture")
        content = json.loads(capture["gateway_result"]["content"])
        node_type = capture.get("node_type")
        if node_type == "lead_planning":
            outputs["lead"] = content
        elif node_type == "specialist_judgment":
            outputs["specialists"].append(content)
        elif node_type == "cross_cell_synthesis":
            outputs["synthesis"] = content
        elif node_type in {"writer", "verifier"}:
            outputs[str(node_type)] = content
        else:
            raise RuntimeError("experiment_a_replay_unknown_node_type")
    return outputs, len(captures)


if __name__ == "__main__":
    raise SystemExit(main())
