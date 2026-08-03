from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

import pytest

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    BoundedAgentExecutionError,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V8_REF,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.fin_0_1_2_s3_product_input import (
    assert_fin_0_1_2_s3_exact_input_matches_manifest,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_2_s3_t02_production_runtime_integration import (
    _CurrentS3ProductionFake,
    _compiled_admission,
)
from test_fin_0_1_s3_t09_deepseek_transport_exact_input_preflight_repair import (
    _create_accepted_case,
    _prepare,
)
from test_fin_0_1_s4_t05_research_lead_gap_atom_deterministic_projection_zero_call_implementation import (
    test_v6_validates_all_atoms_then_projects_deterministic_top_four,
)
from test_fin_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_zero_call_implementation import (
    test_v7_materializes_all_none_some_truth_table,
)


IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_research_lead_v8_local_"
    "semantic_materialization_minimum_zero_call_implementation_v1_0.json"
)
FORMAL_FAILURE = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_execution_"
    "terminal_failure_result_v1_0.json"
)
EXECUTION_ENVELOPE = ROOT / (
    "configs/runtime/fin_ia_0_1_2_s3_t03_nvda_fresh_identity_"
    "execution_envelope_v1_0.json"
)
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_research_lead_v8_"
    "independent_zero_call_proof_decision_v1_0.json"
)
NEXT_ACTION = (
    "FIN-0.1.2-S3-T03-NVDA-REPLACEMENT-EXACT-LIVE-FRESH-"
    "ADMISSION-AUTHORITY-DECISION"
)
_CREDENTIAL_MARKERS = (
    "API_KEY",
    "AUTHORIZATION",
    "ACCESS_TOKEN",
    "SECRET_KEY",
)


class LeadV8IndependentProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeadV8IndependentProofError(code)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        )


class _LeadMutationFake(_CurrentS3ProductionFake):
    def __init__(
        self,
        mutate: Callable[[dict[str, Any]], None],
    ) -> None:
        super().__init__(safe_lead=True)
        self._mutate = mutate

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        response = dict(super().__call__(**kwargs))
        request = json.loads(kwargs["messages"][1]["content"])
        if request["node_id"] != "research_lead":
            return response
        output = json.loads(str(response["content"]))
        self._mutate(output)
        response["content"] = json.dumps(
            output,
            ensure_ascii=False,
            sort_keys=True,
        )
        return response


def _mutate_adjacent_alias_semantics(output: dict[str, Any]) -> None:
    dependency = output["cross_cell_dependencies"][0]
    dependency["claim_ids"] = ["C002"]
    dependency["statement"] = "provider falsely claims direct facts"
    conflict = output["conflict_adjudications"][0]
    conflict["involved_claim_ids"] = ["C001", "C002"]
    conflict["statement"] = "provider falsely claims a resolved conflict"
    conflict["resolution_status"] = "resolved"
    conflict["terminal_state_summary"] = "provider false terminal state"


def _mutate_unknown_alias(output: dict[str, Any]) -> None:
    output["cross_cell_dependencies"][0]["claim_ids"] = ["C999"]


def _mutate_duplicate_alias(output: dict[str, Any]) -> None:
    output["cross_cell_dependencies"][0]["claim_ids"] = ["C001", "C001"]


def _artifact_map(result: Any) -> dict[str, dict[str, Any]]:
    return {
        str(row.artifact_type): dict(row.payload)
        for row in result.artifacts
    }


def _ref_key(value: Mapping[str, Any]) -> tuple[str, str]:
    return str(value["program_cell_id"]), str(value["local_id"])


def _expected_presence(
    refs: list[Mapping[str, Any]],
    specialist_outputs: list[Mapping[str, Any]],
) -> str:
    support = {
        (str(specialist["program_cell_id"]), str(claim["claim_id"])): bool(
            claim.get("support_fact_ids")
        )
        for specialist in specialist_outputs
        for claim in specialist.get("judgment_layer", ())
        if isinstance(claim, Mapping)
    }
    values = [support[_ref_key(ref)] for ref in refs]
    if all(values):
        return "facts_present"
    if not any(values):
        return "no_facts_present"
    return "mixed_fact_presence"


