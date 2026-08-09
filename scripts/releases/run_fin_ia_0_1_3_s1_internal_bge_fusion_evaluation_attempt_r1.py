from __future__ import annotations

import json
from pathlib import Path
import sys
import traceback
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_internal_bge_fusion_evaluation import (  # noqa: E402
    RESULT_SCHEMA,
    execute_internal_bge_fusion_evaluation,
    load_internal_bge_fusion_evaluation_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "bge_fusion_evaluation_policy_v1_0.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_"
    "bge_fusion_evaluation_attempt_r1.json"
)


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def _progress(message: str) -> None:
    print(json.dumps({"progress": message}, ensure_ascii=False), flush=True)


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("internal_bge_fusion_attempt_r1_already_exists")
    policy = load_internal_bge_fusion_evaluation_policy(
        POLICY_PATH, repo_root=ROOT
    )
    try:
        result = execute_internal_bge_fusion_evaluation(
            policy=policy,
            repo_root=ROOT,
            progress=_progress,
        )
    except Exception as exc:
        body = {
            "schema_version": (
                "fin_ia_0_1_3_s1_internal_bge_fusion_"
                "evaluation_failure_envelope_v1_0"
            ),
            "result_schema_expected": RESULT_SCHEMA,
            "attempt_id": str(policy["attempt_id"]),
            "status": "terminal_failed_no_automatic_retry",
            "failure_phase": "local_embedding_or_milvus_ranking_execution",
            "error_type": type(exc).__name__,
            "error_code": str(exc)[:500],
            "traceback_tail": traceback.format_exc()[-4000:],
            "observed_counts": "not_asserted_after_exception",
            "automatic_retry": False,
            "replacement_attempt_authorized": False,
            "candidates_promoted_to_evidence": False,
            "current_quarter_exact_sql": "0_of_6_open",
            "external_official_required_slot_coverage": (
                "4_of_12_open_release_blocker"
            ),
        }
        failure = {**body, "failure_digest": canonical_digest(body)}
        _write_atomic(OUTPUT_PATH, failure)
        print(json.dumps(failure, ensure_ascii=False), flush=True)
        return 4
    _write_atomic(OUTPUT_PATH, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "attempt_id": result["attempt_id"],
                "metrics": {
                    key: value["metrics"]
                    for key, value in result["evaluation"].items()
                },
                "adoption_decision": result["adoption_decision"],
                "runtime_efficiency": result["runtime_efficiency"],
                "result_digest": result["result_digest"],
                "output": OUTPUT_PATH.as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
