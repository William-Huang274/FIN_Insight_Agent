from __future__ import annotations

import argparse
import base64
from datetime import datetime
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Mapping
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
ENGINEERING_PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_"
    "mature_component_relationship_budget_zero_call_proof_v1_0.json"
)
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_v3_"
    "clean_independent_zero_call_proof_result_v1_0.json"
)
R2_OBJECT_ROOT = ROOT / (
    ".codex_runtime/fin013_s1_08_dell_current_search_r2/"
    "fin013_s1_08_dell_r2_admission_3de480abf1cfd6db5037/adapter/objects/"
    "fin-0.1.3/s1-08/current-source-discovery"
)
CURRENT_ACTION = (
    "S1_08_V3_MATURE_COMPONENT_RELATIONSHIP_BUDGET_"
    "CLEAN_INDEPENDENT_ZERO_CALL_PROOF"
)
NEXT_ACTION = "S1_08_V3_DELL_FRESH_LIVE_AUTHORITY_DECISION"
EXPECTED_DEPENDENCIES = {
    "feedparser": "6.0.12",
    "trafilatura": "2.1.0",
    "lxml": "6.1.1",
}
R2_CAPTURES = {
    "1b16c1d89b47e5c20f1ef20ee021f1c166fb938ca94faf0d2bd87c2326c1294c": {
        "body_sha256": (
            "94e5a8f806f03fa13a2d94107b6a32a6bfe6a10090eb41adc5f84ba3fb5f7b8a"
        ),
        "expected_date": "2026-07-29",
        "expected_source": "official_event_heading",
    },
    "7306f99976f05c7bca0574148d0c12ed6e4bac55a3f71f22237960b6973062cb": {
        "body_sha256": (
            "9bcb8759d663b50b91245b5f2bc4f8e0362bccf9aa83fe83fceb155621aa0995"
        ),
        "expected_date": "2026-07-29",
        "expected_source": "official_release_masthead",
    },
}
PYTEST_TARGETS = (
    "tests/contract/test_fin_0_1_3_s1_08_agentic_search_entry_audit.py",
    "tests/contract/test_fin_0_1_3_s1_08_candidate_generation_runtime.py",
    "tests/contract/test_fin_0_1_3_s1_08_dell_current_search_r1_terminal.py",
    "tests/contract/test_fin_0_1_3_s1_08_dell_r2_successor.py",
    "tests/contract/test_fin_0_1_3_s1_08_live_canary.py",
    "tests/contract/test_fin_0_1_3_s1_08_mature_component_v3_runtime.py",
    "tests/contract/test_fin_0_1_3_s1_08_quality_first_sourcehunter_capture_replay.py",
    "tests/contract/test_fin_0_1_3_s1_08_quality_first_sourcehunter_capture_replay_plan.py",
)
REQUIRED_TEST_FRAGMENTS = (
    "test_v3_three_case_round_robin_full_fake_has_no_slot_starvation[DELL]",
    "test_v3_three_case_round_robin_full_fake_has_no_slot_starvation[MU]",
    "test_v3_three_case_round_robin_full_fake_has_no_slot_starvation[NVDA]",
    "test_v3_relationship_and_date_mutations_fail_closed[missing_subject-relationship_binding_mismatch]",
    "test_v3_relationship_and_date_mutations_fail_closed[wrong_owner-relationship_binding_mismatch]",
    "test_v3_relationship_and_date_mutations_fail_closed[untyped_date-typed_publication_date_binding_invalid]",
    "test_actual_immutable_dell_r2_microsoft_captures_recover_financial_dates",
    "test_document_fetch_ceiling_is_real_not_only_an_acceptance_ceiling",
    "test_nested_customer_story_is_rejected_before_document_fetch",
)
SCRUBBED_ENVIRONMENT_MARKERS = (
    "API_KEY",
    "AUTHORIZATION",
    "ACCESS_TOKEN",
    "COOKIE",
    "PASSWORD",
    "SECRET",
    "FINSIGHT_SEC_CONTACT_EMAIL",
)


class S108V3CleanProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S108V3CleanProofError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _capture_path(root: Path, object_digest: str) -> Path:
    return root / object_digest[:2] / object_digest[2:4] / f"{object_digest}.json"


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    _require(
        completed.returncode == 0,
        "git_command_failed:" + ":".join(args) + ":" + completed.stderr[-500:],
    )
    return completed.stdout.strip()


