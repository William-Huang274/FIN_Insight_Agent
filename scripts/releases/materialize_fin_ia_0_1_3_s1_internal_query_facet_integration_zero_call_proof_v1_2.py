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
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_internal_query_facet_integration import (  # noqa: E402
    build_internal_query_facet_zero_call_proof,
    compile_internal_query_facet_requests,
    load_internal_query_facet_policy,
)


RUN_SCOPE = "S1_INTERNAL_BGE_FUSION_AND_RERANK_EVALUATION"
POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "query_facet_integration_policy_v1_2.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_"
    "query_facet_integration_zero_call_proof_v1_2.json"
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("internal_query_facet_v1_2_object_required")
    return value


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("internal_query_facet_v1_2_proof_already_exists")
    policy = load_internal_query_facet_policy(POLICY_PATH)
    bindings = dict(policy["immutable_inputs"])
    stems = (
        "query_facet_proof",
        "query_facet_policy",
        "progression_plan",
        "external_closeout",
        "retrieval_config",
        "milvus_runtime",
        "dense_resource_qualification",
    )
    bound_paths = {}
    for stem in stems:
        path = ROOT / str(bindings[f"{stem}_ref"])
        if (
            not path.is_file()
            or _normalized_sha256(path) != bindings[f"{stem}_sha256"]
        ):
            raise RuntimeError(f"internal_query_facet_v1_2_binding_drift:{stem}")
        bound_paths[stem] = path
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError("internal_query_facet_v1_2_project_os_preflight_blocked")
    bundles, requests = compile_internal_query_facet_requests(
        query_facet_proof=_load(bound_paths["query_facet_proof"]),
        policy=policy,
    )
    proof = build_internal_query_facet_zero_call_proof(
        bundles=bundles,
        requests=requests,
        policy=policy,
    )
    dense_requests = [
        request
        for request in proof["requests"]
        if request["route_id"] == "internal_milvus_dense"
    ]
    if not dense_requests or any(
        request["typed_filters"]["years"]
        != request["typed_filters"]["reporting_fiscal_years"]
        for request in dense_requests
    ):
        raise RuntimeError("internal_query_facet_v1_2_milvus_period_mapping_invalid")
    body = dict(proof)
    body.pop("proof_digest", None)
    body.update(
        {
            "policy_digest": canonical_digest(policy),
            "supersedes_ref": (
                "configs/releases/fin_ia_0_1_3_s1_internal_query_facet_"
                "integration_zero_call_proof_v1_1.json"
            ),
            "correction_reason": (
                "Milvus field fiscal_year stores reporting fiscal year. The v1.1 "
                "request incorrectly supplied filing calendar year, which would "
                "exclude current FY2027 vectors published in calendar 2026."
            ),
            "input_file_sha256": {
                key: _normalized_sha256(path)
                for key, path in sorted(bound_paths.items())
            },
            "project_os_preflight": {
                "status": preflight["status"],
                "run_scope": preflight["run_scope"],
            },
            "implementation": {
                "module_ref": "src/sec_agent/s1_internal_query_facet_integration.py",
                "materializer_ref": (
                    "scripts/releases/materialize_fin_ia_0_1_3_s1_internal_"
                    "query_facet_integration_zero_call_proof_v1_2.py"
                ),
                "policy_ref": POLICY_PATH.relative_to(ROOT).as_posix(),
            },
        }
    )
    output = {**body, "proof_digest": canonical_digest(body)}
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "dense_requests": len(dense_requests),
                "nvda_reporting_fy2027": sum(
                    request["case_key"] == "NVDA"
                    and 2027 in request["typed_filters"]["years"]
                    for request in dense_requests
                ),
                "proof_digest": output["proof_digest"],
                "output": OUTPUT_PATH.as_posix(),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