def _run_failure(
    prepared: Any,
    admission: Any,
    fake: Any,
    identity: str,
) -> dict[str, Any]:
    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    )
    try:
        executor.execute(
            prepared.input_pack,
            admission,
            run_identity={
                "research_run_id": identity,
                "attempt_id": f"{identity}-a1",
            },
        )
    except BoundedAgentExecutionError as exc:
        return {
            "stage": exc.stage,
            "capture_count": len(exc.provider_output_captures),
            "failure_code": exc.failure_observation["failure_code"],
            "local_fact_receipts": len(
                exc.failure_observation["local_fact_receipts"]
            ),
        }
    raise LeadV8IndependentProofError(f"mutation_did_not_fail:{identity}")


def run_worker(temp_root: Path) -> dict[str, Any]:
    monkeypatch = pytest.MonkeyPatch()
    network_attempts: list[str] = []
    original_connect = socket.socket.connect

    def guarded_connect(instance: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) and address else None
        if host in {"127.0.0.1", "::1", "localhost"}:
            return original_connect(instance, address)
        network_attempts.append(repr(address))
        raise AssertionError("external_network_forbidden_in_lead_v8_fresh_proof")

    def blocked_network(*args: Any, **kwargs: Any) -> None:
        network_attempts.append(repr((args, kwargs)))
        raise AssertionError("external_network_forbidden_in_lead_v8_fresh_proof")

    try:
        monkeypatch.setattr(socket.socket, "connect", guarded_connect)
        monkeypatch.setattr(socket, "create_connection", blocked_network)
        for key in list(os.environ):
            if any(marker in key.upper() for marker in _CREDENTIAL_MARKERS):
                monkeypatch.delenv(key, raising=False)
        inherited_credentials = [
            key
            for key in os.environ
            if any(marker in key.upper() for marker in _CREDENTIAL_MARKERS)
        ]
        _require(not inherited_credentials, "credential_environment_not_scrubbed")

        _, local_service, evidence_service, case, accepted = (
            _create_accepted_case(temp_root)
        )
        prepared = _prepare(local_service, evidence_service, case, accepted)
        input_receipt = assert_fin_0_1_2_s3_exact_input_matches_manifest(
            prepared.input_pack,
            source_digest=prepared.preparation_digest,
        )
        _require(
            input_receipt["paid_execution_authorized"] is False,
            "tracked_input_receipt_authorized_paid_execution",
        )
        mutated_input = prepared.input_pack.model_copy(
            update={"query": "independent proof input mutation"}
        )
        input_mutation_rejected = False
        try:
            assert_fin_0_1_2_s3_exact_input_matches_manifest(
                mutated_input,
                source_digest=prepared.preparation_digest,
            )
        except ValueError:
            input_mutation_rejected = True
        _require(input_mutation_rejected, "tracked_input_mutation_not_rejected")

        disabled = _compiled_admission(prepared, enabled=False)
        _require(
            not disabled.execution_enabled
            and disabled.max_provider_calls == 0
            and disabled.max_total_cost_usd == 0.0,
            "prospective_disabled_admission_not_fail_closed",
        )
        admission = _compiled_admission(prepared)
        _require(
            admission.research_lead_transport_ref
            == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V8_REF,
            "lead_v8_not_bound",
        )
        monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")

        fake = _CurrentS3ProductionFake(safe_lead=True)
        result = build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=fake,
        ).execute(
            prepared.input_pack,
            admission,
            run_identity={
                "research_run_id": "fresh-proof-current-nvda",
                "attempt_id": "fresh-proof-current-nvda-a1",
            },
        )
        artifacts = _artifact_map(result)
        manifest = artifacts[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE]
        topology = manifest["interaction_topology"]
        _require(len(fake.calls) == 9, "current_fake_provider_count_mismatch")
        _require(len(result.provider_output_captures) == 9, "capture_count_mismatch")
        _require(len(result.artifacts) == 9, "artifact_count_mismatch")
        _require(
            len(result.execution_observation["local_fact_receipts"]) == 3,
            "local_fact_receipt_count_mismatch",
        )
        _require(
            topology
            == {
                "logical_node_count": 6,
                "logical_interaction_count": 12,
                "local_fact_interaction_count": 3,
                "provider_interaction_count": 9,
                "provider_capture_count": 9,
                "business_artifact_count": 9,
            },
            "current_full_fake_topology_mismatch",
        )

        adjacent_fake = _LeadMutationFake(_mutate_adjacent_alias_semantics)
        adjacent_result = build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=adjacent_fake,
        ).execute(
            prepared.input_pack,
            admission,
            run_identity={
                "research_run_id": "fresh-proof-adjacent-alias",
                "attempt_id": "fresh-proof-adjacent-alias-a1",
            },
        )
        adjacent_judgment = _artifact_map(adjacent_result)[
            BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE
        ]
        lead = adjacent_judgment["cross_cell_lead"]
        dependency = lead["cross_cell_dependencies"][0]
        conflict = lead["conflict_adjudications"][0]
        expected_presence = _expected_presence(
            conflict["involved_claim_ids"],
            adjacent_judgment["specialist_outputs"],
        )
        _require(
            "provider falsely" not in dependency["statement"]
            and "provider falsely" not in conflict["statement"]
            and conflict["resolution_status"] == "unresolved"
            and conflict["fact_presence_summary"] == expected_presence,
            "adjacent_alias_provider_semantics_survived_local_assembly",
        )

        runtime_owned = _CurrentS3ProductionFake(
            safe_lead=True,
            inject_runtime_owned_lead_field=True,
        )
        failures = {
            "runtime_owned_field": _run_failure(
                prepared,
                admission,
                runtime_owned,
                "fresh-proof-runtime-owned-field",
            ),
            "unknown_alias": _run_failure(
                prepared,
                admission,
                _LeadMutationFake(_mutate_unknown_alias),
                "fresh-proof-unknown-alias",
            ),
            "duplicate_alias": _run_failure(
                prepared,
                admission,
                _LeadMutationFake(_mutate_duplicate_alias),
                "fresh-proof-duplicate-alias",
            ),
        }
        _require(
            all(row["stage"] == "research_lead" for row in failures.values()),
            "lead_mutation_failed_at_wrong_stage",
        )

        test_v6_validates_all_atoms_then_projects_deterministic_top_four()
        for mode, expected in (
            ("all", "facts_present"),
            ("none", "no_facts_present"),
            ("some", "mixed_fact_presence"),
        ):
            test_v7_materializes_all_none_some_truth_table(mode, expected)

        _require(not network_attempts, "network_attempt_observed")
        envelope = _load(EXECUTION_ENVELOPE)
        return {
            "status": "pass",
            "current_input": {
                "input_digest": prepared.input_pack.input_digest,
                "preparation_digest": prepared.preparation_digest,
                "stable_business_input_digest": envelope[
                    "stable_business_input"
                ]["digest"],
                "mutation_rejected": input_mutation_rejected,
            },
            "current_full_fake": {
                "logical_nodes": topology["logical_node_count"],
                "logical_interactions": topology["logical_interaction_count"],
                "local_fact_receipts": topology["local_fact_interaction_count"],
                "provider_calls": len(fake.calls),
                "provider_captures": len(result.provider_output_captures),
                "artifacts": len(result.artifacts),
                "artifact_types": sorted(artifacts),
            },
            "adjacent_alias_semantic_mutation": {
                "provider_narrative_survived": False,
                "selected_dependency_claim_count": len(
                    dependency["claim_ids"]
                ),
                "selected_conflict_claim_count": len(
                    conflict["involved_claim_ids"]
                ),
                "local_fact_presence": conflict["fact_presence_summary"],
                "local_resolution_status": conflict["resolution_status"],
                "artifacts": len(adjacent_result.artifacts),
            },
            "negative_mutations": failures,
            "historical_regression": {
                "lead_v6_gap_projection": "pass",
                "lead_v7_fact_presence_all_none_some": "pass",
            },
            "hard_boundaries": {
                "real_model_calls": 0,
                "real_provider_calls": 0,
                "network_attempts": len(network_attempts),
                "source_network_calls": 0,
                "external_tool_calls": 0,
                "business_artifact_promotions": 0,
                "admissions_issued": 0,
                "admissions_consumed": 0,
            },
        }
    finally:
        monkeypatch.undo()