def _assert_clean_synced_head() -> dict[str, Any]:
    _require(not _git("status", "--porcelain"), "source_worktree_not_clean")
    head = _git("rev-parse", "HEAD")
    upstream = _git("rev-parse", "@{upstream}")
    _require(head == upstream, "source_head_not_synced_to_upstream")
    return {
        "commit": head,
        "upstream_commit": upstream,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "clean": True,
        "synced": True,
    }


def _verify_engineering_proof(root: Path) -> dict[str, str]:
    proof_path = root / ENGINEERING_PROOF.relative_to(ROOT)
    proof = _load(proof_path)
    _require(
        proof["status"]
        == "zero_call_engineering_pass_independent_proof_and_live_authority_pending",
        "engineering_proof_status_invalid",
    )
    _require(
        proof["authority"]["network_calls_authorized"] == 0
        and proof["authority"]["model_calls_authorized"] == 0
        and proof["authority"]["provider_calls_authorized"] == 0,
        "engineering_proof_authority_invalid",
    )
    observed: dict[str, str] = {}
    for binding in proof["implementation_inputs"]:
        relative = str(binding["path"])
        digest = _sha256(root / relative)
        _require(digest == binding["sha256"], f"implementation_binding_drift:{relative}")
        observed[relative] = digest
    return observed


def _source_capture_manifest() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for object_digest, expected in R2_CAPTURES.items():
        path = _capture_path(R2_OBJECT_ROOT, object_digest)
        _require(path.exists(), f"restricted_R2_capture_missing:{object_digest}")
        capture = _load(path)
        _require(
            capture.get("body_sha256") == expected["body_sha256"],
            f"restricted_R2_body_digest_drift:{object_digest}",
        )
        rows[object_digest] = {
            "file_sha256": _sha256(path),
            "body_sha256": capture["body_sha256"],
            "bytes": path.stat().st_size,
        }
    return rows


def _extract_clean_archive(commit: str, target: Path) -> None:
    archive_path = target.parent / f"{target.name}.tar"
    with archive_path.open("wb") as handle:
        completed = subprocess.run(
            ["git", "archive", "--format=tar", commit],
            cwd=ROOT,
            stdout=handle,
            stderr=subprocess.PIPE,
            check=False,
        )
    _require(completed.returncode == 0, "git_archive_failed")
    target.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive_path, "r") as archive:
        archive.extractall(target)
    archive_path.unlink()


