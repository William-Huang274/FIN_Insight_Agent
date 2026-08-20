from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import scripts.research.run_s3_multi_agent_preview_live as runner


CHECKPOINT = (
    ROOT
    / "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R10_lead_coordination_checkpoint_v1_0.json"
)
DOWNSTREAM_PROGRESS_CHECKPOINT = (
    ROOT
    / "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R11_downstream_repair_progress_checkpoint_v1_0.json"
)
DOWNSTREAM_ANALYSIS_CHECKPOINT = (
    ROOT
    / "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R11_cash_repair_analysis_fragment_checkpoint_v1_0.json"
)
DOWNSTREAM_PROGRESS_CHECKPOINT_V2 = (
    ROOT
    / "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "R15_downstream_repair_progress_checkpoint_v1_1.json"
)


def _checkpoint() -> dict[str, object]:
    return json.loads(CHECKPOINT.read_text(encoding="utf-8"))


def test_r10_checkpoint_recovers_exact_counter_workpaper_and_lead_decision() -> None:
    checkpoint = _checkpoint()

    counter = runner._load_bound_counter_workpaper(checkpoint)
    coordination = runner._load_bound_lead_coordination_decision(checkpoint)

    assert counter["agent_id"] == "AGENT::COUNTEREVIDENCE"
    assert counter["workpaper_digest"] == (
        checkpoint["workpaper_digests"]["AGENT::COUNTEREVIDENCE"]
    )
    assert coordination["accepted_challenge_ids"] == checkpoint[
        "accepted_challenge_ids"
    ]
    assert coordination["deferred_challenge_ids"] == checkpoint[
        "deferred_challenge_ids"
    ]
    assert coordination["next_state"] == "continue_local_repairs"
    assert 1200 < len(coordination["coordination_rationale"]) <= 2200


def test_r10_checkpoint_rejects_counter_terminal_digest_mutation() -> None:
    checkpoint = deepcopy(_checkpoint())
    checkpoint["source_terminal_result_sha256"] = "0" * 64

    with pytest.raises(
        runner.MultiAgentPreviewLiveError,
        match="multi_agent_preview_coordination_terminal_capture_drift",
    ):
        runner._load_bound_counter_workpaper(checkpoint)


def test_r10_checkpoint_rejects_lead_response_capture_mutation() -> None:
    checkpoint = deepcopy(_checkpoint())
    checkpoint["source_receipts"]["lead_coordination"][
        "response_capture_sha256"
    ] = "0" * 64

    with pytest.raises(
        runner.MultiAgentPreviewLiveError,
        match="multi_agent_preview_coordination_capture_drift",
    ):
        runner._load_bound_lead_coordination_decision(checkpoint)


def test_r11_checkpoint_recovers_completed_demand_and_exact_cash_fragment() -> None:
    progress = json.loads(
        DOWNSTREAM_PROGRESS_CHECKPOINT.read_text(encoding="utf-8")
    )
    fragment = json.loads(
        DOWNSTREAM_ANALYSIS_CHECKPOINT.read_text(encoding="utf-8")
    )

    completed = runner._load_bound_downstream_repair_progress(
        checkpoint=progress,
        fragment_checkpoint=fragment,
    )
    draft, original_messages = runner._load_bound_analysis_checkpoint_source(
        fragment
    )

    assert list(completed) == ["CHALLENGE::B1FC30D87F6DB63FDB91003C"]
    assert completed["CHALLENGE::B1FC30D87F6DB63FDB91003C"][
        "workpaper_digest"
    ] == "3914ddf8e0fde4ba7b82933795ada3feee70701f609fce901af684dcbeaf47e0"
    assert progress["pending_challenge_ids"][0] == (
        "CHALLENGE::803238978B747FEED1CE12C9"
    )
    assert fragment["node_id"] == "AGENT::CASH_CONVERSION::COUNTER_REPAIR"
    assert len(draft) == 815
    assert [row["role"] for row in original_messages] == ["system", "user"]


