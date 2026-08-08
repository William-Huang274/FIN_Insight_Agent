from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_08_candidate_generation_runtime import (  # noqa: E402
    load_source_catalog,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_08_query_atom_canary_runtime import (  # noqa: E402
    OUTPUT_SCHEMA,
    S108QueryAtomCanaryError,
    compile_query_atom_request,
    execute_query_atom_canary,
    issue_query_atom_canary_admission,
    load_query_atom_canary_policy,
    validate_and_compile_query_atom_output,
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
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402


CANARY_POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_08_"
    "deepseek_query_atom_canary_policy_v1_0.json"
)
FACET_POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_08_unified_query_facet_policy_v1_0.json"
)
VISIBLE_PATH = ROOT / (
    "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/"
    "shared_benchmark_evidence_pack_v1.json"
)
IMPLEMENTATION_PROOF_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_query_atom_canary_"
    "zero_call_implementation_proof_v1_0.json"
)
AUTHORITY_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_deepseek_query_atom_"
    "canary_authority_decision_v1_0.json"
)
RUNNER_PATH = ROOT / (
    "scripts/releases/run_fin_ia_0_1_3_s1_08_"
    "deepseek_query_atom_canary.py"
)
ISSUED_AT = "2026-08-08T12:00:00+00:00"
OBSERVED_AT = "2026-08-08T12:01:00+00:00"
EXPIRES_AT = "2026-08-08T14:00:00+00:00"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()


def _runner_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "fin013_query_atom_runner_test",
        RUNNER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def material() -> dict[str, Any]:
    canary_policy = load_query_atom_canary_policy(CANARY_POLICY_PATH)
    facet_policy = load_query_facet_policy(FACET_POLICY_PATH)
    bindings = facet_policy["immutable_inputs"]
    visible = _load(VISIBLE_PATH)
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    intents = compile_search_intents(
        catalog=load_source_catalog(ROOT / bindings["source_catalog_ref"]),
        policy=load_search_intent_policy(
            ROOT / bindings["search_intent_policy_ref"]
        ),
        research_objectives=objectives,
    )
    base_plans = compile_query_facet_plans(
        intents=intents,
        policy=facet_policy,
    )
    request = compile_query_atom_request(
        policy=canary_policy,
        query_facet_plans=[row.as_dict() for row in base_plans],
        research_objectives=objectives,
    )
    return {
        "policy": canary_policy,
        "facet_policy": facet_policy,
        "intents": intents,
        "base_plans": base_plans,
        "request": request,
    }


def _atom_for_first_plan(material: dict[str, Any]) -> dict[str, str]:
    row = material["request"]["plans"][0]
    return {
        "case_key": row["case_key"],
        "evidence_slot_id": row["evidence_slot_id"],
        "evidence_owner_entity_key": row["evidence_owner_entity_key"],
        "language": "en",
        "atom_kind": "metric",
        "value": "remaining performance obligations",
    }


def _output(*atoms: dict[str, str]) -> dict[str, Any]:
    return {"schema_version": OUTPUT_SCHEMA, "atoms": list(atoms)}


def _admission(material: dict[str, Any], *, nonce: str) -> dict[str, Any]:
    return issue_query_atom_canary_admission(
        execution_git_commit="a" * 40,
        runner_sha256="b" * 64,
        runtime_module_sha256="c" * 64,
        policy_sha256="d" * 64,
        authority_decision_digest="e" * 64,
        request=material["request"],
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
        run_nonce=nonce,
        credential_present=True,
        policy=material["policy"],
    )


