from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from sec_agent.providers import ModelGatewayError


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/research/run_s3_current_dynamic_writer_live.py"
SPEC = importlib.util.spec_from_file_location("current_dynamic_writer_live", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def test_live_terminal_failure_materializes_immutable_public_private_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(RUNNER, "ROOT", tmp_path)
    authority_ref = "authority.json"
    _write(tmp_path / authority_ref, {"signed": True})
    request = (
        tmp_path
        / "captures"
        / "RUN"
        / "writer-analysis"
        / "model_visible_request.json"
    )
    _write(
        request,
        {
            "attempt_id": "writer-analysis",
            "request_digest": "request-digest",
        },
    )
    authority = {
        "run_id": "RUN",
        "implementation_commit": "a" * 40,
        "authority_digest": "authority-digest",
        "output_contract": {
            "capture_root_ref": "captures",
            "private_full_result_ref": "private/full_result.json",
            "public_result_ref": "public.json",
        },
    }
    decision = {"decision_digest": "decision-digest"}
    failure = ModelGatewayError(
        "model_gateway_transport_error",
        capture_ref=request.as_posix(),
    )

    public = RUNNER._materialize_terminal_failure(
        authority=authority,
        authority_ref=authority_ref,
        decision=decision,
        exc=failure,
    )

    private = json.loads(
        (tmp_path / "private/full_result.json").read_text(encoding="utf-8")
    )
    persisted_public = json.loads(
        (tmp_path / "public.json").read_text(encoding="utf-8")
    )
    assert public == persisted_public
    assert public["status"] == "terminal_protected_writer_failure_preserved"
    assert public["failure"]["code"] == "model_gateway_transport_error"
    assert public["execution"]["new_provider_calls_attempted"] == 1
    assert public["execution"]["new_provider_http_200"] == 0
    assert public["execution"]["retries"] == 0
    assert private["capture_manifest"][0]["response_present"] is False
    assert private["acceptance"]["S3_pass"] is False
    assert public["private_full_result_digest"] == private["full_result_digest"]

    with pytest.raises(
        RUNNER.CurrentDynamicWriterLiveError,
        match="current_dynamic_writer_live_output_identity_consumed",
    ):
        RUNNER._materialize_terminal_failure(
            authority=authority,
            authority_ref=authority_ref,
            decision=decision,
            exc=failure,
        )


def test_live_tool_payload_requires_exact_expected_call() -> None:
    step = RUNNER.ChatCompletionToolStepResult(
        status="completed_exact_once",
        provider_id="deepseek",
        model="deepseek-v4-pro",
        content="",
        reasoning_content="",
        tool_calls=(),
        finish_reason="stop",
        usage={},
        request_capture_ref="request.json",
        response_capture_ref="response.json",
        request_digest="request",
        response_digest="response",
        private_reasoning_fields_redacted=0,
    )
    with pytest.raises(
        RUNNER.CurrentDynamicWriterLiveError,
        match="current_dynamic_writer_live_tool_call_count_invalid",
    ):
        RUNNER._tool_payload(step)


def test_live_file_binding_accepts_non_json_implementation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(RUNNER, "ROOT", tmp_path)
    implementation = tmp_path / "implementation.py"
    implementation.write_text("VALUE = 1\n", encoding="utf-8")
    binding = {
        "ref": "implementation.py",
        "sha256": hashlib.sha256(implementation.read_bytes()).hexdigest(),
    }

    assert RUNNER._validate_file_binding(binding) is None
    with pytest.raises(
        RUNNER.CurrentDynamicWriterLiveError,
        match="current_dynamic_writer_live_binding_sha_drift",
    ):
        RUNNER._validate_file_binding({**binding, "sha256": "0" * 64})


def test_live_authority_requires_one_exact_authority_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    implementation_commit = "a" * 40
    authority_commit = "b" * 40
    authority_ref = "configs/research/evals/__writer_authority_test__.json"
    preflight_ref = "configs/research/evals/__writer_preflight_test__.json"
    bound_inputs = {"catalog": {"ref": "catalog.json", "sha256": "catalog"}}
    implementation_bindings = [
        {"ref": "src/sec_agent/example.py", "sha256": "implementation"}
    ]
    decision = {
        "bound_inputs": bound_inputs,
        "implementation_bindings": implementation_bindings,
        "execution_budget": RUNNER.expected_current_dynamic_writer_budget(),
        "token_budget_basis": {"writer": "bounded"},
    }
    preflight = {
        "status": "pass_current_decision_bound_preflight",
        "decision_ref": "decision.json",
        "decision_sha256": "decision-sha",
        "run_scope_id": RUNNER.CURRENT_DYNAMIC_WRITER_RUN_SCOPE,
        "repository": {
            "head": implementation_commit,
            "clean": True,
            "synced": True,
        },
        "model_calls": 0,
        "provider_calls": 0,
    }
    authority = {
        "schema_version": RUNNER.AUTHORITY_SCHEMA_VERSION,
        "status": "signed_exact_run_DELL_R10_protected_writer",
        "signed_at": "2026-08-24T00:00:00+08:00",
        "implementation_commit": implementation_commit,
        "case_key": "DELL",
        "run_scope_id": RUNNER.CURRENT_DYNAMIC_WRITER_RUN_SCOPE,
        "run_id": "WRITER_TEST",
        "decision": {
            "ref": "decision.json",
            "sha256": "decision-sha",
            "digest_field": "decision_digest",
            "digest": "decision-digest",
        },
        "project_os_preflight": {
            "ref": preflight_ref,
            "sha256": "preflight-sha",
        },
        "bound_inputs": bound_inputs,
        "implementation_bindings": implementation_bindings,
        "execution_budget": RUNNER.expected_current_dynamic_writer_budget(),
        "token_budget_basis": {"writer": "bounded"},
        "output_contract": {
            "public_result_ref": ".codex_runtime/__writer_test__/public.json",
            "private_full_result_ref": (
                ".codex_runtime/__writer_test__/private.json"
            ),
            "capture_root_ref": ".codex_runtime/__writer_test__/captures",
        },
        "authority_boundary": {
            "one_writer_analysis_call": True,
            "maximum_two_writer_submission_attempts": True,
            "transport_retries": 0,
            "upstream_agent_calls": 0,
            "new_S1_S2_retrieval_source_or_candidate_calls": 0,
            "writer_result_requires_independent_post_run_assessment": True,
            "S3_product_publication_and_release_authorized": False,
        },
    }
    authority["authority_digest"] = RUNNER.canonical_digest(
        RUNNER._authority_body(authority)
    )

    def fake_git(*args: str) -> str:
        if args[0] == "merge-base":
            return implementation_commit
        if args[0] == "rev-list":
            return "1"
        if args[0] == "diff":
            return preflight_ref + "\n" + authority_ref
        raise AssertionError(args)

    def fake_binding(binding):
        if binding.get("ref") == "decision.json":
            return decision
        if binding.get("ref") == preflight_ref:
            return preflight
        return {}

    monkeypatch.setattr(RUNNER, "_clean_synced_head", lambda: authority_commit)
    monkeypatch.setattr(RUNNER, "_git", fake_git)
    monkeypatch.setattr(RUNNER, "_sha", lambda _ref: "authority-sha")
    monkeypatch.setattr(RUNNER, "_validate_binding", fake_binding)
    monkeypatch.setattr(RUNNER, "_validate_file_binding", lambda _binding: None)
    monkeypatch.setattr(
        RUNNER,
        "_git_blob_sha256",
        lambda *, commit, ref: (
            "authority-sha" if ref == authority_ref else "implementation"
        ),
    )

    assert RUNNER._validate_authority(
        authority, authority_ref=authority_ref
    ) == decision

    def two_commit_git(*args: str) -> str:
        if args[0] == "rev-list":
            return "2"
        return fake_git(*args)

    monkeypatch.setattr(RUNNER, "_git", two_commit_git)
    with pytest.raises(
        RUNNER.CurrentDynamicWriterLiveError,
        match="current_dynamic_writer_live_authority_commit_chain_invalid",
    ):
        RUNNER._validate_authority(authority, authority_ref=authority_ref)