def test_r11_completed_demand_replays_against_its_exact_model_context() -> None:
    progress = json.loads(
        DOWNSTREAM_PROGRESS_CHECKPOINT.read_text(encoding="utf-8")
    )
    fragment = json.loads(
        DOWNSTREAM_ANALYSIS_CHECKPOINT.read_text(encoding="utf-8")
    )
    completed, completed_contexts = (
        runner._load_bound_downstream_repair_progress_bundle(
            checkpoint=progress,
            fragment_checkpoint=fragment,
        )
    )
    context = completed_contexts["CHALLENGE::B1FC30D87F6DB63FDB91003C"]
    replayed = runner.revalidate_bound_specialist_workpaper(
        completed["CHALLENGE::B1FC30D87F6DB63FDB91003C"],
        context=context,
        expected_agent_id="AGENT::DEMAND_QUALITY",
    )

    assert context["context_digest"] == (
        "1ddcce797a2fac8566024a3c2dd1ea1eb31c837637a3352bb7dac6d37f1f0e6b"
    )
    assert replayed["workpaper_digest"] == (
        "3914ddf8e0fde4ba7b82933795ada3feee70701f609fce901af684dcbeaf47e0"
    )


def test_r15_progress_reuses_demand_and_cash_then_starts_fresh_supply() -> None:
    progress = json.loads(
        DOWNSTREAM_PROGRESS_CHECKPOINT_V2.read_text(encoding="utf-8")
    )

    completed, contexts, validated = (
        runner._load_bound_downstream_repair_progress_bundle_v2(
            checkpoint=progress
        )
    )

    assert list(completed) == [
        "CHALLENGE::B1FC30D87F6DB63FDB91003C",
        "CHALLENGE::803238978B747FEED1CE12C9",
    ]
    assert set(contexts) == set(completed)
    assert completed["CHALLENGE::803238978B747FEED1CE12C9"][
        "workpaper_digest"
    ] == "31c61429d51b035751dbe696f7fb66c7e49ac187def38de1475482ba1b312a45"
    assert validated["pending_challenge_repairs"] == [
        {
            "challenge_id": "CHALLENGE::71AAF31E7FBD5A99163BBE8D",
            "target_agent_id": "AGENT::SUPPLY_RELATIONSHIP",
            "node_id": "AGENT::SUPPLY_RELATIONSHIP::COUNTER_REPAIR",
        }
    ]
    assert validated["resume_policy"][
        "maximum_analysis_continuation_calls"
    ] == 0


def test_r11_completed_demand_context_rejects_request_digest_mutation() -> None:
    progress = json.loads(
        DOWNSTREAM_PROGRESS_CHECKPOINT.read_text(encoding="utf-8")
    )
    terminal = json.loads(
        (
            ROOT
            / "data/workbench_private/model_runs/"
            "fin_0_1_3_s3_dell_multi_agent_preview_r10_20260820/"
            "terminal_failure.json"
        ).read_text(encoding="utf-8")
    )
    demand_node = deepcopy(
        next(
            row
            for row in terminal["node_executions"]
            if row["node_id"] == "AGENT::DEMAND_QUALITY::COUNTER_REPAIR"
        )
    )
    demand_node["attempts"][0]["request_digest"] = "0" * 64

    with pytest.raises(
        runner.MultiAgentPreviewLiveError,
        match="multi_agent_preview_completed_repair_context_capture_drift",
    ):
        runner._load_bound_completed_repair_context(
            row=demand_node,
            receipt=progress["completed_challenge_repairs"][0],
            source_run_id=progress["source_run_id"],
            coordination_checkpoint=_checkpoint(),
        )