def _inject_restricted_captures(target: Path) -> dict[str, Any]:
    destination_root = target / R2_OBJECT_ROOT.relative_to(ROOT)
    rows: dict[str, Any] = {}
    for object_digest in R2_CAPTURES:
        source = _capture_path(R2_OBJECT_ROOT, object_digest)
        destination = _capture_path(destination_root, object_digest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        _require(_sha256(source) == _sha256(destination), f"capture_copy_drift:{object_digest}")
        rows[object_digest] = {
            "file_sha256": _sha256(destination),
            "body_sha256": _load(destination)["body_sha256"],
            "bytes": destination.stat().st_size,
        }
    return rows


class _StablePytestResult:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.skipped: list[str] = []

    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.when != "call":
            return
        if report.passed:
            self.passed.append(str(report.nodeid))
        elif report.failed:
            self.failed.append(str(report.nodeid))
        elif report.skipped:
            self.skipped.append(str(report.nodeid))


def _worker_payload(runtime_root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(runtime_root / "src"))
    network_attempts: list[str] = []

    def blocked_network(*args: Any, **kwargs: Any) -> Any:
        network_attempts.append("socket")
        raise RuntimeError("s1_08_v3_clean_proof_network_forbidden")

    socket.socket.connect = blocked_network  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked_network  # type: ignore[method-assign]
    socket.create_connection = blocked_network

    import pytest

    from sec_agent.s1_08_official_content_tools import parse_official_html_capture

    dependency_versions = {package: version(package) for package in EXPECTED_DEPENDENCIES}
    _require(dependency_versions == EXPECTED_DEPENDENCIES, "dependency_version_drift")
    implementation_bindings = _verify_engineering_proof(runtime_root)

    plugin = _StablePytestResult()
    exit_code = pytest.main(
        ["-q", "--disable-warnings", *PYTEST_TARGETS],
        plugins=[plugin],
    )
    _require(exit_code == 0, f"pytest_failed:{exit_code}")
    _require(not plugin.failed, "pytest_reported_failure")
    _require(not plugin.skipped, "pytest_reported_skip")
    _require(len(plugin.passed) == 60, "unexpected_passed_test_count")
    nodeids = sorted(plugin.passed)
    for fragment in REQUIRED_TEST_FRAGMENTS:
        _require(
            any(fragment in nodeid for nodeid in nodeids),
            f"required_test_missing:{fragment}",
        )

    date_decisions: dict[str, Any] = {}
    worker_object_root = runtime_root / R2_OBJECT_ROOT.relative_to(ROOT)
    for object_digest, expected in R2_CAPTURES.items():
        path = _capture_path(worker_object_root, object_digest)
        capture = _load(path)
        parsed = parse_official_html_capture(
            body=base64.b64decode(capture["body_base64"]),
            final_url=capture["final_url"],
            headers=capture["headers"],
            as_of="2026-08-06",
            capture_ref=f"restricted://DELL-R2/{object_digest}",
            capture_digest=object_digest,
        )
        decision = parsed.publication_date
        _require(decision.date_value == expected["expected_date"], f"date_drift:{object_digest}")
        _require(decision.date_source == expected["expected_source"], f"date_source_drift:{object_digest}")
        date_decisions[object_digest] = {
            "body_sha256": capture["body_sha256"],
            "date_value": decision.date_value,
            "date_kind": decision.date_kind,
            "date_source": decision.date_source,
            "date_confidence": decision.date_confidence,
            "conflict_status": decision.conflict_status,
            "rejected_reporting_period_dates": sorted(
                {
                    row.date_value
                    for row in decision.candidates
                    if row.date_kind == "reporting_period_end"
                    and row.date_confidence == "rejected"
                }
            ),
            "rejected_reporting_period_sources": sorted(
                {
                    row.date_source
                    for row in decision.candidates
                    if row.date_kind == "reporting_period_end"
                    and row.date_confidence == "rejected"
                }
            ),
        }
    _require(
        date_decisions[
            "7306f99976f05c7bca0574148d0c12ed6e4bac55a3f71f22237960b6973062cb"
        ]["rejected_reporting_period_dates"]
        == ["2026-06-30"],
        "reporting_period_rejection_not_reproduced",
    )
    _require(not network_attempts, "network_attempt_observed")

    return {
        "schema_version": "fin_ia_0_1_3_s1_08_v3_clean_independent_worker_v1_0",
        "status": "pass",
        "dependency_versions": dependency_versions,
        "implementation_bindings": implementation_bindings,
        "restricted_R2_capture_date_decisions": date_decisions,
        "pytest": {
            "passed": len(nodeids),
            "failed": 0,
            "skipped": 0,
            "nodeids": nodeids,
        },
        "coverage": {
            "DELL_MU_NVDA_round_robin_full_fake": True,
            "relationship_and_date_mutations_fail_closed": True,
            "actual_R2_publication_date_adjudication": True,
            "nested_relationship_prefetch_rejection": True,
            "document_fetch_ceiling": True,
        },
        "hard_boundaries": {
            "credential_values_present_or_read": 0,
            "network_attempts": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "retry_calls": 0,
            "admissions_issued": 0,
            "live_runs": 0,
        },
    }


def _clean_child_environment(runtime_root: Path) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not any(marker in key.upper() for marker in SCRUBBED_ENVIRONMENT_MARKERS)
    }
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "LLM_GATEWAY_TRANSPORT_RETRIES": "0",
            "TMP": str(runtime_root / ".tmp"),
            "TEMP": str(runtime_root / ".tmp"),
            "PYTHONPYCACHEPREFIX": str(runtime_root / ".pycache"),
        }
    )
    return environment


