from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.public_context_source import (  # noqa: E402
    compile_public_context_candidate,
    compile_public_html_source_object,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.source_use_policy import SourceUsePolicy  # noqa: E402


def _resolve(path_value: str) -> Path:
    path = Path(path_value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compile_plan(plan: dict) -> dict:
    if not (
        plan.get("schema_version")
        == "fin_ia_s1_public_context_admission_plan_v1_0"
        and plan.get("status") == "bounded_free_public_context_admission_plan"
        and plan.get("case_key")
        and plan.get("research_as_of")
        and isinstance(plan.get("sources"), list)
        and plan["sources"]
        and isinstance(plan.get("candidate_specs"), list)
    ):
        raise ValueError("public_context_admission_plan_invalid")
    policy = SourceUsePolicy.from_mapping(
        _load(_resolve(str(plan["source_use_policy_ref"])))
    )
    source_objects: list[dict] = []
    by_source_id: dict[str, dict] = {}
    capture_receipts: list[dict] = []
    for source_spec in plan["sources"]:
        capture_result_ref = str(source_spec["capture_result_ref"])
        result = _load(_resolve(capture_result_ref))
        matches = [
            row
            for row in result.get("sources") or ()
            if row.get("route_id") == source_spec.get("route_id")
        ]
        if len(matches) != 1 or matches[0].get("status") != "captured":
            raise ValueError("public_context_capture_route_not_successful")
        capture_row = matches[0]
        response_ref = capture_row["response_capture"]
        response_path = _resolve(str(response_ref["object_ref"]))
        response_capture = _load(response_path)
        source = compile_public_html_source_object(
            response_capture=response_capture,
            source_spec=source_spec,
            capture_ref=str(response_ref["object_ref"]),
            capture_sha256=str(response_ref["sha256"]),
        )
        source_id = str(source["source_id"])
        if source_id in by_source_id:
            raise ValueError("public_context_source_id_duplicate")
        by_source_id[source_id] = source
        source_objects.append(source)
        capture_receipts.append(
            {
                "source_id": source_id,
                "route_id": source_spec["route_id"],
                "capture_result_ref": capture_result_ref,
                "capture_attempt_id": result.get("attempt_id"),
                "response_capture_ref": response_ref["object_ref"],
                "response_capture_sha256": response_ref["sha256"],
                "body_sha256": capture_row.get("body_sha256"),
                "source_object_digest": source["source_object_digest"],
            }
        )

    candidates: list[dict] = []
    for spec in plan["candidate_specs"]:
        source_id = str(spec.get("source_id") or "")
        if source_id not in by_source_id:
            raise ValueError("public_context_candidate_source_unknown")
        candidates.append(
            compile_public_context_candidate(
                source_object=by_source_id[source_id],
                candidate_spec=spec,
                source_use_policy=policy,
            )
        )
    body = {
        "schema_version": "fin_ia_s1_public_context_admission_result_v1_0",
        "status": "public_context_candidates_compiled_evidence_admission_pending",
        "case_key": str(plan["case_key"]).upper(),
        "research_as_of": str(plan["research_as_of"]),
        "plan_digest": canonical_digest(plan),
        "source_use_policy_id": policy.policy_id,
        "capture_receipts": capture_receipts,
        "source_objects": source_objects,
        "candidates": candidates,
        "summary": {
            "source_count": len(source_objects),
            "candidate_count": len(candidates),
            "admission_ready_candidate_count": sum(
                row["evidence_admission_required"] is True for row in candidates
            ),
            "policy_rejected_candidate_count": sum(
                row["source_use_decision"]["evidence_promotion_allowed"] is False
                for row in candidates
            ),
            "evidence_promoted_count": 0,
            "model_calls": 0,
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "human_or_independent_evaluator_admission_required": True,
            "source_object_contains_no_target_numeric_authority": True,
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile captured public HTML into source-use-gated context candidates."
        )
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compile_plan(_load(args.plan.resolve()))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"result_digest={result['result_digest']}")
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