def test_r11_completed_demand_rejects_fresh_feedback_context_recompile() -> None:
    progress = json.loads(
        DOWNSTREAM_PROGRESS_CHECKPOINT.read_text(encoding="utf-8")
    )
    fragment = json.loads(
        DOWNSTREAM_ANALYSIS_CHECKPOINT.read_text(encoding="utf-8")
    )
    completed, completed_contexts = (
        runner._load_bound_downstream_repair_progress_bundle(
            checkpoint=progress,
            fragment_checkpoint=fragment,
        )
    )
    challenge_id = "CHALLENGE::B1FC30D87F6DB63FDB91003C"
    context = deepcopy(completed_contexts[challenge_id])
    context["feedback_receipts"][0]["session_id"] = (
        "SESSION::DELL::FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R12_20260820::"
        "AGENT-DEMAND_QUALITY"
    )
    context_body = {
        key: value for key, value in context.items() if key != "context_digest"
    }
    context["context_digest"] = runner.canonical_digest(context_body)

    with pytest.raises(
        ValueError,
        match="multi_agent_bound_workpaper_digest_invalid",
    ):
        runner.revalidate_bound_specialist_workpaper(
            completed[challenge_id],
            context=context,
            expected_agent_id="AGENT::DEMAND_QUALITY",
        )


def test_r11_checkpoint_rejects_completed_repair_digest_mutation() -> None:
    progress = json.loads(
        DOWNSTREAM_PROGRESS_CHECKPOINT.read_text(encoding="utf-8")
    )
    fragment = json.loads(
        DOWNSTREAM_ANALYSIS_CHECKPOINT.read_text(encoding="utf-8")
    )
    progress["completed_challenge_repairs"][0]["workpaper_digest"] = "0" * 64
    progress["checkpoint_digest"] = runner.canonical_digest(
        {
            key: value
            for key, value in progress.items()
            if key != "checkpoint_digest"
        }
    )

    with pytest.raises(
        runner.MultiAgentPreviewLiveError,
        match="multi_agent_preview_downstream_completed_repair_drift",
    ):
        runner._load_bound_downstream_repair_progress(
            checkpoint=progress,
            fragment_checkpoint=fragment,
        )


def test_r11_checkpoint_rejects_cash_capture_mutation() -> None:
    fragment = json.loads(
        DOWNSTREAM_ANALYSIS_CHECKPOINT.read_text(encoding="utf-8")
    )
    fragment["request_capture_sha256"] = "0" * 64
    fragment["checkpoint_digest"] = runner.canonical_digest(
        {
            key: value
            for key, value in fragment.items()
            if key != "checkpoint_digest"
        }
    )

    with pytest.raises(
        runner.MultiAgentPreviewLiveError,
        match="multi_agent_preview_analysis_checkpoint_capture_drift",
    ):
        runner._load_bound_analysis_checkpoint_source(fragment)


