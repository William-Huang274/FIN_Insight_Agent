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
from sec_agent.s1_08_query_facet_plan import (  # noqa: E402
    build_query_facet_zero_call_proof,
    compile_query_facet_plans,
    load_query_facet_policy,
)
from sec_agent.s1_08_search_intent_compiler import (  # noqa: E402
    compile_search_intents,
    load_search_intent_policy,
)


POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_unified_query_facet_policy_v1_0.json"
)
OUTPUT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_unified_query_facet_zero_call_proof_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_sha256(path: Path) -> str:
    normalized = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _verify_bound_input(*, ref: str, expected_sha256: str) -> Path:
    path = ROOT / ref
    if not path.is_file() or _normalized_sha256(path) != expected_sha256:
        raise RuntimeError(f"bound_input_drift:{ref}")
    return path


def main() -> int:
    policy = load_query_facet_policy(POLICY_PATH)
    bindings = policy["immutable_inputs"]
    bound_paths = {
        "search_intent_policy": _verify_bound_input(
            ref=bindings["search_intent_policy_ref"],
            expected_sha256=bindings["search_intent_policy_sha256"],
        ),
        "source_catalog": _verify_bound_input(
            ref=bindings["source_catalog_ref"],
            expected_sha256=bindings["source_catalog_sha256"],
        ),
        "model_visible_case_pack": _verify_bound_input(
            ref=bindings["model_visible_case_pack_ref"],
            expected_sha256=bindings["model_visible_case_pack_sha256"],
        ),
        "progression_plan": _verify_bound_input(
            ref=bindings["progression_plan_ref"],
            expected_sha256=bindings["progression_plan_sha256"],
        ),
        "clean_portfolio_proof": _verify_bound_input(
            ref=bindings["clean_portfolio_proof_ref"],
            expected_sha256=bindings["clean_portfolio_proof_sha256"],
        ),
    }
    clean_proof = _load(bound_paths["clean_portfolio_proof"])
    clean_body = dict(clean_proof)
    clean_digest = clean_body.pop("result_digest", "")
    if (
        clean_digest != canonical_digest(clean_body)
        or clean_proof.get("status")
        != "pass_two_clean_archives_two_fresh_processes_zero_call_reproducible"
        or clean_proof.get("decision", {}).get("next_scope")
        != "S1_08_UNIFIED_QUERY_FACET_PLAN_ZERO_CALL_IMPLEMENTATION"
    ):
        raise RuntimeError("clean_portfolio_proof_invalid")
    visible = _load(bound_paths["model_visible_case_pack"])
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    intents = compile_search_intents(
        catalog=load_source_catalog(bound_paths["source_catalog"]),
        policy=load_search_intent_policy(bound_paths["search_intent_policy"]),
        research_objectives=objectives,
    )
    plans = compile_query_facet_plans(intents=intents, policy=policy)
    proof = build_query_facet_zero_call_proof(plans=plans, policy=policy)
    output_body = {
        **proof,
        "policy_digest": canonical_digest(policy),
        "input_file_sha256": {
            key: _normalized_sha256(path)
            for key, path in sorted(bound_paths.items())
        },
        "implementation": {
            "module_ref": "src/sec_agent/s1_08_query_facet_plan.py",
            "materializer_ref": (
                "scripts/releases/materialize_fin_ia_0_1_3_s1_08_"
                "unified_query_facet_zero_call_proof.py"
            ),
            "policy_ref": POLICY_PATH.relative_to(ROOT).as_posix(),
            "model_atoms_supplied": 0,
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
                "plan_count": output["plan_count"],
                "bound_search_intent_count": output["bound_search_intent_count"],
                "proof_digest": output["proof_digest"],
                "output": str(OUTPUT_PATH),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
