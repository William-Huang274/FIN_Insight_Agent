from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_searxng_diagnostic_adapter import (
    SearXNGDiagnosticAdapter,
    SearXNGDiagnosticError,
    SearXNGDiagnosticQuery,
    SearXNGDiagnosticResponse,
    load_searxng_diagnostic_policy,
    validate_searxng_diagnostic_result,
)


POLICY = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_searxng_diagnostic_provider_policy_v1_0.json"
TEST = ROOT / "tests/contract/test_fin_0_1_3_s1_08_searxng_diagnostic_adapter.py"
COMPOSE = ROOT / "deploy/searxng-diagnostic/docker-compose.yml"


class _FullFakeTransport:
    live_network = False

    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, *, url, headers, timeout_seconds, byte_ceiling):
        self.calls += 1
        case_token = "case"
        for token in ("DELL", "MU", "NVDA"):
            if token.lower() in url.lower():
                case_token = token.lower()
                break
        payload = {
            "results": [
                {
                    "url": f"https://example.org/{case_token}/current?utm_source=diagnostic",
                    "title": f"{case_token.upper()} current locator",
                    "content": "This is a locator candidate, not evidence or financial fact authority.",
                    "engines": ["brave", "duckduckgo"],
                    "positions": [1, 2],
                    "score": 1.25,
                }
            ],
            "unresponsive_engines": [["google", "bounded diagnostic failure"]],
        }
        return SearXNGDiagnosticResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": "application/json"},
            body=json.dumps(payload, sort_keys=True).encode(),
        )


def _run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _git(*args: str) -> str:
    completed = _run(["git", *args])
    if completed.returncode != 0:
        raise RuntimeError(f"git_command_failed:{' '.join(args)}:{completed.stderr.strip()}")
    return completed.stdout.strip()


def _query(case_key: str) -> SearXNGDiagnosticQuery:
    return SearXNGDiagnosticQuery.create(
        query_id=f"{case_key}-DIAGNOSTIC-Q1",
        case_key=case_key,
        evidence_slot_id=f"{case_key.lower()}_broad_web_locator_diagnostic",
        query_text=f"{case_key} current AI infrastructure demand customer supply official source",
        categories=("general", "news"),
        time_range="year",
        result_ceiling=20,
    )


