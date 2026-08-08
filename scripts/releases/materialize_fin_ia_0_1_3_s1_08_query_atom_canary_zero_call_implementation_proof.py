from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_08_candidate_generation_runtime import (  # noqa: E402
    load_source_catalog,
)
from sec_agent.s1_08_query_atom_canary_runtime import (  # noqa: E402
    OUTPUT_SCHEMA,
    S108QueryAtomCanaryError,
    compile_query_atom_request,
    execute_query_atom_canary,
    issue_query_atom_canary_admission,
    load_query_atom_canary_policy,
)
from sec_agent.s1_08_query_facet_plan import (  # noqa: E402
    compile_query_facet_plans,
    load_query_facet_policy,
)
from sec_agent.s1_08_search_intent_compiler import (  # noqa: E402
    compile_search_intents,
    load_search_intent_policy,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


POLICY_REF = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_08_"
    "deepseek_query_atom_canary_policy_v1_0.json"
)
RUNTIME_REF = ROOT / "src/sec_agent/s1_08_query_atom_canary_runtime.py"
RUNNER_REF = ROOT / (
    "scripts/releases/run_fin_ia_0_1_3_s1_08_"
    "deepseek_query_atom_canary.py"
)
OUTPUT_REF = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_query_atom_canary_"
    "zero_call_implementation_proof_v1_0.json"
)
PROOF_SCHEMA = (
    "fin_ia_0_1_3_s1_08_query_atom_canary_"
    "zero_call_implementation_proof_v1_0"
)
RUN_SCOPE = "S1_08_QUERY_FACET_THREE_WAY_DELL_MU_NVDA_EVALUATION"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("query_atom_proof_object_required")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _verify_inputs(policy: Mapping[str, Any]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for key, ref in policy["immutable_inputs"].items():
        if not key.endswith("_ref"):
            continue
        stem = key.removesuffix("_ref")
        path = ROOT / str(ref)
        if not path.is_file() or _sha(path) != policy["immutable_inputs"][
            f"{stem}_sha256"
        ]:
            raise RuntimeError("query_atom_proof_bound_input_drift:" + stem)
        paths[stem] = path
    return paths


def _admission(
    *, policy: Mapping[str, Any], request: Mapping[str, Any], nonce: str
) -> dict[str, Any]:
    return issue_query_atom_canary_admission(
        execution_git_commit="a" * 40,
        runner_sha256="b" * 64,
        runtime_module_sha256="c" * 64,
        policy_sha256="d" * 64,
        authority_decision_digest="e" * 64,
        request=request,
        issued_at="2026-08-08T12:00:00+00:00",
        expires_at="2026-08-08T14:00:00+00:00",
        run_nonce=nonce,
        credential_present=True,
        policy=policy,
    )


def _fake_result(output: Mapping[str, Any]) -> dict[str, Any]:
    content = json.dumps(output, ensure_ascii=False)
    return {
        "status": "ok",
        "content": content,
        "message": {
            "content": content,
            "reasoning_content": "private-reasoning-must-not-persist",
        },
        "raw_response": {
            "choices": [
                {
                    "message": {
                        "content": content,
                        "reasoning_details": "private-details-must-not-persist",
                    }
                }
            ]
        },
        "finish_reason": "stop",
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
        "transport_attempt_count": 1,
        "latency_ms": 5,
    }


def _execute_fake(
    *,
    admission: Mapping[str, Any],
    output: Mapping[str, Any],
    root: Path,
    ledger: SharedAdmissionConsumptionLedger,
    request: Mapping[str, Any],
    policy: Mapping[str, Any],
    intents: Any,
    facet_policy: Mapping[str, Any],
) -> dict[str, Any]:
    def provider_call(**kwargs: Any) -> dict[str, Any]:
        if kwargs.get("max_transport_attempts") != 1:
            raise RuntimeError("fake_transport_attempt_budget_drift")
        return _fake_result(output)

    return execute_query_atom_canary(
        admission=admission,
        request=request,
        policy=policy,
        intents=intents,
        query_facet_policy=facet_policy,
        execution_git_commit="a" * 40,
        runner_sha256="b" * 64,
        runtime_module_sha256="c" * 64,
        policy_sha256="d" * 64,
        runtime_root=root,
        shared_ledger=ledger,
        provider_call=provider_call,
        observed_at="2026-08-08T12:01:00+00:00",
    )


def main() -> int:
    policy = load_query_atom_canary_policy(POLICY_REF)
    paths = _verify_inputs(policy)
    three_way = _load(paths["three_way_zero_call_proof"])
    three_way_body = dict(three_way)
    three_way_digest = str(three_way_body.pop("evaluation_digest", ""))
    if (
        three_way_digest != canonical_digest(three_way_body)
        or three_way.get("status")
        != "zero_call_A_B_pass_model_atom_observation_pending"
    ):
        raise RuntimeError("query_atom_proof_three_way_basis_invalid")

    visible = _load(paths["model_visible_case_pack"])
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    facet_policy = load_query_facet_policy(paths["query_facet_policy"])
    intents = compile_search_intents(
        catalog=load_source_catalog(paths["source_catalog"]),
        policy=load_search_intent_policy(paths["search_intent_policy"]),
        research_objectives=objectives,
    )
    base_plans = compile_query_facet_plans(
        intents=intents,
        policy=facet_policy,
    )
    base_rows = [row.as_dict() for row in base_plans]
    if base_rows != _load(paths["query_facet_proof"]).get("plans"):
        raise RuntimeError("query_atom_proof_base_plan_drift")
    request = compile_query_atom_request(
        policy=policy,
        query_facet_plans=base_rows,
        research_objectives=objectives,
    )
    first = request["plans"][0]
    valid_atom = {
        "case_key": first["case_key"],
        "evidence_slot_id": first["evidence_slot_id"],
        "evidence_owner_entity_key": first["evidence_owner_entity_key"],
        "language": "en",
        "atom_kind": "metric",
        "value": "remaining performance obligations",
    }
    valid_output = {"schema_version": OUTPUT_SCHEMA, "atoms": [valid_atom]}
    empty_output = {"schema_version": OUTPUT_SCHEMA, "atoms": []}
    invalid_output = {
        "schema_version": OUTPUT_SCHEMA,
        "atoms": [{**valid_atom, "value": "FY2028 demand"}],
    }

    with TemporaryDirectory(prefix="fin013_s1_08_query_atom_proof_") as temp:
        temp_root = Path(temp)
        ledger = SharedAdmissionConsumptionLedger(temp_root / "shared/ledger.sqlite")
        success_admission = _admission(
            policy=policy,
            request=request,
            nonce="zero-call-success",
        )
        success = _execute_fake(
            admission=success_admission,
            output=valid_output,
            root=temp_root / "success",
            ledger=ledger,
            request=request,
            policy=policy,
            intents=intents,
            facet_policy=facet_policy,
        )
        capture = _load(temp_root / "success" / success["capture_ref"])
        capture_text = json.dumps(capture, ensure_ascii=False)
        capture_sanitized = not any(
            value in capture_text
            for value in (
                "reasoning_content",
                "reasoning_details",
                "private-reasoning-must-not-persist",
                "private-details-must-not-persist",
            )
        )
        duplicate_blocked = False
        try:
            _execute_fake(
                admission=success_admission,
                output=empty_output,
                root=temp_root / "duplicate",
                ledger=ledger,
                request=request,
                policy=policy,
                intents=intents,
                facet_policy=facet_policy,
            )
        except SharedAdmissionLedgerError as exc:
            duplicate_blocked = str(exc).startswith(
                "shared_admission_already_consumed"
            )

        empty = _execute_fake(
            admission=_admission(
                policy=policy,
                request=request,
                nonce="zero-call-empty",
            ),
            output=empty_output,
            root=temp_root / "empty",
            ledger=ledger,
            request=request,
            policy=policy,
            intents=intents,
            facet_policy=facet_policy,
        )
        invalid = _execute_fake(
            admission=_admission(
                policy=policy,
                request=request,
                nonce="zero-call-invalid",
            ),
            output=invalid_output,
            root=temp_root / "invalid",
            ledger=ledger,
            request=request,
            policy=policy,
            intents=intents,
            facet_policy=facet_policy,
        )

    if not (
        success["status"] == "terminal_succeeded_exact_once"
        and success["accepted_atom_count"] == 1
        and success["runtime_activation"] is False
        and empty["status"] == "terminal_succeeded_exact_once"
        and empty["accepted_atom_count"] == 0
        and invalid["status"] == "terminal_failed_no_retry"
        and str(invalid["terminal_code"]).endswith(
            "model_atom_authority_violation"
        )
        and capture_sanitized
        and duplicate_blocked
    ):
        raise RuntimeError("query_atom_proof_fake_runtime_gate_failed")

    implementation_paths = {
        "runtime_module": RUNTIME_REF,
        "runner": RUNNER_REF,
        "policy": POLICY_REF,
        "materializer": Path(__file__).resolve(),
    }
    body = {
        "schema_version": PROOF_SCHEMA,
        "contract_ref": "fin_0_1_3.S1_08.deepseek_query_atom_canary:v1",
        "run_scope": RUN_SCOPE,
        "status": "zero_call_implementation_pass_live_authority_pending",
        "three_way_zero_call_evaluation_digest": three_way_digest,
        "request_contract": {
            "request_digest": request["request_digest"],
            "visible_plan_count": len(request["plans"]),
            "visible_language": "en",
            "maximum_atoms": policy["selection_contract"]["maximum_atoms"],
            "maximum_atoms_per_plan": policy["selection_contract"][
                "maximum_atoms_per_plan"
            ],
            "hidden_target_or_URL_leak_count": 0,
        },
        "fake_runtime_proof": {
            "valid_atom_terminal": success["status"],
            "valid_atom_count": success["accepted_atom_count"],
            "empty_abstention_terminal": empty["status"],
            "empty_atom_count": empty["accepted_atom_count"],
            "invalid_authority_atom_terminal": invalid["status"],
            "invalid_authority_atom_code": invalid["terminal_code"],
            "duplicate_admission_blocked": duplicate_blocked,
            "private_reasoning_stripped_from_capture": capture_sanitized,
            "full_visible_request_captured": (
                capture["model_visible_request"] == request
            ),
            "assistant_content_captured_before_validation": bool(
                capture["gateway_result"].get("content")
            ),
            "credential_or_authorization_value_saved": capture[
                "credential_or_authorization_value_saved"
            ],
            "business_evidence_or_fact_authority": capture[
                "business_evidence_or_fact_authority"
            ],
            "retry_count": success["retry_count"],
            "runtime_activation": success["runtime_activation"],
        },
        "implementation_binding": {
            key + "_ref": path.relative_to(ROOT).as_posix()
            for key, path in implementation_paths.items()
        }
        | {
            key + "_sha256_normalized": _sha(path)
            for key, path in implementation_paths.items()
        },
        "observed_calls": {
            "real_provider": 0,
            "network": 0,
            "natural_model": 0,
            "document_fetch": 0,
            "retrieval": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
            "fake_provider_invocations": 3,
        },
        "stage_acceptance": {
            "raw_vs_local_zero_call_A_B": True,
            "query_atom_canary_implementation": True,
            "natural_model_atom_observation": False,
            "three_way_effectiveness_evaluation": False,
            "combined_external_live": False,
            "internal_retrieval": False,
            "BGE_fusion_rerank": False,
            "S1_08": False,
            "release": False,
        },
        "decision": {
            "next": "bounded_deepseek_query_atom_canary_clean_authority_decision",
            "provider_call_authorized_by_this_proof": False,
            "automatic_runtime_activation": False,
            "internal_retrieval_and_BGE_rerank_backlog_preserved": True,
        },
        "known_boundary": (
            "This proof exercises the exact-once query-atom runtime only with local "
            "fake provider outputs. It does not qualify DeepSeek, prove incremental "
            "candidate recall, execute external or internal retrieval, admit BGE or "
            "reranking, promote Evidence, close S1-08 or release the product."
        ),
    }
    output = {**body, "proof_digest": canonical_digest(body)}
    OUTPUT_REF.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "visible_plan_count": output["request_contract"][
                    "visible_plan_count"
                ],
                "valid_atom_terminal": success["status"],
                "empty_atom_terminal": empty["status"],
                "invalid_atom_terminal": invalid["status"],
                "duplicate_admission_blocked": duplicate_blocked,
                "proof_digest": output["proof_digest"],
                "next": output["decision"]["next"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except S108QueryAtomCanaryError as exc:
        raise SystemExit(exc.code) from exc
