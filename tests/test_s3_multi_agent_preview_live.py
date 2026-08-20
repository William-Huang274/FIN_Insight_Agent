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