def test_r10_authority_accepts_only_coordination_checkpoint_successor(
    tmp_path: Path,
) -> None:
    prior_authority = json.loads(
        (
            ROOT
            / "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
            "preview_live_authority_v1_8.json"
        ).read_text(encoding="utf-8")
    )
    scope_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "live_scope_decision_v1_8.json"
    )
    scope = json.loads((ROOT / scope_ref).read_text(encoding="utf-8"))

    def binding(ref: str) -> dict[str, str]:
        path = ROOT / ref
        return {"ref": ref, "sha256": runner._sha(path)}

    base_names = {
        "topology",
        "objective",
        "zero_call_proof",
        "successor_zero_call_proof",
        "planning_overlay",
        "analysis_profile",
        "submission_profile",
        "historical_five_cell_assessment",
        "predecessor_plan_checkpoint",
    }
    bound_inputs = {
        name: deepcopy(prior_authority["bound_inputs"][name])
        for name in base_names
    }
    bound_inputs.update(
        {
            "project_os_scope_decision": binding(scope_ref),
            "predecessor_scope_decision": binding(
                scope["predecessor_scope_decision_ref"]
            ),
            "predecessor_authority": binding(
                scope["predecessor_live_authority_ref"]
            ),
            "predecessor_result": binding(
                scope["predecessor_live_result_ref"]
            ),
            "lead_plan_checkpoint": binding(scope["lead_plan_checkpoint_ref"]),
            "workpaper_checkpoint": binding(scope["workpaper_checkpoint_ref"]),
            "lead_coordination_checkpoint": binding(
                scope["lead_coordination_checkpoint_ref"]
            ),
            "coordination_checkpoint_successor_zero_call_proof": binding(
                scope[
                    "coordination_checkpoint_successor_zero_call_proof_ref"
                ]
            ),
        }
    )
    output_prefix = "data/pytest_multi_agent_preview_r10_authority_unused"
    authority = {
        "schema_version": runner.COORDINATION_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA,
        "status": (
            "approved_for_one_R9_lead_coordination_checkpoint_downstream_"
            "successor_after_project_os_preflight"
        ),
        "authorized_at": "2026-08-20T12:00:00+08:00",
        "implementation_commit": runner._git_head(),
        "bound_inputs": bound_inputs,
        "execution_limits": deepcopy(scope["execution_limits"]),
        "outputs": {
            "run_id": "PYTEST-R10-UNUSED",
            "capture_root_ref": output_prefix + "_captures",
            "private_output_root_ref": output_prefix + "_private",
            "public_result_ref": output_prefix + "_public.json",
        },
        "authority_statement": "pytest-only authority validation",
    }
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps(authority), encoding="utf-8")

    validated, inputs, outputs = runner._validate_authority(authority_path)

    assert validated["schema_version"] == (
        runner.COORDINATION_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA
    )
    assert set(inputs) == set(bound_inputs)
    assert outputs["run_id"] == "PYTEST-R10-UNUSED"


def test_r11_authority_accepts_only_downstream_analysis_successor(
    tmp_path: Path,
) -> None:
    prior_authority = json.loads(
        (
            ROOT
            / "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
            "preview_live_authority_v1_9.json"
        ).read_text(encoding="utf-8")
    )
    scope_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "live_scope_decision_v1_9.json"
    )
    scope = json.loads((ROOT / scope_ref).read_text(encoding="utf-8"))

    def binding(ref: str) -> dict[str, str]:
        path = ROOT / ref
        return {"ref": ref, "sha256": runner._sha(path)}

    base_names = {
        "topology",
        "objective",
        "zero_call_proof",
        "successor_zero_call_proof",
        "planning_overlay",
        "analysis_profile",
        "submission_profile",
        "historical_five_cell_assessment",
        "predecessor_plan_checkpoint",
    }
    bound_inputs = {
        name: deepcopy(prior_authority["bound_inputs"][name])
        for name in base_names
    }
    bound_inputs.update(
        {
            "project_os_scope_decision": binding(scope_ref),
            "predecessor_scope_decision": binding(
                scope["predecessor_scope_decision_ref"]
            ),
            "predecessor_authority": binding(
                scope["predecessor_live_authority_ref"]
            ),
            "predecessor_result": binding(
                scope["predecessor_live_result_ref"]
            ),
            "lead_plan_checkpoint": binding(scope["lead_plan_checkpoint_ref"]),
            "workpaper_checkpoint": binding(scope["workpaper_checkpoint_ref"]),
            "lead_coordination_checkpoint": binding(
                scope["lead_coordination_checkpoint_ref"]
            ),
            "downstream_repair_progress_checkpoint": binding(
                scope["downstream_repair_progress_checkpoint_ref"]
            ),
            "downstream_analysis_fragment_checkpoint": binding(
                scope["downstream_analysis_fragment_checkpoint_ref"]
            ),
            "downstream_analysis_successor_zero_call_proof": binding(
                scope["downstream_analysis_successor_zero_call_proof_ref"]
            ),
            "analysis_continuation_profile": binding(
                scope["analysis_continuation_profile_ref"]
            ),
        }
    )
    output_prefix = "data/pytest_multi_agent_preview_r11_authority_unused"
    authority = {
        "schema_version": runner.DOWNSTREAM_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA,
        "status": (
            "approved_for_one_R10_downstream_repair_analysis_checkpoint_"
            "successor_after_project_os_preflight"
        ),
        "authorized_at": "2026-08-20T14:00:00+08:00",
        "implementation_commit": runner._git_head(),
        "bound_inputs": bound_inputs,
        "execution_limits": deepcopy(scope["execution_limits"]),
        "outputs": {
            "run_id": "PYTEST-R11-UNUSED",
            "capture_root_ref": output_prefix + "_captures",
            "private_output_root_ref": output_prefix + "_private",
            "public_result_ref": output_prefix + "_public.json",
        },
        "authority_statement": "pytest-only authority validation",
    }
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps(authority), encoding="utf-8")

    validated, inputs, outputs = runner._validate_authority(authority_path)

    assert validated["schema_version"] == (
        runner.DOWNSTREAM_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA
    )
    assert set(inputs) == set(bound_inputs)
    assert outputs["run_id"] == "PYTEST-R11-UNUSED"


