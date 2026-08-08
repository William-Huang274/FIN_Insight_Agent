from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_08_external_combined_live import (  # noqa: E402
    EXACT_LIVE_SCOPE,
    S108ExternalCombinedError,
    compile_external_combined_plan,
    execute_external_combined,
    issue_external_combined_admission,
    load_bound_inputs,
    load_external_combined_policy,
    sha256_file,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


DEFAULT_POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_external_combined_live_policy_v1_0.json"
DEFAULT_PLAN = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_external_combined_plan_v1_0.json"
DEFAULT_PROOF = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_external_combined_live_zero_call_proof_v1_0.json"


class _UnusedTransport:
    live_network = False


def _authority() -> dict[str, Any]:
    body = {
        "schema_version": "fin_ia_0_1_3_s1_08_external_combined_fake_authority_v1_0",
        "status": "approved_one_external_combined_exact_live",
        "exact_live_authority": {
            "scope": EXACT_LIVE_SCOPE,
            "maximum_admissions": 1,
            "maximum_executions": 1,
            "network_call_ceiling": 72,
            "retry_ceiling": 0,
            "model_call_ceiling": 0,
        },
        "fake_only": True,
    }
    return {**body, "authority_digest": canonical_digest(body)}


def _fake_official(**values: Any) -> dict[str, Any]:
    return {
        "case_key": values["case_key"],
        "status": "completed",
        "terminal_code": "full_fake_official_case_complete",
        "candidate_result": {
            "terminal_status": "complete",
            "accepted_candidates": [],
            "typed_gaps": [],
        },
        "network_calls": 2,
        "document_fetches": 1,
        "bound_query_receipts": [
            {
                "query_facet_plan_digest": row["plan_digest"],
                "case_key": row["case_key"],
                "evidence_slot_id": row["evidence_slot_id"],
            }
            for row in values["plan_rows"]
        ],
    }


def _firecrawl_ok(_endpoint: str, request: bytes, _timeout: int) -> tuple[int, bytes]:
    query = json.loads(request.decode("utf-8"))["query"]
    payload = {
        "success": True,
        "id": canonical_digest(query)[:16],
        "creditsUsed": 1,
        "data": {
            "web": [
                {
                    "url": "https://example.com/" + canonical_digest(query)[:16],
                    "title": query[:100],
                    "description": "full-fake candidate locator",
                    "position": 1,
                }
            ]
        },
    }
    return 200, json.dumps(payload).encode("utf-8")


def _fake_admission(policy: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    return issue_external_combined_admission(
        policy=policy,
        plan=plan,
        authority=_authority(),
        execution_git_commit="a" * 40,
        runner_sha256="b" * 64,
        runtime_module_sha256="c" * 64,
        policy_sha256="d" * 64,
        zero_call_proof_sha256="e" * 64,
        issued_at="2026-08-09T00:00:00Z",
        expires_at="2026-08-10T00:00:00Z",
        run_nonce="zero-call-full-fake",
    )


def _execute_fake(
    *,
    root: Path,
    policy: Mapping[str, Any],
    bound_inputs: Mapping[str, Mapping[str, Any]],
    plan: Mapping[str, Any],
    firecrawl_call=_firecrawl_ok,
) -> dict[str, Any]:
    return execute_external_combined(
        admission=_fake_admission(policy, plan),
        policy=policy,
        plan=plan,
        catalog=bound_inputs["source_catalog"],
        execution_git_commit="a" * 40,
        runner_sha256="b" * 64,
        runtime_module_sha256="c" * 64,
        policy_sha256="d" * 64,
        runtime_root=root / "runtime",
        shared_ledger=SharedAdmissionConsumptionLedger(root / "ledger.json"),
        official_transport=_UnusedTransport(),
        firecrawl_call=firecrawl_call,
        official_lane_executor=_fake_official,
        observed_at="2026-08-09T01:00:00Z",
    )


def materialize(*, policy_path: Path, plan_path: Path, proof_path: Path) -> dict[str, Any]:
    policy = load_external_combined_policy(policy_path)
    bound_inputs = load_bound_inputs(repo_root=ROOT, policy=policy)
    plan = compile_external_combined_plan(policy=policy, bound_inputs=bound_inputs)

    with TemporaryDirectory(prefix="fin013-s1-08-external-combined-") as directory:
        temp = Path(directory)
        full_fake = _execute_fake(
            root=temp / "full-fake",
            policy=policy,
            bound_inputs=bound_inputs,
            plan=plan,
        )

        systemic_calls = 0

        def systemic_rejection(*_args: Any) -> tuple[int, bytes]:
            nonlocal systemic_calls
            systemic_calls += 1
            return 403, b'{"message":"forbidden"}'

        systemic = _execute_fake(
            root=temp / "systemic",
            policy=policy,
            bound_inputs=bound_inputs,
            plan=plan,
            firecrawl_call=systemic_rejection,
        )
        raw_before_parse = _execute_fake(
            root=temp / "parse-failure",
            policy=policy,
            bound_inputs=bound_inputs,
            plan=plan,
            firecrawl_call=lambda *_: (200, b"not-json"),
        )
        first_parse_failure = raw_before_parse["firecrawl_shadow_results"][0]
        raw_path = (
            temp
            / "parse-failure/runtime/firecrawl-shadow"
            / first_parse_failure["capture_refs"]["raw_response"]
        )
        raw_response_saved_before_parse_failure = raw_path.is_file()

    mutation_results: dict[str, str] = {}
    for name, input_key, field, value in (
        ("model_variant_activation", "query_atom_result", "status", "accepted"),
        ("facet_plan_loss", "query_facet_proof", "plan_count", 35),
        ("stage_order_drift", "progression_plan", "status", "internal_started_early"),
    ):
        mutated = deepcopy(bound_inputs)
        mutated[input_key][field] = value
        try:
            compile_external_combined_plan(policy=policy, bound_inputs=mutated)
        except S108ExternalCombinedError as exc:
            mutation_results[name] = exc.code
        else:
            raise AssertionError(f"mutation did not fail closed: {name}")

    if (
        full_fake["status"] != "completed"
        or len(full_fake["official_case_results"]) != 3
        or len(full_fake["firecrawl_shadow_results"]) != 24
        or full_fake["observed_counts"]["model_calls"] != 0
        or full_fake["observed_counts"]["evidence_promotions"] != 0
        or systemic_calls != 1
        or len(systemic["firecrawl_shadow_results"]) != 24
        or raw_before_parse["status"] != "completed_with_typed_failures"
        or not raw_response_saved_before_parse_failure
    ):
        raise AssertionError("external combined zero-call proof acceptance failed")

    _write(plan_path, plan)
    proof_body = {
        "schema_version": "fin_ia_0_1_3_s1_08_external_combined_live_zero_call_proof_v1_0",
        "contract_ref": "fin_0_1_3.S1_08.external_official_firecrawl_shadow_combined:v1",
        "run_scope": (
            "S1_08_OFFICIAL_ROUTES_PLUS_FIRECRAWL_SHADOW_COMBINED_LIVE_"
            "ZERO_CALL_IMPLEMENTATION_AND_AUTHORITY_DECISION"
        ),
        "status": "zero_call_engineering_pass_authority_not_yet_issued",
        "plan_digest": plan["plan_digest"],
        "plan_sha256": sha256_file(plan_path),
        "policy_sha256": sha256_file(policy_path),
        "source_bindings": {
            "runtime_module_sha256": sha256_file(
                ROOT / "src/sec_agent/s1_08_external_combined_live.py"
            ),
            "exact_live_runner_sha256": sha256_file(
                ROOT / "scripts/releases/run_fin_ia_0_1_3_s1_08_external_combined_live.py"
            ),
            "materializer_sha256": sha256_file(Path(__file__).resolve()),
        },
        "acceptance": {
            "official_query_facet_plans": 18,
            "shadow_query_facet_plans": 24,
            "required_case_slot_opportunities": 12,
            "full_fake_official_cases_terminalized": 3,
            "full_fake_shadow_queries_terminalized": 24,
            "systemic_rejection_network_calls": systemic_calls,
            "systemic_rejection_shadow_identities_terminalized": 24,
            "raw_response_saved_before_parse_failure": True,
            "model_atoms_accepted": 0,
            "reranker_rescue": False,
            "evidence_promotion": False,
            "internal_retrieval_executed": False,
        },
        "mutation_results": mutation_results,
        "simulated_topology_counts": full_fake["observed_counts"],
        "observed_real_calls": {
            "provider": 0,
            "network": 0,
            "model": 0,
            "document_fetch": 0,
            "evidence_promotion": 0,
            "embedding": 0,
            "rerank": 0,
        },
        "authority_state": "not_issued_requires_clean_commit_and_fresh_preflight",
        "known_boundary": (
            "This proves the combined exact-once topology and failure semantics with "
            "local fakes. It does not establish fresh source recall, candidate quality, "
            "Evidence quality, internal retrieval, ranking, downstream research quality, "
            "S1-08 acceptance or release readiness."
        ),
    }
    proof = {**proof_body, "proof_digest": canonical_digest(proof_body)}
    _write(proof_path, proof)
    return proof


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--proof", type=Path, default=DEFAULT_PROOF)
    args = parser.parse_args()
    proof = materialize(
        policy_path=args.policy,
        plan_path=args.plan,
        proof_path=args.proof,
    )
    print(
        json.dumps(
            {
                "status": proof["status"],
                "plan_digest": proof["plan_digest"],
                "proof_digest": proof["proof_digest"],
                "observed_real_calls": proof["observed_real_calls"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