def _execute(
    material: dict[str, Any],
    *,
    tmp_path: Path,
    admission: dict[str, Any],
    provider_output: dict[str, Any],
    ledger: SharedAdmissionConsumptionLedger | None = None,
    runtime_name: str = "run",
) -> dict[str, Any]:
    def fake_provider(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["max_transport_attempts"] == 1
        assert kwargs["enable_thinking"] is False
        return {
            "status": "ok",
            "content": json.dumps(provider_output),
            "message": {
                "content": json.dumps(provider_output),
                "reasoning_content": "must-not-be-saved",
            },
            "raw_response": {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(provider_output),
                            "reasoning_details": "must-not-be-saved-either",
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

    return execute_query_atom_canary(
        admission=admission,
        request=material["request"],
        policy=material["policy"],
        intents=material["intents"],
        query_facet_policy=material["facet_policy"],
        execution_git_commit="a" * 40,
        runner_sha256="b" * 64,
        runtime_module_sha256="c" * 64,
        policy_sha256="d" * 64,
        runtime_root=tmp_path / runtime_name,
        shared_ledger=ledger
        or SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite"),
        provider_call=fake_provider,
        observed_at=OBSERVED_AT,
    )


def test_request_is_18_plan_bounded_and_contains_no_hidden_targets(
    material: dict[str, Any],
) -> None:
    request = material["request"]
    serialized = json.dumps(request, ensure_ascii=False)
    assert len(request["plans"]) == 18
    assert len({tuple(row["plan_key"]) for row in request["plans"]}) == 18
    assert request["output_contract"]["maximum_atoms_per_plan"] == 1
    assert "SRC_" not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized
    assert "target-in-pool labels" in serialized


def test_admission_storage_uses_windows_safe_run_id_not_logical_id(
    tmp_path: Path,
) -> None:
    runner = _runner_module()
    run_id = "fin013_s1_08_query_atom_canary_" + "a" * 20
    path = runner.admission_storage_path(
        {
            "admission_id": "admission::" + run_id,
            "run_id": run_id,
        },
        authority_root=tmp_path,
    )
    assert path == tmp_path / f"{run_id}.json"
    assert ":" not in path.name
    with pytest.raises(runner.QueryAtomRunnerError) as exc_info:
        runner.admission_storage_path(
            {"run_id": "unsafe:run"},
            authority_root=tmp_path,
        )
    assert str(exc_info.value) == (
        "s1_08_query_atom_runner_admission_storage_identity_invalid"
    )


def test_valid_atom_is_locally_compiled_without_authority_drift(
    material: dict[str, Any],
) -> None:
    atom = _atom_for_first_plan(material)
    accepted, assisted = validate_and_compile_query_atom_output(
        output=_output(atom),
        request=material["request"],
        policy=material["policy"],
        intents=material["intents"],
        query_facet_policy=material["facet_policy"],
    )
    assert accepted == [{**atom, "provenance": "model_proposed_untrusted"}]
    assert len(assisted) == 36
    base_by_key = {
        (row.case_key, row.evidence_slot_id, row.evidence_owner_entity_key, row.language): row
        for row in material["base_plans"]
    }
    changed = next(row for row in assisted if row.accepted_model_atoms)
    base = base_by_key[
        (
            changed.case_key,
            changed.evidence_slot_id,
            changed.evidence_owner_entity_key,
            changed.language,
        )
    ]
    assert changed.metric_facets[-1] == atom["value"]
    assert changed.subject_entity_key == base.subject_entity_key
    assert changed.evidence_owner_entity_key == base.evidence_owner_entity_key
    assert changed.relationship_direction == base.relationship_direction
    assert changed.period_terms == base.period_terms
    assert changed.route_specific_filters == base.route_specific_filters
    assert changed.eligible_external_routes == base.eligible_external_routes
    assert changed.eligible_internal_routes == base.eligible_internal_routes


@pytest.mark.parametrize(
    ("mutation", "expected_suffix"),
    [
        ({"value": "Dell Technologies"}, "model_atom_authority_violation"),
        ({"value": "FY2028 demand"}, "model_atom_authority_violation"),
        ({"value": "https://example.com"}, "model_atom_authority_violation"),
        ({"atom_kind": "identity"}, "model_atom_shape_invalid"),
        ({"value": "x" * 65}, "model_atom_shape_invalid"),
    ],
)
def test_authority_violating_atoms_fail_closed(
    material: dict[str, Any],
    mutation: dict[str, str],
    expected_suffix: str,
) -> None:
    atom = {**_atom_for_first_plan(material), **mutation}
    with pytest.raises(S108QueryAtomCanaryError) as exc_info:
        validate_and_compile_query_atom_output(
            output=_output(atom),
            request=material["request"],
            policy=material["policy"],
            intents=material["intents"],
            query_facet_policy=material["facet_policy"],
        )
    assert exc_info.value.code.endswith(expected_suffix)


def test_duplicate_unknown_and_extra_shape_fail_closed(
    material: dict[str, Any],
) -> None:
    atom = _atom_for_first_plan(material)
    for output, expected in (
        (_output(atom, atom), "s1_08_query_atom_canary_output_plan_binding_invalid"),
        (
            _output({**atom, "case_key": "UNKNOWN"}),
            "s1_08_query_atom_canary_output_plan_binding_invalid",
        ),
        (
            _output({**atom, "unexpected": "field"}),
            "s1_08_query_atom_canary_output_atom_shape_invalid",
        ),
    ):
        with pytest.raises(S108QueryAtomCanaryError) as exc_info:
            validate_and_compile_query_atom_output(
                output=output,
                request=material["request"],
                policy=material["policy"],
                intents=material["intents"],
                query_facet_policy=material["facet_policy"],
            )
        assert exc_info.value.code == expected


def test_exact_once_success_captures_visible_io_but_strips_private_reasoning(
    material: dict[str, Any], tmp_path: Path
) -> None:
    admission = _admission(material, nonce="valid-one")
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite")
    terminal = _execute(
        material,
        tmp_path=tmp_path,
        admission=admission,
        provider_output=_output(_atom_for_first_plan(material)),
        ledger=ledger,
    )
    assert terminal["status"] == "terminal_succeeded_exact_once"
    assert terminal["accepted_atom_count"] == 1
    assert terminal["completed_calls"] == 1
    assert terminal["retry_count"] == 0
    assert terminal["runtime_activation"] is False
    assert terminal["business_artifact_promotions"] == 0
    assert terminal["shared_admission_receipt"]["state"] == "terminal"

    capture = _load(tmp_path / "run" / terminal["capture_ref"])
    capture_text = json.dumps(capture, ensure_ascii=False)
    assert capture["model_visible_request"] == material["request"]
    assert capture["gateway_result"]["content"]
    assert "reasoning_content" not in capture_text
    assert "reasoning_details" not in capture_text
    assert "must-not-be-saved" not in capture_text
    assert "api_key_env" not in capture["provider_request"]
    assert capture["credential_or_authorization_value_saved"] is False
    assert capture["business_evidence_or_fact_authority"] is False

    with pytest.raises(SharedAdmissionLedgerError) as exc_info:
        _execute(
            material,
            tmp_path=tmp_path,
            admission=admission,
            provider_output=_output(),
            ledger=ledger,
            runtime_name="duplicate-new-root",
        )
    assert str(exc_info.value).startswith("shared_admission_already_consumed")


def test_empty_atom_set_is_valid_observed_abstention(
    material: dict[str, Any], tmp_path: Path
) -> None:
    terminal = _execute(
        material,
        tmp_path=tmp_path,
        admission=_admission(material, nonce="empty-set"),
        provider_output=_output(),
    )
    assert terminal["status"] == "terminal_succeeded_exact_once"
    assert terminal["accepted_atom_count"] == 0
    assert terminal["accepted_atoms"] == []
    assert terminal["assisted_plan_set_digest"] is not None


def test_invalid_natural_output_is_terminal_failure_and_not_retried(
    material: dict[str, Any], tmp_path: Path
) -> None:
    invalid = _output({**_atom_for_first_plan(material), "value": "FY2028 demand"})
    terminal = _execute(
        material,
        tmp_path=tmp_path,
        admission=_admission(material, nonce="invalid-output"),
        provider_output=invalid,
    )
    assert terminal["status"] == "terminal_failed_no_retry"
    assert terminal["terminal_code"].endswith("model_atom_authority_violation")
    assert terminal["completed_calls"] == 1
    assert terminal["retry_count"] == 0
    assert terminal["accepted_atoms"] == []
    assert terminal["runtime_activation"] is False


def test_policy_mutations_cannot_self_authorize_or_expand_model_power(
    tmp_path: Path,
) -> None:
    policy = _load(CANARY_POLICY_PATH)
    policy["calls_authorized_by_policy_alone"]["model"] = 1
    target = tmp_path / "policy.json"
    target.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(S108QueryAtomCanaryError) as exc_info:
        load_query_atom_canary_policy(target)
    assert exc_info.value.code == "s1_08_query_atom_canary_policy_self_authorized_call"

    policy = _load(CANARY_POLICY_PATH)
    policy["selection_contract"]["model_may_emit_final_query"] = True
    target.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(S108QueryAtomCanaryError) as exc_info:
        load_query_atom_canary_policy(target)
    assert exc_info.value.code == "s1_08_query_atom_canary_selection_contract_invalid"


def test_materialized_implementation_proof_is_digest_bound_and_honest() -> None:
    proof = _load(IMPLEMENTATION_PROOF_PATH)
    body = dict(proof)
    supplied = body.pop("proof_digest")
    assert supplied == canonical_digest(body)
    assert proof["status"] == (
        "zero_call_implementation_pass_live_authority_pending"
    )
    assert proof["request_contract"]["visible_plan_count"] == 18
    assert proof["fake_runtime_proof"]["duplicate_admission_blocked"] is True
    assert proof["fake_runtime_proof"][
        "private_reasoning_stripped_from_capture"
    ] is True
    assert proof["observed_calls"]["real_provider"] == 0
    assert proof["observed_calls"]["natural_model"] == 0
    assert proof["decision"]["provider_call_authorized_by_this_proof"] is False
    assert proof["decision"][
        "internal_retrieval_and_BGE_rerank_backlog_preserved"
    ] is True


def test_clean_authority_binds_implementation_and_only_one_model_call() -> None:
    authority = _load(AUTHORITY_PATH)
    body = dict(authority)
    supplied = body.pop("decision_digest")
    assert supplied == canonical_digest(body)
    assert authority["status"] == (
        "one_bounded_deepseek_query_atom_canary_authorized"
    )
    assert authority["run_scope"] == (
        "S1_08_QUERY_FACET_DEEPSEEK_ATOM_CANARY_EXACT_LIVE_EXECUTION"
    )
    granted = authority["authority"]
    assert granted["provider_call_ceiling"] == 1
    assert granted["transport_attempt_ceiling"] == 1
    assert granted["retry_count"] == 0
    assert granted["fallback_count"] == 0
    assert granted["automatic_runtime_activation"] is False
    assert granted["automatic_combined_live"] is False
    assert granted["automatic_internal_retrieval"] is False
    assert not any(authority["calls_executed_by_this_decision"].values())

    binding = authority["implementation_binding"]
    implementation_pairs = (
        ("runner_ref", "runner_sha256_normalized"),
        ("runtime_module_ref", "runtime_module_sha256_normalized"),
        ("policy_ref", "policy_sha256_normalized"),
    )
    current_hashes_match = all(
        _normalized_sha256(ROOT / binding[ref_key]) == binding[hash_key]
        for ref_key, hash_key in implementation_pairs
    )
    exact_scope = run_project_os_preflight(
        ROOT,
        run_scope=(
            "S1_08_QUERY_FACET_DEEPSEEK_ATOM_CANARY_EXACT_LIVE_EXECUTION"
        ),
    )
    if exact_scope["status"] == "pass":
        assert current_hashes_match
    else:
        assert current_hashes_match is False
    ancestor = subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            authority["implementation_commit"],
            "HEAD",
        ],
        cwd=ROOT,
        check=False,
    )
    assert ancestor.returncode == 0


def test_project_os_exposes_only_latest_typed_scope() -> None:
    latest = json.loads(
        [
            line
            for line in (
                ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
            ).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ][-1]
    )
    allowed = set(latest["allowed_run_scopes"])
    for scope in (
        "S1_08_QUERY_FACET_THREE_WAY_DELL_MU_NVDA_EVALUATION",
        "S1_08_QUERY_FACET_DEEPSEEK_ATOM_CANARY_EXACT_LIVE_EXECUTION",
        "S1_08_QUERY_ATOM_CANARY_WINDOWS_SAFE_ADMISSION_STORAGE_ZERO_CALL_REPAIR",
    ):
        preflight = run_project_os_preflight(ROOT, run_scope=scope)
        expected = "pass" if scope in allowed else "blocked"
        assert preflight["status"] == expected
        assert preflight["contract_errors"] == []
