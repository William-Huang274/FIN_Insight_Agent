from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.s2_same_evidence_experiment_runtime import (  # noqa: E402
    SECTION_IDS,
    load_frozen_blind_inputs,
    load_runtime_policy,
)
from sec_agent.s2_same_evidence_layered_evaluation import evaluate_raw_chain  # noqa: E402
from sec_agent.s2_same_evidence_supervision import compile_supervision_boundary  # noqa: E402


def _load_raw_outputs(capture_root: Path) -> dict[str, Any]:
    captures = []
    for path in sorted(capture_root.glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        content = row.get("gateway_result", {}).get("content")
        if not isinstance(content, str):
            raise ValueError(f"capture_content_missing:{path.name}")
        captures.append((row.get("call_index"), row.get("node_type"), json.loads(content)))
    captures.sort(key=lambda row: int(row[0]))
    by_type: dict[str, list[Any]] = {}
    for _, node_type, content in captures:
        by_type.setdefault(str(node_type), []).append(content)
    required_single = ("lead_planning", "cross_cell_synthesis", "writer", "verifier")
    if any(len(by_type.get(node_type, [])) != 1 for node_type in required_single):
        raise ValueError("s2_06_required_single_node_capture_missing")
    specialists = by_type.get("specialist_judgment", [])
    if not 6 <= len(specialists) <= 8:
        raise ValueError("s2_06_specialist_capture_count_invalid")
    if len(captures) != len(specialists) + 4:
        raise ValueError("s2_06_unexpected_capture_type")
    return {
        "lead": by_type["lead_planning"][0],
        "specialists": specialists,
        "synthesis": by_type["cross_cell_synthesis"][0],
        "writer": by_type["writer"][0],
        "verifier": by_type["verifier"][0],
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    terminal_path = args.raw_root / "layered_terminal_result.json"
    capture_root = args.raw_root / "captures"
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    run_id = str(terminal.get("run_id") or "")
    terminal_digest = str(terminal.get("terminal_result_digest") or "")
    case_key = str(terminal.get("case_key") or "")
    if terminal.get("status") != "terminal_completed_layered_raw_evaluation":
        raise ValueError("s2_06_raw_terminal_not_complete")

    policy = load_runtime_policy(ROOT)
    cases = load_frozen_blind_inputs(ROOT, policy)["cases"]
    case_input = next((row for row in cases if row.get("case_key") == case_key), None)
    if not isinstance(case_input, dict):
        raise ValueError("s2_06_case_input_missing")
    evaluation = evaluate_raw_chain(
        _load_raw_outputs(capture_root),
        case_input=case_input,
        policy=policy,
        section_ids=SECTION_IDS,
    )
    boundary = compile_supervision_boundary(
        evaluation,
        raw_run_id=run_id,
        raw_terminal_digest=terminal_digest,
    )
    payload = {
        "schema_version": "fin_ia_0_1_3_s2_06_supervision_materialization_v1_0",
        "case_key": case_key,
        "source_raw_root": str(args.raw_root),
        "model_provider_network_calls": [0, 0, 0],
        "recalibrated_raw_evaluation": evaluation,
        "supervision_boundary": boundary,
    }
    _atomic_write_json(args.output, payload)
    print(json.dumps({
        "status": "materialized_zero_call_supervision_boundary",
        "case_key": case_key,
        "finding_count": evaluation["finding_count"],
        "material_failure": evaluation["material_failure"],
        "correction_count": len(boundary["corrections"]),
        "next_case_may_be_considered_by_separate_authority": boundary["campaign_boundary"]["next_case_may_be_considered_by_separate_authority"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