def test_r12_authority_requires_immutable_r11_preprovider_disposition(
    tmp_path: Path,
) -> None:
    failed_authority_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "live_authority_v1_10.json"
    )
    failed_result_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "live_result_v1_10.json"
    )
    disposition_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "R12_preprovider_failure_disposition_zero_call_result_v1_0.json"
    )
    authority = json.loads(
        (ROOT / failed_authority_ref).read_text(encoding="utf-8")
    )

    def binding(ref: str) -> dict[str, str]:
        path = ROOT / ref
        return {"ref": ref, "sha256": runner._sha(path)}

    authority["schema_version"] = (
        runner.DOWNSTREAM_ANALYSIS_REPLACEMENT_AUTHORITY_SCHEMA
    )
    authority["status"] = (
        "approved_for_one_R12_preprovider_replacement_after_"
        "project_os_preflight"
    )
    authority["implementation_commit"] = runner._git_head()
    authority["bound_inputs"].update(
        {
            "failed_preprovider_authority": binding(failed_authority_ref),
            "failed_preprovider_result": binding(failed_result_ref),
            "preprovider_failure_disposition_zero_call_proof": binding(
                disposition_ref
            ),
        }
    )
    output_prefix = "data/pytest_multi_agent_preview_r12_authority_unused"
    authority["outputs"] = {
        "run_id": "PYTEST-R12-UNUSED",
        "capture_root_ref": output_prefix + "_captures",
        "private_output_root_ref": output_prefix + "_private",
        "public_result_ref": output_prefix + "_public.json",
    }
    authority["authority_statement"] = (
        "pytest-only new attempt after immutable R11 preprovider failure"
    )
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps(authority), encoding="utf-8")

    validated, inputs, outputs = runner._validate_authority(authority_path)

    assert validated["schema_version"] == (
        runner.DOWNSTREAM_ANALYSIS_REPLACEMENT_AUTHORITY_SCHEMA
    )
    assert set(inputs) == set(authority["bound_inputs"])
    assert outputs["run_id"] == "PYTEST-R12-UNUSED"