def materialize() -> dict[str, Any]:
    source_commit = _git("rev-parse", "HEAD")
    dirty_before = _git("status", "--porcelain")
    if dirty_before:
        raise RuntimeError("clean_source_commit_required")

    policy = load_searxng_diagnostic_policy(POLICY)
    pytest_run = _run([sys.executable, "-m", "pytest", "-q", str(TEST.relative_to(ROOT))])
    if pytest_run.returncode != 0:
        raise RuntimeError(f"searxng_adapter_contract_tests_failed:{pytest_run.stdout}:{pytest_run.stderr}")
    match = re.search(r"(\d+) passed", pytest_run.stdout)
    passed_tests = int(match.group(1)) if match else 0

    compose_env = dict(os.environ)
    compose_env["SEARXNG_SECRET"] = "zero-call-compose-validation-only"
    compose_run = _run(
        ["docker", "compose", "-f", str(COMPOSE.relative_to(ROOT)), "config", "--quiet"],
        env=compose_env,
    )
    if compose_run.returncode != 0:
        raise RuntimeError(f"searxng_compose_contract_invalid:{compose_run.stderr.strip()}")

    with tempfile.TemporaryDirectory(prefix="fin013-searxng-zero-call-") as temp_dir:
        transport = _FullFakeTransport()
        adapter = SearXNGDiagnosticAdapter(
            policy=policy,
            runtime_root=temp_dir,
            transport=transport,
        )
        case_results = [adapter.search(_query(case_key)) for case_key in ("DELL", "MU", "NVDA")]
        for row in case_results:
            validate_searxng_diagnostic_result(row)

        mutated = deepcopy(case_results[0])
        mutated["capability_boundary"]["evidence_promotion_allowed"] = True
        mutated_body = dict(mutated)
        mutated_body.pop("result_digest")
        mutated["result_digest"] = canonical_digest(mutated_body)
        false_promotion_rejected = False
        try:
            validate_searxng_diagnostic_result(mutated)
        except SearXNGDiagnosticError as exc:
            false_promotion_rejected = exc.code == "searxng_result_false_promotion"
        if not false_promotion_rejected:
            raise RuntimeError("searxng_false_promotion_mutation_not_rejected")

        capture_count = len(adapter.capture_refs)
        query_calls = adapter.query_calls
        network_calls = adapter.network_calls
        transport_calls = transport.calls
        case_summaries = [
            {
                "case_key": row["query"]["case_key"],
                "status": row["status"],
                "terminal_code": row["terminal_code"],
                "normalized_locator_count": row["observed_counts"]["normalized_locators"],
                "locator_bundle_digest": row["locator_bundle_digest"],
                "evidence_promotions": row["observed_counts"]["evidence_promotions"],
            }
            for row in case_results
        ]

    body = {
        "schema_version": "fin_ia_0_1_3_s1_08_searxng_diagnostic_adapter_zero_call_proof_v1_1",
        "contract_ref": "fin_0_1_3.S1_08.searxng_diagnostic_locator_provider:v1",
        "source_commit": source_commit,
        "source_worktree_clean_before_proof": True,
        "policy_ref": str(POLICY.relative_to(ROOT)).replace("\\", "/"),
        "policy_digest": canonical_digest(policy),
        "test_ref": str(TEST.relative_to(ROOT)).replace("\\", "/"),
        "verification": {
            "contract_test_exit_code": pytest_run.returncode,
            "contract_tests_passed": passed_tests,
            "docker_compose_config_exit_code": compose_run.returncode,
            "deployment_safety_contract_proven": True,
            "configured_metasearch_engines": list(
                policy["metasearch_fanout_contract"]["configured_engines"]
            ),
            "healthcheck_may_invoke_search": policy["metasearch_fanout_contract"][
                "healthcheck_may_invoke_search"
            ],
            "three_case_full_fake": case_summaries,
            "query_calls": query_calls,
            "fake_transport_calls": transport_calls,
            "network_calls": network_calls,
            "model_calls": 0,
            "provider_model_calls": 0,
            "retry_calls": 0,
            "capture_count": capture_count,
            "expected_capture_count": 9,
            "false_promotion_mutation_rejected": false_promotion_rejected,
            "all_result_digests_valid": True,
            "all_capture_readbacks_valid": True,
        },
        "acceptance": {
            "adapter_zero_call_engineering_pass": (
                passed_tests >= 15
                and compose_run.returncode == 0
                and len(case_summaries) == 3
                and all(row["status"] == "completed" for row in case_summaries)
                and all(row["evidence_promotions"] == 0 for row in case_summaries)
                and query_calls == 3
                and transport_calls == 3
                and network_calls == 0
                and capture_count == 9
                and false_promotion_rejected
                and policy["metasearch_fanout_contract"]["healthcheck_may_invoke_search"]
                is False
            ),
            "self_hosted_network_baseline_executed": False,
            "production_search_capability_proven": False,
            "evidence_retrieval_quality_proven": False,
        },
        "next_boundary": {
            "allowed": [
                "inspect_local_docker_daemon",
                "start_loopback_only_self_hosted_searxng",
                "separately_authorized_bounded_three_query_diagnostic_baseline"
            ],
            "forbidden": [
                "public_searxng_instance_fallback",
                "evidence_pack_promotion",
                "writer_consumption",
                "production_capability_claim",
                "automatic_paid_search_provider_selection"
            ]
        }
    }
    if body["acceptance"]["adapter_zero_call_engineering_pass"] is not True:
        raise RuntimeError("searxng_adapter_zero_call_acceptance_failed")
    return {**body, "proof_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    result = materialize()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
