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
    compile_query_facet_plans,
    load_query_facet_policy,
)
from sec_agent.s1_08_query_facet_three_way_evaluation import (  # noqa: E402
    build_three_way_zero_call_evaluation,
    load_three_way_policy,
)
from sec_agent.s1_08_search_intent_compiler import (  # noqa: E402
    compile_search_intents,
    load_search_intent_policy,
)


POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_query_facet_three_way_evaluation_policy_v1_0.json"
)
OUTPUT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_query_facet_three_way_zero_call_proof_v1_0.json"
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
    policy = load_three_way_policy(POLICY_PATH)
    bound_paths = {
        key.removesuffix("_ref"): _verify_bound_input(
            ref=value,
            expected_sha256=policy["immutable_inputs"][
                f"{key.removesuffix('_ref')}_sha256"
            ],
        )
        for key, value in policy["immutable_inputs"].items()
        if key.endswith("_ref")
    }
    proof = _load(bound_paths["query_facet_proof"])
    facet_policy = load_query_facet_policy(bound_paths["query_facet_policy"])
    visible = _load(bound_paths["model_visible_case_pack"])
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    facet_bindings = facet_policy["immutable_inputs"]
    search_policy_path = _verify_bound_input(
        ref=facet_bindings["search_intent_policy_ref"],
        expected_sha256=facet_bindings["search_intent_policy_sha256"],
    )
    source_catalog_path = _verify_bound_input(
        ref=facet_bindings["source_catalog_ref"],
        expected_sha256=facet_bindings["source_catalog_sha256"],
    )
    intents = compile_search_intents(
        catalog=load_source_catalog(source_catalog_path),
        policy=load_search_intent_policy(search_policy_path),
        research_objectives=objectives,
    )
    current_plans = compile_query_facet_plans(
        intents=intents,
        policy=facet_policy,
    )
    permuted_plans = compile_query_facet_plans(
        intents=tuple(reversed(intents)),
        policy=facet_policy,
    )
    current_rows = [row.as_dict() for row in current_plans]
    permuted_rows = [row.as_dict() for row in permuted_plans]
    permutation_stable = current_rows == permuted_rows
    if current_rows != proof.get("plans"):
        raise RuntimeError("query_facet_proof_runtime_projection_drift")
    evaluation = build_three_way_zero_call_evaluation(
        policy=policy,
        query_facet_proof=proof,
        model_visible_case_pack=visible,
        firecrawl_result=_load(bound_paths["firecrawl_result"]),
        firecrawl_assessment=_load(bound_paths["firecrawl_assessment"]),
        firecrawl_scoring=_load(bound_paths["firecrawl_scoring"]),
        deterministic_permutation_stable=permutation_stable,
    )
    output_body = {
        **evaluation,
        "policy_digest": canonical_digest(policy),
        "input_file_sha256": {
            key: _normalized_sha256(path)
            for key, path in sorted(bound_paths.items())
        },
        "deterministic_recompilation": {
            "normal_plan_set_digest": canonical_digest(current_rows),
            "reversed_input_plan_set_digest": canonical_digest(permuted_rows),
            "byte_equal": permutation_stable,
        },
        "implementation": {
            "module_ref": (
                "src/sec_agent/s1_08_query_facet_three_way_evaluation.py"
            ),
            "materializer_ref": (
                "scripts/releases/materialize_fin_ia_0_1_3_s1_08_"
                "query_facet_three_way_zero_call_proof.py"
            ),
            "policy_ref": POLICY_PATH.relative_to(ROOT).as_posix(),
            "natural_model_atoms_supplied": 0,
        },
    }
    output_body.pop("evaluation_digest", None)
    output = {**output_body, "evaluation_digest": canonical_digest(output_body)}
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "raw_mean_facet_coverage": output["variant_summary"][
                    "user_raw_query"
                ]["mean_facet_coverage"],
                "local_mean_facet_coverage": output["variant_summary"][
                    "deterministic_local_compiler"
                ]["mean_facet_coverage"],
                "local_addressability": output[
                    "english_target_addressability_proxy"
                ]["variant_summary"]["deterministic_local_compiler"][
                    "addressable"
                ],
                "next": output["decision"]["next"],
                "evaluation_digest": output["evaluation_digest"],
                "output": str(OUTPUT_PATH),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
