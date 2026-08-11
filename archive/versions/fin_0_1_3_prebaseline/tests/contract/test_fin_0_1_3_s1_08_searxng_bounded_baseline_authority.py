from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.project_os_preflight import run_project_os_preflight


AUTHORITY = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_searxng_bounded_diagnostic_baseline_authority_v1_0.json"
POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_searxng_diagnostic_provider_policy_v1_0.json"
PROOF = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_searxng_diagnostic_adapter_zero_call_proof_v1_1.json"
RUNNER = ROOT / "scripts/releases/run_fin_ia_0_1_3_s1_08_searxng_bounded_diagnostic_baseline.py"
RESULT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_searxng_bounded_diagnostic_baseline_result_v1_0.json"
QUALITY = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_searxng_bounded_diagnostic_baseline_quality_assessment_v1_0.json"
POST_TERMINAL_FAILURE = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_searxng_bounded_diagnostic_baseline_post_terminal_display_failure_v1_0.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runner_module():
    spec = importlib.util.spec_from_file_location("searxng_bounded_baseline_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _historical_blob_sha256(commit: str, path: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return hashlib.sha256(completed.stdout).hexdigest()


def test_authority_is_digest_bound_to_passed_adapter_policy_and_runner() -> None:
    module = _runner_module()
    authority = module.load_authority(AUTHORITY)
    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    policy = json.loads(POLICY.read_text(encoding="utf-8"))

    assert authority["adapter_proof_digest"] == proof["proof_digest"]
    assert authority["adapter_proof_file_sha256"] == _sha256(PROOF)
    assert authority["policy_digest"] == canonical_digest(policy)
    assert authority["policy_file_sha256"] == _sha256(POLICY)
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert authority["runner_sha256"] == _historical_blob_sha256(
        result["source_commit"], authority["runner_ref"]
    )
    assert result["admission_digest"] == authority["authority_digest"]
    assert result["admission_consumed"] is True
    assert proof["acceptance"]["adapter_zero_call_engineering_pass"] is True


def test_authority_is_exactly_three_cases_zero_retry_and_non_promotable() -> None:
    authority = _runner_module().load_authority(AUTHORITY)
    assert [row["case_key"] for row in authority["queries"]] == ["DELL", "MU", "NVDA"]
    assert len({row["query_id"] for row in authority["queries"]}) == 3
    contract = authority["execution_contract"]
    assert contract["fin_to_searxng_query_call_ceiling"] == 3
    assert contract["configured_engine_ceiling_per_query"] == 4
    assert contract["retry_ceiling"] == 0
    assert contract["model_call_ceiling"] == 0
    assert contract["public_instance_fallback_allowed"] is False
    assert contract["downstream_document_fetch_allowed"] is False
    assert contract["evidence_promotion_allowed"] is False
    assert contract["writer_consumption_allowed"] is False
    assert contract["production_capability_claim_allowed"] is False


def test_post_terminal_console_repair_does_not_reauthorize_consumed_run() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    authority = _runner_module().load_authority(AUTHORITY)
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert "ensure_ascii=True" in source
    assert _sha256(RUNNER) != authority["runner_sha256"]
    assert result["acceptance"]["bounded_diagnostic_execution_materialized"] is True
    failure = json.loads(POST_TERMINAL_FAILURE.read_text(encoding="utf-8"))
    assert failure["runtime_result_ref"] == f'{result["runtime_root"]}/execution-result.json'
    assert failure["result_files_identical"] is True


def test_materialized_baseline_is_digest_valid_byte_identical_and_non_promotable() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    runtime_result = ROOT / result["runtime_root"] / "execution-result.json"
    body = {key: value for key, value in result.items() if key != "result_digest"}

    assert result["result_digest"] == canonical_digest(body)
    if runtime_result.exists():
        assert RESULT.read_bytes() == runtime_result.read_bytes()
    assert result["summary"]["formal_case_queries"] == 3
    assert result["summary"]["fin_to_searxng_query_calls"] == 3
    assert result["summary"]["adapter_observed_network_calls"] == 3
    assert result["summary"]["raw_locator_rows"] == 30
    assert result["summary"]["normalized_unique_locators"] == 30
    assert result["summary"]["capture_count"] == 9
    assert result["summary"]["evidence_promotions"] == 0
    assert result["summary"]["model_calls"] == 0
    assert result["summary"]["retry_calls"] == 0

    locators = [
        locator
        for case in result["case_results"]
        for locator in case["result"]["locators"]
    ]
    assert len(locators) == 30
    assert {engine for row in locators for engine in row["source_engines"]} == {"duckduckgo"}
    assert all(row["published_on_candidate"] == "" for row in locators)
    assert all(row["promotion_status"] == "diagnostic_locator_only" for row in locators)
    assert all(row["evidence_promotion_allowed"] is False for row in locators)
    assert all(row["writer_citable"] is False for row in locators)
    assert all(row["financial_fact_authority"] is False for row in locators)


def test_quality_and_post_terminal_failure_preserve_honest_disposition() -> None:
    quality = json.loads(QUALITY.read_text(encoding="utf-8"))
    failure = json.loads(POST_TERMINAL_FAILURE.read_text(encoding="utf-8"))
    result = json.loads(RESULT.read_text(encoding="utf-8"))

    assert quality["status"] == "diagnostic_execution_pass_multi_engine_and_currentness_quality_fail"
    assert quality["assessment"]["multi_engine_comparison"] == "fail_effective_engine_count_1"
    assert quality["assessment"]["currentness_metadata"] == "fail_0_of_30_have_date"
    assert quality["disposition"]["rerun_same_baseline"] is False
    assert quality["disposition"]["SearXNG_provider_state"] == "diagnostic_live_measured_not_production"
    assert failure["status"] == "business_terminal_materialized_process_exit_failed"
    assert failure["terminal_phase"] == "post_terminal_console_display"
    assert failure["admission_consumed"] is True
    assert failure["rerun_performed"] is False
    assert failure["result_digest"] == result["result_digest"]


def test_consumed_baseline_and_product_live_remain_blocked() -> None:
    baseline = run_project_os_preflight(
        ROOT,
        run_scope="S1_08_DIAGNOSTIC_BROAD_SEARCH_SEARXNG_BOUNDED_NETWORK_BASELINE",
    )
    product_live = run_project_os_preflight(
        ROOT,
        run_scope="S1_08_V3_DELL_R3_EXACT_LIVE_ISSUANCE_AND_EXECUTION",
    )
    hygiene = run_project_os_preflight(ROOT, run_scope="repository_and_git_hygiene")

    assert baseline["status"] == "blocked"
    assert product_live["status"] == "blocked"
    assert hygiene["status"] == "pass"
    assert baseline["contract_errors"] == []
    assert product_live["contract_errors"] == []
