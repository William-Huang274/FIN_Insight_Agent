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
    RUN_SCOPE,
    build_internal_query_facet_zero_call_proof,
    compile_internal_query_facet_requests,
    load_internal_query_facet_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "query_facet_integration_policy_v1_1.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_"
    "query_facet_integration_zero_call_proof_v1_1.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _verify_bound_input(*, ref: str, expected_sha256: str) -> Path:
    path = ROOT / ref
    if not path.is_file() or _normalized_sha256(path) != expected_sha256:
        raise RuntimeError(f"bound_input_drift:{ref}")
    return path


def main() -> int:
    policy = load_internal_query_facet_policy(POLICY_PATH)
    bindings = policy["immutable_inputs"]
    stems = (
        "query_facet_proof",
        "query_facet_policy",
        "progression_plan",
        "external_closeout",
        "retrieval_config",
        "milvus_runtime",
    )
    bound_paths = {
        stem: _verify_bound_input(
            ref=bindings[f"{stem}_ref"],
            expected_sha256=bindings[f"{stem}_sha256"],
        )
        for stem in stems
    }
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") not in {"pass", "blocked"}:
        raise RuntimeError("internal_query_facet_project_os_preflight_invalid")
    source_proof = _load(bound_paths["query_facet_proof"])
    bundles, requests = compile_internal_query_facet_requests(
        query_facet_proof=source_proof,
        policy=policy,
    )
    proof = build_internal_query_facet_zero_call_proof(
        bundles=bundles,
        requests=requests,
        policy=policy,
    )
    body = {
        **proof,
        "policy_digest": canonical_digest(policy),
        "supersedes_observation": (
            "configs/releases/fin_ia_0_1_3_s1_internal_candidate_"
            "inventory_observation_v1_0.json"
        ),
        "correction_reason": (
            "The first inventory observation exposed that reporting fiscal year "
            "and document filing calendar year were conflated. This successor "
            "separates their typed authority before another candidate observation."
        ),
        "input_file_sha256": {
            key: _normalized_sha256(path)
            for key, path in sorted(bound_paths.items())
        },
        "project_os_preflight": {
            "status": str(preflight["status"]),
            "run_scope": str(preflight["run_scope"]),
            "registry_version": str(preflight.get("registry_version") or ""),
        },
        "implementation": {
            "module_ref": "src/sec_agent/s1_internal_query_facet_integration.py",
            "materializer_ref": (
                "scripts/releases/materialize_fin_ia_0_1_3_s1_internal_"
                "query_facet_integration_zero_call_proof_v1_1.py"
            ),
            "policy_ref": POLICY_PATH.relative_to(ROOT).as_posix(),
        },
    }
    body.pop("proof_digest", None)
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
                "bilingual_bundle_count": output["bilingual_bundle_count"],
                "physical_request_count": output["physical_request_count"],
                "proof_digest": output["proof_digest"],
                "output": str(OUTPUT_PATH),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