def test_r13_authority_requires_exact_r10_source_context_replay(
    tmp_path: Path,
) -> None:
    failed_authority_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "live_authority_v1_11.json"
    )
    failed_result_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "live_result_v1_11.json"
    )
    disposition_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "R13_source_context_replay_failure_disposition_zero_call_result_v1_0.json"
    )
    authority = json.loads(
        (ROOT / failed_authority_ref).read_text(encoding="utf-8")
    )

    def binding(ref: str) -> dict[str, str]:
        path = ROOT / ref
        return {"ref": ref, "sha256": runner._sha(path)}

    authority["schema_version"] = (
        runner.DOWNSTREAM_CONTEXT_REPLAY_REPLACEMENT_AUTHORITY_SCHEMA
    )
    authority["status"] = (
        "approved_for_one_R13_source_context_replay_replacement_after_"
        "project_os_preflight"
    )
    authority["implementation_commit"] = runner._git_head()
    authority["bound_inputs"].update(
        {
            "failed_preprovider_authority": binding(failed_authority_ref),
            "failed_preprovider_result": binding(failed_result_ref),
            "preprovider_failure_disposition_zero_call_proof": binding(
                disposition_ref
            ),
        }
    )
    output_prefix = "data/pytest_multi_agent_preview_r13_authority_unused"
    authority["outputs"] = {
        "run_id": "PYTEST-R13-UNUSED",
        "capture_root_ref": output_prefix + "_captures",
        "private_output_root_ref": output_prefix + "_private",
        "public_result_ref": output_prefix + "_public.json",
    }
    authority["authority_statement"] = (
        "pytest-only new attempt after immutable R12 context replay failure"
    )
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps(authority), encoding="utf-8")

    validated, inputs, outputs = runner._validate_authority(authority_path)

    assert validated["schema_version"] == (
        runner.DOWNSTREAM_CONTEXT_REPLAY_REPLACEMENT_AUTHORITY_SCHEMA
    )
    assert set(inputs) == set(authority["bound_inputs"])
    assert outputs["run_id"] == "PYTEST-R13-UNUSED"


def test_r14_authority_replaces_only_the_failed_continuation_profile(
    tmp_path: Path,
) -> None:
    failed_authority_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "live_authority_v1_12.json"
    )
    failed_result_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "live_result_v1_12.json"
    )
    disposition_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "R14_continuation_profile_failure_disposition_zero_call_result_v1_0.json"
    )
    completion_profile_ref = (
        "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_"
        "analysis_completion_non_thinking_profile_v1_0.json"
    )
    authority = json.loads(
        (ROOT / failed_authority_ref).read_text(encoding="utf-8")
    )

    def binding(ref: str) -> dict[str, str]:
        path = ROOT / ref
        return {"ref": ref, "sha256": runner._sha(path)}

    authority["schema_version"] = (
        runner.DOWNSTREAM_CONTINUATION_PROFILE_REPLACEMENT_AUTHORITY_SCHEMA
    )
    authority["status"] = (
        "approved_for_one_R14_non_thinking_continuation_profile_"
        "replacement_after_project_os_preflight"
    )
    authority["implementation_commit"] = runner._git_head()
    for name in (
        "failed_preprovider_authority",
        "failed_preprovider_result",
        "preprovider_failure_disposition_zero_call_proof",
    ):
        authority["bound_inputs"].pop(name)
    authority["bound_inputs"].update(
        {
            "failed_continuation_authority": binding(failed_authority_ref),
            "failed_continuation_result": binding(failed_result_ref),
            "continuation_profile_failure_disposition_zero_call_proof": binding(
                disposition_ref
            ),
            "analysis_completion_profile": binding(completion_profile_ref),
        }
    )
    output_prefix = "data/pytest_multi_agent_preview_r14_authority_unused"
    authority["outputs"] = {
        "run_id": "PYTEST-R14-UNUSED",
        "capture_root_ref": output_prefix + "_captures",
        "private_output_root_ref": output_prefix + "_private",
        "public_result_ref": output_prefix + "_public.json",
    }
    authority["authority_statement"] = (
        "pytest-only provider-profile replacement after immutable R13 failure"
    )
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps(authority), encoding="utf-8")

    validated, inputs, outputs = runner._validate_authority(authority_path)

    assert validated["schema_version"] == (
        runner.DOWNSTREAM_CONTINUATION_PROFILE_REPLACEMENT_AUTHORITY_SCHEMA
    )
    assert set(inputs) == set(authority["bound_inputs"])
    assert outputs["run_id"] == "PYTEST-R14-UNUSED"
    assert json.loads(
        inputs["analysis_completion_profile"].read_text(encoding="utf-8")
    )["request_defaults"] == {
        "max_tokens": 2000,
        "stream": False,
        "thinking": {"type": "disabled"},
    }