def _clean_child_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not any(marker in key.upper() for marker in _CREDENTIAL_MARKERS)
    }
    environment["PYTHONHASHSEED"] = "0"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def build_decision() -> dict[str, Any]:
    implementation = _load(IMPLEMENTATION)
    formal_failure = _load(FORMAL_FAILURE)
    _require(
        implementation["status"]
        == "engineering_pass_fixture_and_natural_failure_body_proven_"
        "independent_proof_pending",
        "implementation_not_ready_for_independent_proof",
    )
    for relative, expected in implementation["exact_code_bindings"].items():
        _require(
            _sha256(ROOT / relative) == expected,
            f"implementation_binding_drift:{relative}",
        )
    _require(
        formal_failure["typed_terminal"]["status"] == "failed",
        "formal_failure_reclassified",
    )
    _require(
        formal_failure["observed_execution"]["business_artifacts"] == 0,
        "formal_failure_artifact_count_changed",
    )

    outputs: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="lead-v8-proof-parent-") as parent:
        parent_path = Path(parent)
        for ordinal in (1, 2):
            child_root = parent_path / f"fresh-{ordinal}"
            child_root.mkdir()
            output = child_root / "worker-result.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker-root",
                    str(child_root),
                    "--worker-output",
                    str(output),
                ],
                cwd=ROOT,
                env=_clean_child_environment(),
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            _require(
                completed.returncode == 0,
                "fresh_worker_failed:"
                + str(ordinal)
                + ":"
                + completed.stderr[-1000:],
            )
            outputs.append(_load(output))
    _require(outputs[0] == outputs[1], "fresh_worker_outputs_differ")
    matrix = outputs[0]

    return {
        "schema_version": (
            "fin_ia_0_1_2_s3_t03_research_lead_v8_independent_"
            "zero_call_proof_decision_v1_0"
        ),
        "decision_id": (
            "FIN-0.1.2-S3-T03-RESEARCH-LEAD-V8-LOCAL-SEMANTIC-"
            "MATERIALIZATION-INDEPENDENT-ZERO-CALL-PROOF-DECISION"
        ),
        "recorded_at": "2026-08-03T23:30:00+08:00",
        "status": (
            "pass_independent_two_fresh_process_zero_call_proof_"
            "replacement_admission_authority_pending"
        ),
        "source_bindings": {
            "implementation": {
                "ref": _display(IMPLEMENTATION),
                "sha256": _sha256(IMPLEMENTATION),
            },
            "immutable_primary_failure": {
                "ref": _display(FORMAL_FAILURE),
                "sha256": _sha256(FORMAL_FAILURE),
                "status": "failed",
                "provider_captures": 7,
                "artifacts": 0,
                "reclassified": False,
            },
            "exact_code_bindings": implementation["exact_code_bindings"],
            "research_lead_transport_ref": (
                S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V8_REF
            ),
        },
        "fresh_process_proof": {
            "independent_processes": 2,
            "distinct_disposable_roots": 2,
            "normalized_outputs_equal": True,
            "normalized_output_digest": canonical_digest(matrix),
            "credential_environment_scrubbed_before_import": True,
            "socket_network_guard_installed": True,
            "diagnostic_capture_replay_or_repair_callback_used": False,
            "matrix": matrix,
        },
        "acceptance_boundary": {
            "Lead_v8_engineering_proof": True,
            "formal_S3_T03_pass": False,
            "replacement_admission_issued": False,
            "replacement_exact_live_executed": False,
            "paired_assessment_performed": False,
            "owner_acceptance_performed": False,
            "S3_T04_entered": False,
            "release_qualified": False,
        },
        "experiment_governance": {
            "replacement_admission_authority_decision_authorized_next": True,
            "replacement_admission_issuance_authorized_now": False,
            "live_execution_authorized_now": False,
            "model_or_provider_call_authorized_now": False,
            "third_exact_attempt_ever_authorized": False,
            "L2_to_L4_debt_owner": "S3-T04",
            "replacement_new_L1_disposition": "S3_honest_block",
        },
        "root_cause_disposition": {
            "issue_id": (
                "RC-P36-108-fin-0-1-2-s3-t03-research-lead-"
                "deterministic-fact-presence-and-claim-alias-semantic-"
                "ownership-regression"
            ),
            "prior_status": (
                "structural_implementation_fixture_proven_"
                "independent_proof_pending"
            ),
            "new_status": (
                "independent_fresh_zero_call_proof_pass_"
                "replacement_admission_authority_pending"
            ),
            "closed": False,
            "closure_requires_replacement_exact_live_L1_pass": True,
        },
        "proof_generator": {
            "ref": _display(Path(__file__)),
            "sha256": _sha256(Path(__file__)),
        },
        "next_action": NEXT_ACTION,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-root", type=Path)
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--output", type=Path, default=DECISION)
    args = parser.parse_args()
    if args.worker_root is not None:
        _require(args.worker_output is not None, "worker_output_required")
        result = run_worker(args.worker_root)
        _write_json(args.worker_output, result)
        return 0
    result = build_decision()
    _write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
