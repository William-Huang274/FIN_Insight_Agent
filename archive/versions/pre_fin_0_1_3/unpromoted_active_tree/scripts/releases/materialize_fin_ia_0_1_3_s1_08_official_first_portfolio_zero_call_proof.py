from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_08_candidate_generation_runtime import (  # noqa: E402
    load_source_catalog,
)
from sec_agent.s1_08_official_first_portfolio import (  # noqa: E402
    compile_portfolio_route_plan,
    load_portfolio_policy,
    run_portfolio_zero_call_replay,
)
from sec_agent.s1_08_search_intent_compiler import (  # noqa: E402
    compile_search_intents,
    load_search_intent_policy,
)


POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_official_first_portfolio_policy_v1_0.json"
)
VISIBLE_PATH = (
    ROOT
    / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
)
OUTPUT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_official_first_portfolio_zero_call_proof_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    normalized = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _verify_bound_input(*, ref: str, expected_sha256: str) -> Path:
    path = ROOT / ref
    if not path.is_file() or _sha256(path) != expected_sha256:
        raise RuntimeError(f"bound_input_drift:{ref}")
    return path


def main() -> int:
    policy = load_portfolio_policy(POLICY_PATH)
    bindings = policy["immutable_replay_inputs"]
    bound_paths = {
        "firecrawl_result": _verify_bound_input(
            ref=bindings["firecrawl_result_ref"],
            expected_sha256=bindings["firecrawl_result_sha256"],
        ),
        "firecrawl_assessment": _verify_bound_input(
            ref=bindings["firecrawl_assessment_ref"],
            expected_sha256=bindings["firecrawl_assessment_sha256"],
        ),
        "tencent_result": _verify_bound_input(
            ref=bindings["tencent_result_ref"],
            expected_sha256=bindings["tencent_result_sha256"],
        ),
        "tencent_assessment": _verify_bound_input(
            ref=bindings["tencent_assessment_ref"],
            expected_sha256=bindings["tencent_assessment_sha256"],
        ),
        "dell_r2": _verify_bound_input(
            ref=bindings["dell_r2_ref"],
            expected_sha256=bindings["dell_r2_sha256"],
        ),
        "official_source_closeout": _verify_bound_input(
            ref=bindings["official_source_closeout_ref"],
            expected_sha256=bindings["official_source_closeout_sha256"],
        ),
        "search_intent_policy": _verify_bound_input(
            ref=bindings["search_intent_policy_ref"],
            expected_sha256=bindings["search_intent_policy_sha256"],
        ),
        "source_catalog": _verify_bound_input(
            ref=bindings["source_catalog_ref"],
            expected_sha256=bindings["source_catalog_sha256"],
        ),
    }
    decision = policy["decision_binding"]
    decision_path = _verify_bound_input(
        ref=decision["decision_ref"],
        expected_sha256=decision["decision_file_sha256"],
    )
    decision_payload = _load(decision_path)
    if decision_payload.get("decision_digest") != decision["decision_digest"]:
        raise RuntimeError("portfolio_decision_digest_drift")

    # The route plan is compiled before the evaluator-only benchmark pack is used
    # for post-terminal measurement.  Gold locators never enter the plan.
    visible = _load(VISIBLE_PATH)
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    catalog = load_source_catalog(bound_paths["source_catalog"])
    search_policy = load_search_intent_policy(bound_paths["search_intent_policy"])
    intents = compile_search_intents(
        catalog=catalog,
        policy=search_policy,
        research_objectives=objectives,
    )
    route_plan = compile_portfolio_route_plan(intents=intents, policy=policy)
    proof = run_portfolio_zero_call_replay(
        policy=policy,
        route_plan=route_plan,
        firecrawl_result=_load(bound_paths["firecrawl_result"]),
        firecrawl_assessment=_load(bound_paths["firecrawl_assessment"]),
        tencent_result=_load(bound_paths["tencent_result"]),
        tencent_assessment=_load(bound_paths["tencent_assessment"]),
        dell_r2_result=_load(bound_paths["dell_r2"]),
        official_source_closeout=_load(bound_paths["official_source_closeout"]),
    )
    output_body = {
        **proof,
        "policy_digest": canonical_digest(policy),
        "input_file_sha256": {
            key: _sha256(path) for key, path in sorted(bound_paths.items())
        },
        "decision_file_sha256": _sha256(decision_path),
        "implementation": {
            "module_ref": "src/sec_agent/s1_08_official_first_portfolio.py",
            "script_ref": "scripts/releases/materialize_fin_ia_0_1_3_s1_08_official_first_portfolio_zero_call_proof.py",
            "policy_ref": str(POLICY_PATH.relative_to(ROOT)).replace("\\", "/"),
        },
    }
    output_body.pop("proof_digest", None)
    output = {**output_body, "proof_digest": canonical_digest(output_body)}
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "route_plan_digest": output["route_plan_digest"],
                "quality_card_digest": output["search_quality_card"][
                    "quality_card_digest"
                ],
                "proof_digest": output["proof_digest"],
                "output": str(OUTPUT_PATH),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