def _run_worker(runtime_root: Path, output_path: Path) -> dict[str, Any]:
    (runtime_root / ".tmp").mkdir(parents=True, exist_ok=True)
    worker_script = runtime_root / Path(__file__).resolve().relative_to(ROOT)
    completed = subprocess.run(
        [
            sys.executable,
            str(worker_script),
            "--worker",
            "--runtime-root",
            str(runtime_root),
            "--output",
            str(output_path),
        ],
        cwd=runtime_root,
        env=_clean_child_environment(runtime_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    _require(
        completed.returncode == 0,
        "fresh_worker_failed:"
        + str(completed.returncode)
        + ":"
        + completed.stdout[-5000:]
        + ":"
        + completed.stderr[-3000:],
    )
    _require(output_path.exists(), "fresh_worker_output_missing")
    return _load(output_path)


def build_result() -> dict[str, Any]:
    git_state = _assert_clean_synced_head()
    implementation_bindings = _verify_engineering_proof(ROOT)
    source_captures_before = _source_capture_manifest()

    worker_payloads: list[dict[str, Any]] = []
    worker_bytes: list[bytes] = []
    injected_manifests: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="fin013-s1-08-v3-clean-proof-") as parent:
        parent_path = Path(parent).resolve()
        _require(parent_path.name.startswith("fin013-s1-08-v3-clean-proof-"), "temporary_root_invalid")
        for ordinal in (1, 2):
            runtime_root = parent_path / f"clean-archive-{ordinal}"
            _extract_clean_archive(git_state["commit"], runtime_root)
            injected_manifests.append(_inject_restricted_captures(runtime_root))
            output_path = runtime_root / f"worker-result-{ordinal}.json"
            payload = _run_worker(runtime_root, output_path)
            worker_payloads.append(payload)
            worker_bytes.append(_canonical_bytes(payload))
        _require(worker_bytes[0] == worker_bytes[1], "fresh_worker_outputs_differ")
        _require(
            injected_manifests[0] == injected_manifests[1],
            "fresh_worker_injected_inputs_differ",
        )

    source_captures_after = _source_capture_manifest()
    _require(source_captures_before == source_captures_after, "source_captures_changed")
    _require(
        _verify_engineering_proof(ROOT) == implementation_bindings,
        "implementation_binding_changed_during_proof",
    )
    _require(not _git("status", "--porcelain"), "worktree_changed_during_proof")

    body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_08_v3_clean_independent_"
            "zero_call_proof_result_v1_0"
        ),
        "proof_id": CURRENT_ACTION,
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "stage": "013-S1-08",
        "status": "pass_two_clean_archives_two_fresh_processes_zero_call_reproducible",
        "source_commit": git_state,
        "source_bindings": {
            "engineering_proof_ref": ENGINEERING_PROOF.relative_to(ROOT).as_posix(),
            "engineering_proof_sha256": _sha256(ENGINEERING_PROOF),
            "implementation_files": implementation_bindings,
            "proof_runner_ref": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "proof_runner_sha256": _sha256(Path(__file__).resolve()),
        },
        "independent_proof": {
            "clean_git_archives": 2,
            "fresh_python_processes": 2,
            "distinct_disposable_roots": 2,
            "restricted_R2_captures_injected": len(R2_CAPTURES),
            "restricted_R2_captures_byte_identical": True,
            "restricted_raw_body_or_headers_emitted": False,
            "normalized_outputs_equal": True,
            "normalized_output_sha256": hashlib.sha256(worker_bytes[0]).hexdigest(),
            "worker_result": worker_payloads[0],
            "temporary_roots_removed": True,
        },
        "source_read_only_audit": {
            "restricted_R2_before": source_captures_before,
            "restricted_R2_after": source_captures_after,
            "restricted_R2_unchanged": True,
            "repository_status_unchanged_until_result_write": True,
        },
        "acceptance_boundary": {
            "S1_08_v3_deterministic_engineering": "independently_proven",
            "mature_component_dependency_reproducibility": "pass",
            "actual_R2_date_adjudication_reproducibility": "pass",
            "DELL_MU_NVDA_fake_and_mutation_reproducibility": "pass",
            "fresh_live_source_reachability": "not_run_not_proven",
            "target_in_pool_and_required_slot_recall": "not_run_not_proven",
            "ranking_and_selected_evidence_pack": "not_admitted",
            "research_content_quality": "not_measured",
            "business_promotion": False,
            "release": False,
        },
        "observed_counts": {
            "network_calls": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "retry_calls": 0,
            "admissions_issued": 0,
            "live_runs": 0,
        },
        "next_action": NEXT_ACTION,
        "next_action_authorized": False,
        "known_boundary": (
            "This dual clean-archive proof establishes deterministic S1-08 v3 "
            "reproducibility, dependency identity, immutable R2 date adjudication, "
            "and three-case fake/mutation behavior only. It does not prove fresh "
            "source reachability, target-in-pool, ranking, Evidence promotion, "
            "DeepSeek behavior, research-content quality or release readiness."
        ),
    }
    return {**body, "result_digest": _canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--output", type=Path, default=RESULT)
    args = parser.parse_args()
    if args.worker:
        _require(args.runtime_root is not None, "worker_runtime_root_required")
        payload = _worker_payload(args.runtime_root.resolve())
    else:
        payload = build_result()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if not args.worker:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