def test_r15_authority_reuses_two_repairs_and_starts_fresh_supply(
    tmp_path: Path,
) -> None:
    source_authority_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "live_authority_v1_13.json"
    )
    scope_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "live_scope_decision_v1_10.json"
    )
    failed_result_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "live_result_v1_13.json"
    )
    disposition_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "R15_role_repair_context_failure_disposition_zero_call_result_v1_0.json"
    )
    progress_ref = (
        "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
        "R15_downstream_repair_progress_checkpoint_v1_1.json"
    )
    repair_profile_ref = (
        "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_"
        "role_repair_analysis_high_profile_v1_0.json"
    )
    authority = json.loads(
        (ROOT / source_authority_ref).read_text(encoding="utf-8")
    )
    scope = json.loads((ROOT / scope_ref).read_text(encoding="utf-8"))

    def binding(ref: str) -> dict[str, str]:
        path = ROOT / ref
        return {"ref": ref, "sha256": runner._sha(path)}

    authority["schema_version"] = (
        runner.DOWNSTREAM_REPAIR_CONTEXT_REPLACEMENT_AUTHORITY_SCHEMA
    )
    authority["status"] = (
        "approved_for_one_R15_role_scoped_repair_context_"
        "replacement_after_project_os_preflight"
    )
    authority["implementation_commit"] = runner._git_head()
    for name in (
        "failed_continuation_authority",
        "failed_continuation_result",
        "continuation_profile_failure_disposition_zero_call_proof",
        "analysis_completion_profile",
    ):
        authority["bound_inputs"].pop(name)
    authority["bound_inputs"].update(
        {
            "project_os_scope_decision": binding(scope_ref),
            "predecessor_scope_decision": binding(
                scope["predecessor_scope_decision_ref"]
            ),
            "predecessor_authority": binding(
                scope["predecessor_live_authority_ref"]
            ),
            "predecessor_result": binding(
                scope["predecessor_live_result_ref"]
            ),
            "failed_repair_authority": binding(source_authority_ref),
            "failed_repair_result": binding(failed_result_ref),
            "repair_context_failure_disposition_zero_call_proof": binding(
                disposition_ref
            ),
            "downstream_repair_progress_checkpoint_v2": binding(
                progress_ref
            ),
            "repair_analysis_profile": binding(repair_profile_ref),
        }
    )
    authority["execution_limits"] = deepcopy(scope["execution_limits"])
    output_prefix = "data/pytest_multi_agent_preview_r15_authority_unused"
    authority["outputs"] = {
        "run_id": "PYTEST-R15-UNUSED",
        "capture_root_ref": output_prefix + "_captures",
        "private_output_root_ref": output_prefix + "_private",
        "public_result_ref": output_prefix + "_public.json",
    }
    authority["authority_statement"] = (
        "pytest-only fresh Supply repair after immutable R14 failure"
    )
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps(authority), encoding="utf-8")

    validated, inputs, outputs = runner._validate_authority(authority_path)

    assert validated["schema_version"] == (
        runner.DOWNSTREAM_REPAIR_CONTEXT_REPLACEMENT_AUTHORITY_SCHEMA
    )
    assert set(inputs) == set(authority["bound_inputs"])
    assert outputs["run_id"] == "PYTEST-R15-UNUSED"
    assert validated["execution_limits"][
        "reused_completed_challenge_repair_count"
    ] == 2
    assert validated["execution_limits"][
        "maximum_resumed_downstream_analysis_continuations"
    ] == 0
