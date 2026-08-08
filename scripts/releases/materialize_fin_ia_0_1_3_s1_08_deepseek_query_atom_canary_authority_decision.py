from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


RUNNER_REF = ROOT / (
    "scripts/releases/run_fin_ia_0_1_3_s1_08_"
    "deepseek_query_atom_canary.py"
)
RUNTIME_REF = ROOT / "src/sec_agent/s1_08_query_atom_canary_runtime.py"
POLICY_REF = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_08_"
    "deepseek_query_atom_canary_policy_v1_0.json"
)
PROOF_REF = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_query_atom_canary_"
    "zero_call_implementation_proof_v1_0.json"
)
OUTPUT_REF = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_deepseek_query_atom_"
    "canary_authority_decision_v1_0.json"
)
SCHEMA = (
    "fin_ia_0_1_3_s1_08_deepseek_query_atom_"
    "canary_authority_decision_v1_0"
)
RUN_SCOPE = "S1_08_QUERY_FACET_DEEPSEEK_ATOM_CANARY_EXACT_LIVE_EXECUTION"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("query_atom_authority_json_object_required")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("query_atom_authority_git_failure:" + ":".join(args))
    return result.stdout.strip()


def _runner_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "fin013_s1_08_query_atom_canary_runner",
        RUNNER_REF,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("query_atom_authority_runner_import_failure")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if _git("status", "--porcelain"):
        raise RuntimeError("query_atom_authority_repository_not_clean")
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise RuntimeError("query_atom_authority_repository_not_synced")

    runner = _runner_module()
    material = runner.build_material()
    proof = _load(PROOF_REF)
    proof_body = dict(proof)
    proof_digest = str(proof_body.pop("proof_digest", ""))
    if (
        proof_digest != canonical_digest(proof_body)
        or proof.get("status")
        != "zero_call_implementation_pass_live_authority_pending"
        or proof.get("decision", {}).get(
            "provider_call_authorized_by_this_proof"
        )
        is not False
    ):
        raise RuntimeError("query_atom_authority_implementation_proof_invalid")

    proof_bindings = proof.get("implementation_binding") or {}
    expected_proof_bindings = {
        "runtime_module_sha256_normalized": _sha(RUNTIME_REF),
        "runner_sha256_normalized": _sha(RUNNER_REF),
        "policy_sha256_normalized": _sha(POLICY_REF),
    }
    if any(
        proof_bindings.get(key) != value
        for key, value in expected_proof_bindings.items()
    ):
        raise RuntimeError("query_atom_authority_implementation_proof_drift")

    implementation_binding = {
        "runner_ref": RUNNER_REF.relative_to(ROOT).as_posix(),
        "runner_sha256_normalized": _sha(RUNNER_REF),
        "runtime_module_ref": RUNTIME_REF.relative_to(ROOT).as_posix(),
        "runtime_module_sha256_normalized": _sha(RUNTIME_REF),
        "policy_ref": POLICY_REF.relative_to(ROOT).as_posix(),
        "policy_sha256_normalized": _sha(POLICY_REF),
        "request_digest": material["request"]["request_digest"],
        "three_way_evaluation_digest": material[
            "three_way_evaluation_digest"
        ],
        "query_facet_plan_set_digest": material[
            "query_facet_plan_set_digest"
        ],
    }
    body = {
        "schema_version": SCHEMA,
        "contract_ref": "fin_0_1_3.S1_08.deepseek_query_atom_canary:v1",
        "recorded_at": "2026-08-09",
        "status": "one_bounded_deepseek_query_atom_canary_authorized",
        "run_scope": RUN_SCOPE,
        "implementation_commit": head,
        "basis": {
            "zero_call_implementation_proof_ref": PROOF_REF.relative_to(
                ROOT
            ).as_posix(),
            "zero_call_implementation_proof_digest": proof_digest,
            "raw_local_zero_call_AB_status": (
                "pass_structural_addressability_not_live_recall"
            ),
            "natural_model_atom_observed": False,
            "historical_provider_pool_attributable_to_new_variants": False,
        },
        "implementation_binding": implementation_binding,
        "authority": {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "visible_language": "en",
            "visible_typed_plan_count": 18,
            "provider_call_ceiling": 1,
            "transport_attempt_ceiling": 1,
            "retry_count": 0,
            "fallback_count": 0,
            "maximum_output_tokens": 2200,
            "maximum_atoms": 18,
            "maximum_atoms_per_plan": 1,
            "empty_atom_set_allowed": True,
            "fresh_admission_required": True,
            "credential_presence_required_at_admission": True,
            "credential_value_may_be_persisted": False,
            "full_visible_request_and_assistant_output_capture_required": True,
            "provider_private_reasoning_may_be_persisted": False,
            "document_fetches": 0,
            "retrieval_calls": 0,
            "embedding_calls": 0,
            "rerank_calls": 0,
            "evidence_promotions": 0,
            "automatic_runtime_activation": False,
            "automatic_combined_live": False,
            "automatic_internal_retrieval": False,
        },
        "terminal_disposition": {
            "valid_or_empty_atom_output": (
                "preserve_capture_compile_locally_and_materialize_three_way_"
                "evaluation_without_runtime_activation"
            ),
            "invalid_schema_or_authority_violation": (
                "terminal_fail_no_retry_preserve_capture_reject_model_variant"
            ),
            "provider_or_transport_failure": (
                "terminal_fail_no_retry_no_replacement_in_this_authority"
            ),
        },
        "calls_executed_by_this_decision": {
            "provider": 0,
            "network": 0,
            "model": 0,
            "document_fetch": 0,
            "retrieval": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "stage_acceptance": {
            "query_atom_canary_implementation": True,
            "query_atom_canary_authority": True,
            "natural_model_atom_observation": False,
            "three_way_effectiveness_evaluation": False,
            "combined_external_live": False,
            "internal_retrieval": False,
            "BGE_fusion_rerank": False,
            "S1_08": False,
            "release": False,
        },
        "decision": {
            "next": "issue_fresh_admission_then_execute_once",
            "internal_retrieval_and_BGE_rerank_backlog_preserved": True,
        },
        "known_boundary": (
            "This decision authorizes one query-atom observation only. It does not "
            "qualify DeepSeek, activate model-assisted queries, execute external or "
            "internal retrieval, admit BGE/reranking, promote Evidence, close S1-08 "
            "or release the product."
        ),
    }
    output = {**body, "decision_digest": canonical_digest(body)}
    OUTPUT_REF.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "implementation_commit": head,
                "provider_call_ceiling": 1,
                "retry_count": 0,
                "automatic_runtime_activation": False,
                "decision_digest": output["decision_digest"],
                "next": output["decision"]["next"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
