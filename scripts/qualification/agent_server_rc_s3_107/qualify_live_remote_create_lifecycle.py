"""RC-S3-107 zero-model live qualification host runner.

This runner is deliberately fail closed.  It defines the bounded K0-K6 matrix,
checks that the repository and the immutable Agent Server catalog are ready, and
only then permits a fresh Docker Compose project to be created.  It never retries
an invocation and it never removes containers or volumes.

The current file is the host-side qualification surface.  Scenario mechanics
live in ``live_killpoint_phase.py``; the readiness gate also requires the
concurrently owned production client/identity/SQL contract to be frozen before
``main`` can start Docker.  Keeping that gate here prevents implemented-but-
unqualified mechanics from being mistaken for a completed live proof.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[3]
EXPECTED_BRANCH = "codex/fin013-dell-s1-s2-product-bridge"
PROJECT_PREFIX = "finsight-dell-qualification-rc-s3-107"
DEFAULT_API_PORT = 18131
ARTIFACT_ROOT = Path(
    os.environ.get(
        "FIN_RC_S3_107_ARTIFACT_ROOT",
        r"Z:\FIN_Insight_Agent_qualification\dell_reference_vertical"
        r"\agent_server_control_plane\attempts",
    )
)
BASE_COMPOSE = ROOT / "deploy" / "dell_agent_server" / "compose.yaml"
OVERLAY_COMPOSE = (
    ROOT
    / "deploy"
    / "dell_agent_server"
    / "compose.zero-model-rc-s3-107-qualification.yaml"
)
PHASE_SCRIPT_IN_CONTAINER = (
    "/opt/fin-insight-qualification/rc-s3-107/live_killpoint_phase.py"
)
FOUNDATION_PATH = (
    ROOT
    / "configs"
    / "research"
    / "fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
)

CATALOG_FILES = (
    ROOT
    / "deploy"
    / "dell_agent_server"
    / "postgres-init"
    / "025-install-fin-runtime-lifecycle-v1-1.sh",
    ROOT
    / "deploy"
    / "dell_agent_server"
    / "postgres-init"
    / "031-runtime-readiness-v1-1.sh",
)
CATALOG_PLACEHOLDER = "__RC_S3_107_V1_1_CATALOG_SHA256_PENDING_REAL_POSTGRES__"
CATALOG_ASSIGNMENT_RE = re.compile(
    r"(?m)^expected_v1_1_catalog_sha256=(?P<value>[^\s#]+)\s*$"
)

FORBIDDEN_RECEIPT_KEYS = (
    "authorization",
    "api_key",
    "apikey",
    "password",
    "postgres_uri",
    "token",
    "secret",
    "raw_state",
    "raw_payload",
    "evidence_text",
    "prompt",
)
SECRET_VALUE_RE = re.compile(
    r"(?i)(?:bearer\s+[A-Za-z0-9._~-]+|(?:sk|key)-[A-Za-z0-9_-]{12,})"
)
HOST_PATH_RE = re.compile(r"(?i)(?:[A-Z]:\\|/Users/|/home/)")


class QualificationError(RuntimeError):
    """A typed, owner-visible qualification blocker."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if detail is None else f"{code}: {detail}")


@dataclasses.dataclass(frozen=True)
class ScenarioContract:
    scenario_id: str
    title: str
    kill_point: str
    expected_sdk_create_calls: int
    expected_remote_runs: int
    expected_invocation_count: int
    restart_required: bool
    proof: tuple[str, ...]
    implementation_state: str
    blocker_code: str | None = None


SCENARIOS: tuple[ScenarioContract, ...] = (
    ScenarioContract(
        scenario_id="K0",
        title="normal_control",
        kill_point="none",
        expected_sdk_create_calls=1,
        expected_remote_runs=1,
        expected_invocation_count=1,
        restart_required=False,
        proof=("PENDING", "ORPHAN", "RECONCILED", "FINAL"),
        implementation_state="ready",
        blocker_code=None,
    ),
    ScenarioContract(
        scenario_id="K1",
        title="crash_at_both_pre_sdk_create_commit_boundaries",
        kill_point=(
            "after_pending_before_dispatch_and_after_dispatched_before_sdk_create"
        ),
        expected_sdk_create_calls=0,
        expected_remote_runs=0,
        expected_invocation_count=2,
        restart_required=False,
        proof=(
            "PENDING_FAILED_BEFORE_DISPATCH",
            "DISPATCHED_AMBIGUOUS_WITHOUT_CREATE",
            "RECOVERY_REQUIRED",
            "NO_RECREATE",
        ),
        implementation_state="ready",
        blocker_code=None,
    ),
    ScenarioContract(
        scenario_id="K2",
        title="header_observed_body_lost",
        kill_point="after_on_run_created_before_create_response_return",
        expected_sdk_create_calls=1,
        expected_remote_runs=1,
        expected_invocation_count=1,
        restart_required=False,
        proof=(
            "ORPHAN_WITH_RUN_ID",
            "CONTENT_LOCATION_AUTHORITY",
            "EXACT_GET",
            "RECONCILED",
            "NO_RECREATE",
        ),
        implementation_state="ready",
        blocker_code=None,
    ),
    ScenarioContract(
        scenario_id="K3",
        title="bind_transaction_rollback",
        kill_point="before_reconciled_insert_inside_binding_transaction",
        expected_sdk_create_calls=1,
        expected_remote_runs=1,
        expected_invocation_count=1,
        restart_required=False,
        proof=("ROLLBACK", "ORPHAN", "FRESH_RECOVERY", "NO_RECREATE"),
        implementation_state="ready",
        blocker_code=None,
    ),
    ScenarioContract(
        scenario_id="K4",
        title="delayed_remote_visibility",
        kill_point=(
            "response_unknown_then_exact_observation_and_operator_authorized_bind"
        ),
        expected_sdk_create_calls=1,
        expected_remote_runs=1,
        expected_invocation_count=1,
        restart_required=False,
        proof=(
            "ORPHAN_WITHOUT_RUN_ID",
            "DELAYED_EXACT_OBSERVATION",
            "PENDING_OWNER_HANDOFF",
            "INDEPENDENT_OPERATOR_DISPOSITION",
            "EXACT_BIND_WITHOUT_RECREATE",
        ),
        implementation_state="ready",
        blocker_code=None,
    ),
    ScenarioContract(
        scenario_id="K5",
        title="api_and_postgres_restart",
        kill_point=(
            "after_reconciled_and_after_operator_disposed_ambiguous_orphan"
        ),
        expected_sdk_create_calls=2,
        expected_remote_runs=2,
        expected_invocation_count=2,
        restart_required=True,
        proof=(
            "DURABLE_REPLAY",
            "PENDING_OWNER_HANDOFF",
            "INDEPENDENT_OPERATOR_DISPOSITION",
            "RESTART_DURABILITY",
        ),
        implementation_state="ready",
        blocker_code=None,
    ),
    ScenarioContract(
        scenario_id="K6",
        title="concurrent_same_invocation",
        kill_point="two_process_barrier_before_begin_run_create",
        expected_sdk_create_calls=1,
        expected_remote_runs=1,
        expected_invocation_count=1,
        restart_required=False,
        proof=("ONE_DURABLE_WINNER", "ONE_SDK_CREATE", "ONE_REMOTE_RUN"),
        implementation_state="ready",
        blocker_code=None,
    ),
)


@dataclasses.dataclass(frozen=True)
class PhaseStep:
    step_id: str
    kind: str
    expected_exit_code: int | None = None
    expected_milestone: str | None = None
    service: str | None = None
    produces_final_receipt: bool = False


SCENARIO_STEPS: Mapping[str, tuple[PhaseStep, ...]] = {
    "K0": (
        PhaseStep("control_and_readback", "phase", 0, produces_final_receipt=True),
    ),
    "K1": (
        PhaseStep(
            "pending_victim",
            "phase",
            91,
            "pending_committed_before_dispatch",
        ),
        PhaseStep(
            "classify_pending_failed_before_dispatch",
            "phase",
            0,
            "pending_classified_failed_before_dispatch",
        ),
        PhaseStep(
            "dispatched_victim",
            "phase",
            94,
            "dispatched_committed_before_sdk_create",
        ),
        PhaseStep(
            "fresh_recovery_and_readback",
            "phase",
            0,
            produces_final_receipt=True,
        ),
    ),
    "K2": (
        PhaseStep(
            "header_victim",
            "phase",
            92,
            "orphan_with_run_id_committed_body_unread",
        ),
        PhaseStep("fresh_recovery_and_readback", "phase", 0, produces_final_receipt=True),
    ),
    "K3": (
        PhaseStep(
            "bind_rollback_victim",
            "phase",
            0,
            "binding_transaction_rolled_back",
        ),
        PhaseStep("fresh_recovery_and_readback", "phase", 0, produces_final_receipt=True),
    ),
    "K4": (
        PhaseStep(
            "response_loss_first_pass",
            "phase",
            93,
            "response_lost_orphan_without_run_id",
        ),
        PhaseStep(
            "fresh_exact_observation",
            "phase",
            0,
            "exact_observation_persisted_pending_owner",
        ),
        PhaseStep(
            "record_operator_disposition",
            "operator",
            0,
            "operator_disposition_recorded",
        ),
        PhaseStep(
            "fresh_authorized_bind_and_readback",
            "phase",
            0,
            produces_final_receipt=True,
        ),
    ),
    "K5": (
        PhaseStep(
            "seed_restart_states",
            "phase",
            0,
            "restart_states_seeded",
        ),
        PhaseStep(
            "pending_owner_handoff_readback",
            "phase",
            0,
            "pending_owner_handoff_observed",
        ),
        PhaseStep(
            "record_operator_disposition",
            "operator",
            0,
            "operator_disposition_recorded",
        ),
        PhaseStep("restart_api", "restart", service="langgraph-api"),
        PhaseStep(
            "readback_after_api_restart",
            "phase",
            0,
            "api_restart_readback_observed",
        ),
        PhaseStep("restart_postgres", "restart", service="langgraph-postgres"),
        PhaseStep(
            "final_readback_after_postgres_restart",
            "phase",
            0,
            produces_final_receipt=True,
        ),
    ),
    "K6": (
        PhaseStep(
            "concurrent_workers_and_readback",
            "phase",
            0,
            produces_final_receipt=True,
        ),
    ),
}


STEP_OBSERVATION_EXPECTATIONS: Mapping[tuple[str, str], tuple[int, int]] = {
    ("K1", "pending_victim"): (0, 0),
    ("K1", "classify_pending_failed_before_dispatch"): (0, 0),
    ("K1", "dispatched_victim"): (0, 0),
    ("K2", "header_victim"): (1, 1),
    ("K3", "bind_rollback_victim"): (1, 1),
    ("K4", "response_loss_first_pass"): (1, 1),
    ("K4", "fresh_exact_observation"): (1, 1),
    ("K4", "record_operator_disposition"): (1, 1),
    ("K5", "seed_restart_states"): (2, 2),
    ("K5", "pending_owner_handoff_readback"): (2, 2),
    ("K5", "record_operator_disposition"): (2, 2),
    ("K5", "readback_after_api_restart"): (2, 2),
}


EXECUTION_BOUNDARY = {
    "zero_model": True,
    "external_research_or_model_calls": False,
    "provider_model_calls": False,
    "langsmith_observability_egress": True,
    "trace_content_in_receipt": False,
}


OBSERVATION_SOURCES = {
    "sdk_create_attempts": "QUALIFICATION_INSTRUMENTED_OFFICIAL_SDK_BOUNDARY",
    "remote_committed_runs": "AGENT_SERVER_READBACK",
    "lifecycle_events": "FIN_POSTGRES_READBACK",
    "final_bindings": "FIN_POSTGRES_READBACK",
}

ALLOWED_REMOTE_RUN_STATUSES = frozenset(
    {"pending", "running", "error", "success", "timeout", "interrupted"}
)
FINAL_REMOTE_STATUS_RULES = {
    "K0": {"primary": frozenset({"success"})},
    "K2": {"primary": frozenset({"success", "error"})},
    "K3": {"primary": frozenset({"success", "error"})},
    "K4": {"primary": frozenset({"success", "error"})},
    "K5": {
        "reconciled_restart": frozenset({"success"}),
        "unresolved_orphan_restart": frozenset({"error"}),
    },
    "K6": {"shared_invocation": frozenset({"success"})},
}


SCENARIO_RULES: Mapping[str, Mapping[str, Any]] = {
    "K0": {
        "invocations": (
            (
                "primary",
                ("PENDING", "DISPATCHED", "ORPHAN", "ORPHAN", "RECONCILED"),
                "APPLIED",
                ("NOT_APPLICABLE", "NOT_APPLICABLE", None, False, True),
                1,
                1,
            ),
        ),
        "proof": {
            "callback_observed": True,
            "remote_catalog_distinct_run_count": 1,
        },
    },
    "K1": {
        "invocations": (
            (
                "pending_before_dispatch",
                ("PENDING",),
                "FAILED_BEFORE_DISPATCH",
                (
                    "NOT_APPLICABLE",
                    "NOT_APPLICABLE",
                    None,
                    False,
                    True,
                ),
                0,
                0,
            ),
            (
                "dispatched_before_sdk_create",
                ("PENDING", "DISPATCHED", "ORPHAN"),
                "AMBIGUOUS_AFTER_DISPATCH",
                (
                    "RECOVERY_REQUIRED",
                    "PENDING_OWNER_DECISION",
                    None,
                    True,
                    False,
                ),
                0,
                0,
            ),
        ),
        "proof": {
            "pending_victim_exit_code": 91,
            "pending_victim_milestone": "pending_committed_before_dispatch",
            "pending_supervisor_classification_observed": True,
            "dispatched_victim_exit_code": 94,
            "dispatched_victim_milestone": (
                "dispatched_committed_before_sdk_create"
            ),
            "dispatched_without_sdk_create_recovery_required": True,
            "sdk_create_attempt_count_for_both_invocations": 0,
            "remote_catalog_distinct_run_count": 0,
            "fresh_recovery_process": True,
            "second_create_attempted": False,
        },
    },
    "K2": {
        "invocations": (
            (
                "primary",
                ("PENDING", "DISPATCHED", "ORPHAN", "ORPHAN", "RECONCILED"),
                "APPLIED",
                (
                    "NOT_APPLICABLE",
                    "NOT_APPLICABLE",
                    None,
                    False,
                    True,
                ),
                1,
                1,
            ),
        ),
        "proof": {
            "victim_exit_code": 92,
            "victim_milestone": "orphan_with_run_id_committed_body_unread",
            "header_callback_committed_before_exit": True,
            "observation_authority": "DURABLE_CONTENT_LOCATION_RUN_ID",
            "recovery_lookup_kind": "EXACT_GET_BY_OBSERVED_RUN_ID",
            "observed_server_run_id_preserved": True,
            "reconciled_observation_digest_bound": True,
            "remote_catalog_distinct_run_count": 1,
            "fresh_recovery_process": True,
            "second_create_attempted": False,
        },
    },
    "K3": {
        "invocations": (
            (
                "primary",
                ("PENDING", "DISPATCHED", "ORPHAN", "ORPHAN", "RECONCILED"),
                "APPLIED",
                (
                    "NOT_APPLICABLE",
                    "NOT_APPLICABLE",
                    None,
                    False,
                    True,
                ),
                1,
                1,
            ),
        ),
        "proof": {
            "transaction_rollback_observed": True,
            "binding_count_after_failed_transaction": 0,
            "reconciled_rows_after_failed_transaction": 0,
            "fresh_recovery_process": True,
            "remote_catalog_distinct_run_count": 1,
            "second_create_attempted": False,
        },
    },
    "K4": {
        "invocations": (
            (
                "primary",
                (
                    "PENDING",
                    "DISPATCHED",
                    "ORPHAN",
                    "ORPHAN",
                    "RECONCILED",
                ),
                "AMBIGUOUS_AFTER_DISPATCH",
                (
                    "RECOVERY_REQUIRED",
                    "RECORDED",
                    "DO_NOT_RETRY",
                    True,
                    True,
                ),
                1,
                1,
            ),
        ),
        "proof": {
            "response_body_loss_observed": True,
            "create_callback_exposed": False,
            "first_pass_hidden_exact_scans": 2,
            "first_pass_fin_state": "ORPHAN_WITHOUT_RUN_ID",
            "fresh_exact_observation_process": True,
            "exact_observation_persisted_before_disposition": True,
            "pending_owner_handoff_observed_before_disposition": True,
            "operator_authority_process_distinct": True,
            "canonical_recovery_decision": "DO_NOT_RETRY",
            "recovery_disposition_exact_binding": True,
            "ambiguous_action_unchanged_after_disposition": True,
            "disposition_recorded_after_exact_observation": True,
            "reconciled_exact_observation_digest_match": True,
            "reconciled_server_status_match": True,
            "fresh_authorized_bind_process": True,
            "remote_catalog_distinct_run_count": 1,
            "second_create_attempted": False,
        },
    },
    "K5": {
        "invocations": (
            (
                "reconciled_restart",
                ("PENDING", "DISPATCHED", "ORPHAN", "ORPHAN", "RECONCILED"),
                "APPLIED",
                ("NOT_APPLICABLE", "NOT_APPLICABLE", None, False, True),
                1,
                1,
            ),
            (
                "unresolved_orphan_restart",
                ("PENDING", "DISPATCHED", "ORPHAN", "ORPHAN"),
                "AMBIGUOUS_AFTER_DISPATCH",
                (
                    "RECOVERY_REQUIRED",
                    "RECORDED",
                    "DO_NOT_RETRY",
                    True,
                    True,
                ),
                0,
                1,
            ),
        ),
        "proof": {
            "pending_owner_handoff_observed_before_disposition": True,
            "exact_observation_persisted_before_disposition": True,
            "operator_authority_process_distinct": True,
            "canonical_recovery_decision": "DO_NOT_RETRY",
            "recovery_disposition_exact_binding": True,
            "ambiguous_action_unchanged_after_disposition": True,
            "disposition_recorded_after_exact_observation": True,
            "api_restart_observed": True,
            "postgres_restart_observed": True,
            "reconciled_binding_persisted": True,
            "disposed_orphan_persisted": True,
            "disposition_persisted_after_api_restart": True,
            "disposition_persisted_after_postgres_restart": True,
            "reconciled_replay_create_attempts": 0,
            "orphan_replay_create_attempts": 0,
            "remote_catalog_distinct_run_count": 2,
        },
    },
    "K6": {
        "invocations": (
            (
                "shared_invocation",
                ("PENDING", "DISPATCHED", "ORPHAN", "ORPHAN", "RECONCILED"),
                "APPLIED",
                ("NOT_APPLICABLE", "NOT_APPLICABLE", None, False, True),
                1,
                1,
            ),
        ),
        "proof": {
            "worker_processes": 2,
            "barrier_participants": 2,
            "durable_winner_count": 1,
            "sdk_create_winner_count": 1,
            "remote_catalog_distinct_run_count": 1,
            "losing_worker_action": "RECONCILIATION_ONLY",
        },
    },
}


def scenario_contracts() -> tuple[ScenarioContract, ...]:
    """Return the immutable, bounded RC-S3-107 matrix."""

    return SCENARIOS


def incomplete_scenario_blockers() -> tuple[str, ...]:
    """Return typed blockers that prohibit a partial live qualification."""

    return tuple(
        scenario.blocker_code
        for scenario in SCENARIOS
        if scenario.implementation_state != "ready" and scenario.blocker_code
    )


def _run_readonly(
    command: Sequence[str],
    *,
    cwd: Path = ROOT,
    timeout: float = 30.0,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=None if env is None else dict(env),
    )


def _require_success(
    completed: subprocess.CompletedProcess[str], code: str
) -> str:
    if completed.returncode != 0:
        raise QualificationError(code)
    return completed.stdout.strip()


def _git(*args: str) -> str:
    return _require_success(
        _run_readonly(("git", *args)),
        "rc_s3_107_git_preflight_failed",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _catalog_literal(path: Path) -> str:
    if not path.is_file():
        raise QualificationError("rc_s3_107_catalog_file_missing", path.name)
    text = path.read_text(encoding="utf-8")
    if CATALOG_PLACEHOLDER in text:
        raise QualificationError("rc_s3_107_catalog_hash_unresolved", path.name)
    assignment = CATALOG_ASSIGNMENT_RE.search(text)
    if assignment is None:
        raise QualificationError("rc_s3_107_catalog_hash_missing", path.name)
    value = assignment.group("value").lower()
    if re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise QualificationError("rc_s3_107_catalog_hash_invalid", path.name)
    return value


def _assert_catalog_ready() -> str:
    literals = tuple(_catalog_literal(path) for path in CATALOG_FILES)
    if len(set(literals)) != 1:
        raise QualificationError("rc_s3_107_catalog_hash_mismatch")
    return literals[0]


def _assert_repo_state() -> str:
    branch = _git("branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise QualificationError("rc_s3_107_wrong_branch", branch or "DETACHED")
    if _git("status", "--porcelain=v1"):
        raise QualificationError("rc_s3_107_dirty_worktree")
    local = _git("rev-parse", "HEAD")
    upstream = _git("rev-parse", "@{u}")
    if local != upstream:
        raise QualificationError("rc_s3_107_upstream_mismatch")
    return local


def _assert_required_files() -> None:
    required = (
        BASE_COMPOSE,
        OVERLAY_COMPOSE,
        ROOT / "src" / "sec_agent" / "agent_runtime" / "dell_agent_server_client.py",
        ROOT / "src" / "sec_agent" / "agent_runtime" / "dell_agent_server_identity.py",
        ROOT / "src" / "sec_agent" / "agent_runtime" / "dell_agent_server_entry.py",
        Path(__file__).with_name("live_killpoint_phase.py"),
    )
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise QualificationError(
            "rc_s3_107_required_file_missing", ",".join(sorted(missing))
        )


def _assert_zero_model_surface() -> None:
    forbidden = (
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "MODEL_PROVIDER",
    )
    text = OVERLAY_COMPOSE.read_text(encoding="utf-8")
    found = [name for name in forbidden if name in text]
    if found:
        raise QualificationError(
            "rc_s3_107_model_surface_forbidden", ",".join(sorted(found))
        )
    base = BASE_COMPOSE.read_text(encoding="utf-8")
    required_observability = (
        "LANGSMITH_API_KEY:",
        'LANGSMITH_TRACING: "true"',
        'LANGSMITH_HIDE_INPUTS: "true"',
        'LANGSMITH_HIDE_OUTPUTS: "true"',
    )
    if any(fragment not in base for fragment in required_observability):
        raise QualificationError("rc_s3_107_langsmith_boundary_invalid")


def _assert_phase_implementation_complete() -> None:
    blockers = incomplete_scenario_blockers()
    if blockers:
        raise QualificationError(
            "rc_s3_107_live_matrix_incomplete", ",".join(blockers)
        )


def static_preflight() -> Mapping[str, str]:
    """Run checks which cannot mutate Docker or create an attempt directory."""

    _assert_required_files()
    _assert_zero_model_surface()
    commit = _assert_repo_state()
    catalog_hash = _assert_catalog_ready()
    _assert_phase_implementation_complete()
    return {"commit": commit, "catalog_sha256": catalog_hash}


def _assert_port_free(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise QualificationError("rc_s3_107_api_port_not_free", str(port)) from exc


def _assert_fresh_compose_identity(project: str) -> None:
    ps = _require_success(
        _run_readonly(
            (
                "docker",
                "ps",
                "-a",
                "--filter",
                f"label=com.docker.compose.project={project}",
                "--format",
                "{{.ID}}",
            )
        ),
        "rc_s3_107_docker_unavailable",
    )
    if ps:
        raise QualificationError("rc_s3_107_compose_project_not_fresh", project)
    volume = f"{project}_langgraph-data"
    inspected = _run_readonly(("docker", "volume", "inspect", volume))
    if inspected.returncode == 0:
        raise QualificationError("rc_s3_107_volume_not_fresh", volume)
    if inspected.returncode not in (1,):
        raise QualificationError("rc_s3_107_volume_preflight_failed", volume)


def runtime_preflight(project: str, port: int) -> None:
    """Perform read-only Docker and port checks after static preflight passes."""

    _require_success(
        _run_readonly(("docker", "version", "--format", "{{.Server.Version}}")),
        "rc_s3_107_docker_unavailable",
    )
    _assert_port_free(port)
    _assert_fresh_compose_identity(project)


def _attempt_id(now: dt.datetime | None = None) -> str:
    stamp = now or dt.datetime.now(dt.timezone.utc)
    return stamp.strftime("rc-s3-107-a1-%Y%m%dT%H%M%SZ").lower()


def _project_name(attempt_id: str) -> str:
    suffix = attempt_id.removeprefix("rc-s3-107-a1-").replace("t", "-").replace("z", "")
    return f"{PROJECT_PREFIX}-{suffix}".lower()


def _scenario_identity_manifest(attempt_id: str) -> dict[str, list[dict[str, str]]]:
    identities: dict[str, list[dict[str, str]]] = {}
    for scenario_id, rule in SCENARIO_RULES.items():
        rows: list[dict[str, str]] = []
        for invocation_rule in rule["invocations"]:
            role = invocation_rule[0]
            invocation_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"fin.rc_s3_107:{attempt_id}:{scenario_id}:{role}",
                )
            )
            rows.append({"role": role, "invocation_id": invocation_id})
        identities[scenario_id] = rows
    return identities


def _scenario_runtime_cases(
    attempt_id: str,
    identities: Mapping[str, Sequence[Mapping[str, str]]],
) -> dict[str, list[dict[str, Any]]]:
    """Build canonical product inputs for the production client executors."""

    try:
        from sec_agent.agent_runtime.dell_agent_server_data_composition import (
            DELL_APPROVED_DATA_SNAPSHOT_ID,
            DELL_APPROVED_RESEARCH_AS_OF,
        )
        from sec_agent.agent_runtime.dell_owner_data_gate import (
            DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST,
        )
        from sec_agent.agent_runtime.dell_reference_vertical_contracts import (
            canonical_sha256,
        )
        from sec_agent.agent_runtime.dell_zero_model_graph_qualification import (
            ZERO_MODEL_EXECUTION_PROFILE,
        )
        from sec_agent.canonical_runtime.contracts_v1_2 import (
            canonical_json_sha256,
            create_agent_session_v1_2,
            create_research_run,
            create_run_invocation,
        )
        from sec_agent.research_foundation.contracts import (
            load_dell_reference_vertical_foundation,
        )
    except Exception as exc:
        raise QualificationError("rc_s3_107_runtime_contract_import_failed") from exc

    try:
        foundation = load_dell_reference_vertical_foundation(FOUNDATION_PATH)
        foundation_digest = canonical_sha256(foundation)
        as_of = dt.date.fromisoformat(DELL_APPROVED_RESEARCH_AS_OF[:10])
    except Exception as exc:
        raise QualificationError("rc_s3_107_runtime_foundation_invalid") from exc
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    runtime_cases: dict[str, list[dict[str, Any]]] = {}
    for scenario_id, rows in identities.items():
        cases: list[dict[str, Any]] = []
        for index, identity in enumerate(rows):
            role = identity["role"]
            invocation_id = identity["invocation_id"]
            identity_token = uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"fin.rc_s3_107:case:{attempt_id}:{scenario_id}:{role}",
            ).hex
            session_id = f"SESSION::DELL::RC-S3-107::{scenario_id}::{identity_token}"
            fin_thread_id = f"THREAD::DELL::RC-S3-107::{scenario_id}::{identity_token}"
            research_run_id = f"RUN::DELL::RC-S3-107::{scenario_id}::{identity_token}"
            plan = {
                "case": "DELL_AI_INFRA_REFERENCE_VERTICAL",
                "profile": ZERO_MODEL_EXECUTION_PROFILE,
                "qualification": "RC-S3-107",
                "scenario_id": scenario_id,
                "role": role,
            }
            plan_digest = canonical_json_sha256(plan)
            session = create_agent_session_v1_2(
                session_id=session_id,
                thread_id=fin_thread_id,
                case_id=foundation.case_identity.case_id,
                case_version="FIN_0_1_3",
                as_of_date=as_of,
                objective_ref=(
                    f"objective://dell/agent-server-rc-s3-107/{scenario_id}/{role}"
                ),
                objective_digest=canonical_json_sha256(
                    {
                        "question": foundation.case_identity.top_level_question_zh,
                        "scenario_id": scenario_id,
                        "role": role,
                    }
                ),
                data_snapshot_ref=f"snapshot://dell/{DELL_APPROVED_DATA_SNAPSHOT_ID}",
                data_snapshot_digest=DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST,
                runtime_policy_ref="policy://dell/zero-model-control-plane-v1",
                runtime_policy_digest=canonical_json_sha256(
                    {
                        "execution_profile": ZERO_MODEL_EXECUTION_PROFILE,
                        "model_calls": 0,
                        "external_research_or_model_calls": 0,
                        "langsmith_observability_egress": True,
                    }
                ),
                authority_refs=("authority://owner/data-gate/2026-09-03",),
                active_plan_ref=(
                    f"plan://dell/agent-server-rc-s3-107/{scenario_id}/{role}/v1"
                ),
                active_plan_digest=plan_digest,
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            research_run = create_research_run(
                run_id=research_run_id,
                session_id=session.session_id,
                parent_run_id=None,
                origin_kind="INITIAL",
                legacy_paid_full_chain_execution_label=None,
                status="RUNNING",
                base_plan_ref=session.active_plan_ref,
                base_plan_digest=session.active_plan_digest,
                current_plan_ref=session.active_plan_ref,
                current_plan_digest=session.active_plan_digest,
                last_session_sequence=0,
                created_at=now,
                terminal_at=None,
            )
            invocation = create_run_invocation(
                invocation_id=invocation_id,
                session_id=session.session_id,
                run_id=research_run.run_id,
                ordinal=1,
                invocation_kind="START",
                status="RUNNING",
                trigger_ref=(
                    f"qualification://dell/agent-server-rc-s3-107/"
                    f"{attempt_id}/{scenario_id}/{role}"
                ),
                lease_ref=(
                    f"lease://dell/agent-server-rc-s3-107/"
                    f"{scenario_id}/{identity_token}/{index + 1}"
                ),
                started_at=now + dt.timedelta(seconds=index + 1),
                finished_at=None,
            )
            cases.append(
                {
                    "role": role,
                    "agent_session": session.model_dump(mode="json"),
                    "research_run": research_run.model_dump(mode="json"),
                    "run_invocation": invocation.model_dump(mode="json"),
                    "graph_input": {
                        "run_id": research_run.run_id,
                        "case_id": foundation.case_identity.case_id,
                        "research_question": (
                            foundation.case_identity.top_level_question_zh
                        ),
                        "research_as_of": DELL_APPROVED_RESEARCH_AS_OF,
                        "snapshot_id": DELL_APPROVED_DATA_SNAPSHOT_ID,
                        "foundation_digest": foundation_digest,
                    },
                }
            )
        runtime_cases[scenario_id] = cases
    return runtime_cases


def _manifest(
    *,
    attempt_id: str,
    project: str,
    port: int,
    commit: str,
    catalog_hash: str,
) -> dict[str, Any]:
    scenario_identities = _scenario_identity_manifest(attempt_id)
    return {
        "schema_version": "fin.rc_s3_107.qualification_manifest.v1",
        "attempt_id": attempt_id,
        "project": project,
        "api_port": port,
        "commit": commit,
        "catalog_sha256": catalog_hash,
        "claim_boundary": {
            "local": "at_most_one_sdk_create_attempt_per_durable_invocation",
            "remote": "one_observed_committed_run_in_tested_single_host_topology",
            "excluded": "provider_or_network_exactly_once",
        },
        "constraints": {
            **EXECUTION_BOUNDARY,
            "automatic_second_attempt": False,
            "cleanup_on_failure": False,
        },
        "scenario_identities": scenario_identities,
        "runtime_cases": _scenario_runtime_cases(attempt_id, scenario_identities),
        "scenarios": [dataclasses.asdict(item) for item in SCENARIOS],
    }


def _validate_sanitized(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower()
            if any(forbidden in normalized for forbidden in FORBIDDEN_RECEIPT_KEYS):
                raise QualificationError(
                    "rc_s3_107_receipt_forbidden_key", f"{path}.{key}"
                )
            _validate_sanitized(nested, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _validate_sanitized(nested, f"{path}[{index}]")
        return
    if isinstance(value, str):
        if SECRET_VALUE_RE.search(value):
            raise QualificationError("rc_s3_107_receipt_secret_like_value", path)
        if HOST_PATH_RE.search(value):
            raise QualificationError("rc_s3_107_receipt_host_path", path)


def _write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    _validate_sanitized(payload)
    path.parent.mkdir(parents=True, exist_ok=False)
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)


def _write_json_in_existing_attempt(path: Path, payload: Mapping[str, Any]) -> None:
    _validate_sanitized(payload)
    if not path.parent.is_dir():
        raise QualificationError("rc_s3_107_attempt_directory_missing")
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)


def _compose_prefix(project: str) -> tuple[str, ...]:
    return (
        "docker",
        "compose",
        "--project-name",
        project,
        "--file",
        str(BASE_COMPOSE),
        "--file",
        str(OVERLAY_COMPOSE),
    )


def _expect_mapping(value: Any, *, code: str, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise QualificationError(code, path)
    if any(not isinstance(key, str) for key in value):
        raise QualificationError(code, path)
    return value


def _expect_list(value: Any, *, code: str, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise QualificationError(code, path)
    return value


def _expect_exact_keys(
    value: Mapping[str, Any], expected: set[str], *, code: str, path: str
) -> None:
    if set(value) != expected:
        raise QualificationError(code, path)


def _expect_exact(value: Any, expected: Any, *, code: str, path: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise QualificationError(code, path)


def _scenario_contract(scenario_id: str) -> ScenarioContract:
    for scenario in SCENARIOS:
        if scenario.scenario_id == scenario_id:
            return scenario
    raise QualificationError("rc_s3_107_receipt_scenario_unknown", scenario_id)


def _validate_execution_boundary(value: Any, *, path: str) -> None:
    boundary = _expect_mapping(
        value,
        code="rc_s3_107_receipt_execution_boundary_invalid",
        path=path,
    )
    _expect_exact_keys(
        boundary,
        set(EXECUTION_BOUNDARY),
        code="rc_s3_107_receipt_execution_boundary_unknown_or_missing_field",
        path=path,
    )
    for key, expected in EXECUTION_BOUNDARY.items():
        _expect_exact(
            boundary[key],
            expected,
            code="rc_s3_107_receipt_execution_boundary_mismatch",
            path=f"{path}.{key}",
        )


def _expected_identity_rows(
    manifest: Mapping[str, Any], scenario_id: str
) -> list[Mapping[str, Any]]:
    identities = _expect_mapping(
        manifest.get("scenario_identities"),
        code="rc_s3_107_manifest_scenario_identities_invalid",
        path="$.scenario_identities",
    )
    if set(identities) != set(SCENARIO_STEPS):
        raise QualificationError("rc_s3_107_manifest_scenario_identities_incomplete")
    rows = _expect_list(
        identities.get(scenario_id),
        code="rc_s3_107_manifest_scenario_identity_invalid",
        path=f"$.scenario_identities.{scenario_id}",
    )
    normalized: list[Mapping[str, Any]] = []
    for index, raw in enumerate(rows):
        row = _expect_mapping(
            raw,
            code="rc_s3_107_manifest_scenario_identity_invalid",
            path=f"$.scenario_identities.{scenario_id}[{index}]",
        )
        _expect_exact_keys(
            row,
            {"role", "invocation_id"},
            code="rc_s3_107_manifest_scenario_identity_invalid",
            path=f"$.scenario_identities.{scenario_id}[{index}]",
        )
        if not isinstance(row["role"], str) or not isinstance(
            row["invocation_id"], str
        ):
            raise QualificationError("rc_s3_107_manifest_scenario_identity_invalid")
        normalized.append(row)
    return normalized


def _validate_recovery(
    value: Any,
    expected: tuple[str, str, str | None, bool, bool],
    *,
    path: str,
) -> None:
    recovery = _expect_mapping(
        value,
        code="rc_s3_107_receipt_recovery_invalid",
        path=path,
    )
    _expect_exact_keys(
        recovery,
        {
            "status",
            "recovery_disposition_status",
            "canonical_recovery_decision",
            "owner_visible",
            "resolved",
            "automatic_second_create_attempted",
        },
        code="rc_s3_107_receipt_recovery_unknown_or_missing_field",
        path=path,
    )
    (
        expected_status,
        expected_disposition_status,
        expected_decision,
        expected_owner,
        expected_resolved,
    ) = expected
    expected_values = {
        "status": expected_status,
        "recovery_disposition_status": expected_disposition_status,
        "canonical_recovery_decision": expected_decision,
        "owner_visible": expected_owner,
        "resolved": expected_resolved,
        "automatic_second_create_attempted": False,
    }
    for key, expected_value in expected_values.items():
        _expect_exact(
            recovery[key],
            expected_value,
            code="rc_s3_107_receipt_recovery_semantics_mismatch",
            path=f"{path}.{key}",
        )
    if recovery["status"] == "NOT_APPLICABLE":
        if (
            recovery["recovery_disposition_status"] != "NOT_APPLICABLE"
            or recovery["canonical_recovery_decision"] is not None
            or recovery["owner_visible"] is not False
            or recovery["resolved"] is not True
        ):
            raise QualificationError(
                "rc_s3_107_receipt_impossible_recovery_disposition", path
            )
    elif recovery["status"] == "RECOVERY_REQUIRED":
        if (
            recovery["recovery_disposition_status"] == "NOT_APPLICABLE"
            or recovery["owner_visible"] is not True
        ):
            raise QualificationError(
                "rc_s3_107_receipt_impossible_recovery_disposition", path
            )
        if recovery["recovery_disposition_status"] == "PENDING_OWNER_DECISION":
            if (
                recovery["canonical_recovery_decision"] is not None
                or recovery["resolved"] is not False
            ):
                raise QualificationError(
                    "rc_s3_107_receipt_impossible_recovery_disposition", path
                )
        elif recovery["recovery_disposition_status"] == "RECORDED":
            if recovery["canonical_recovery_decision"] not in {
                "DO_NOT_RETRY",
                "RETRY_AS_NEW_ACTION",
                "RESUME_WITHOUT_RETRY",
                "ABANDON_RUN",
                "ESCALATE_TO_HUMAN",
            }:
                raise QualificationError(
                    "rc_s3_107_receipt_impossible_recovery_disposition", path
                )
        else:
            raise QualificationError(
                "rc_s3_107_receipt_recovery_disposition_status_unknown", path
            )
    else:
        raise QualificationError("rc_s3_107_receipt_recovery_status_unknown", path)


def validate_scenario_receipt(
    value: Any,
    *,
    manifest: Mapping[str, Any],
    expected_scenario_id: str,
) -> dict[str, Any]:
    """Strictly validate one final K0-K6 receipt and its semantics."""

    receipt = _expect_mapping(
        value,
        code="rc_s3_107_receipt_not_object",
        path="$",
    )
    _expect_exact_keys(
        receipt,
        {
            "schema_version",
            "attempt_id",
            "project",
            "scenario_id",
            "status",
            "execution_boundary",
            "identity",
            "counts",
            "observation_sources",
            "invocations",
            "proof",
        },
        code="rc_s3_107_receipt_unknown_or_missing_field",
        path="$",
    )
    exact_root = {
        "schema_version": "fin.rc_s3_107.scenario_receipt.v1",
        "attempt_id": manifest.get("attempt_id"),
        "project": manifest.get("project"),
        "scenario_id": expected_scenario_id,
        "status": "PASS",
    }
    for key, expected in exact_root.items():
        _expect_exact(
            receipt[key],
            expected,
            code="rc_s3_107_receipt_identity_or_schema_mismatch",
            path=f"$.{key}",
        )
    _validate_execution_boundary(receipt["execution_boundary"], path="$.execution_boundary")

    contract = _scenario_contract(expected_scenario_id)
    rule = SCENARIO_RULES[expected_scenario_id]
    expected_identities = _expected_identity_rows(manifest, expected_scenario_id)
    expected_invocation_ids = [row["invocation_id"] for row in expected_identities]
    expected_roles = [row["role"] for row in expected_identities]
    if len(set(expected_invocation_ids)) != len(expected_invocation_ids):
        raise QualificationError("rc_s3_107_manifest_invocation_identity_collision")

    identity = _expect_mapping(
        receipt["identity"],
        code="rc_s3_107_receipt_identity_invalid",
        path="$.identity",
    )
    _expect_exact_keys(
        identity,
        {
            "attempt_id",
            "project",
            "scenario_id",
            "invocation_ids",
            "cross_scenario_identity_collision_count",
        },
        code="rc_s3_107_receipt_identity_unknown_or_missing_field",
        path="$.identity",
    )
    expected_identity_values = {
        "attempt_id": manifest.get("attempt_id"),
        "project": manifest.get("project"),
        "scenario_id": expected_scenario_id,
        "invocation_ids": expected_invocation_ids,
        "cross_scenario_identity_collision_count": 0,
    }
    for key, expected in expected_identity_values.items():
        _expect_exact(
            identity[key],
            expected,
            code="rc_s3_107_receipt_identity_isolation_failed",
            path=f"$.identity.{key}",
        )

    invocation_rules = rule["invocations"]
    invocations = _expect_list(
        receipt["invocations"],
        code="rc_s3_107_receipt_invocations_invalid",
        path="$.invocations",
    )
    if len(invocations) != contract.expected_invocation_count:
        raise QualificationError("rc_s3_107_receipt_invocation_count_mismatch")
    if len(invocation_rules) != len(expected_identities):
        raise QualificationError("rc_s3_107_internal_receipt_rule_invalid")

    expected_event_rows = 0
    expected_final_bindings = 0
    for index, (raw, invocation_rule, expected_identity) in enumerate(
        zip(invocations, invocation_rules, expected_identities)
    ):
        invocation = _expect_mapping(
            raw,
            code="rc_s3_107_receipt_invocation_invalid",
            path=f"$.invocations[{index}]",
        )
        _expect_exact_keys(
            invocation,
            {
                "invocation_id",
                "role",
                "lifecycle",
                "canonical_action_outcome",
                "recovery",
                "final_binding_count",
                "sdk_create_attempts",
                "remote_run_status",
                "remote_run_id",
            },
            code="rc_s3_107_receipt_invocation_unknown_or_missing_field",
            path=f"$.invocations[{index}]",
        )
        (
            role,
            lifecycle,
            action_outcome,
            recovery,
            final_binding_count,
            sdk_create_attempts,
        ) = invocation_rule
        if role != expected_roles[index]:
            raise QualificationError("rc_s3_107_internal_receipt_role_invalid")
        exact_invocation = {
            "invocation_id": expected_identity["invocation_id"],
            "role": role,
            "lifecycle": list(lifecycle),
            "canonical_action_outcome": action_outcome,
            "final_binding_count": final_binding_count,
            "sdk_create_attempts": sdk_create_attempts,
        }
        for key, expected in exact_invocation.items():
            _expect_exact(
                invocation[key],
                expected,
                code="rc_s3_107_receipt_invocation_semantics_mismatch",
                path=f"$.invocations[{index}].{key}",
            )
        remote_status = invocation["remote_run_status"]
        remote_run_id = invocation["remote_run_id"]
        if sdk_create_attempts == 0:
            _expect_exact(
                remote_status,
                None,
                code="rc_s3_107_receipt_remote_status_mismatch",
                path=f"$.invocations[{index}].remote_run_status",
            )
            _expect_exact(
                remote_run_id,
                None,
                code="rc_s3_107_receipt_remote_run_id_mismatch",
                path=f"$.invocations[{index}].remote_run_id",
            )
        elif remote_status not in ALLOWED_REMOTE_RUN_STATUSES:
            raise QualificationError(
                "rc_s3_107_receipt_remote_status_invalid",
                f"$.invocations[{index}].remote_run_status",
            )
        else:
            try:
                parsed_remote_run_id = uuid.UUID(remote_run_id)
            except (TypeError, ValueError, AttributeError):
                raise QualificationError(
                    "rc_s3_107_receipt_remote_run_id_invalid",
                    f"$.invocations[{index}].remote_run_id",
                ) from None
            if str(parsed_remote_run_id) != remote_run_id.lower():
                raise QualificationError(
                    "rc_s3_107_receipt_remote_run_id_invalid",
                    f"$.invocations[{index}].remote_run_id",
                )
        allowed_final_statuses = FINAL_REMOTE_STATUS_RULES.get(
            expected_scenario_id, {}
        ).get(role)
        if allowed_final_statuses is not None and remote_status not in allowed_final_statuses:
            raise QualificationError(
                "rc_s3_107_receipt_remote_terminal_status_mismatch",
                f"$.invocations[{index}].remote_run_status",
            )
        _validate_recovery(
            invocation["recovery"],
            recovery,
            path=f"$.invocations[{index}].recovery",
        )
        expected_event_rows += len(lifecycle)
        expected_final_bindings += final_binding_count

    counts = _expect_mapping(
        receipt["counts"],
        code="rc_s3_107_receipt_counts_invalid",
        path="$.counts",
    )
    expected_counts = {
        "sdk_create_attempts": contract.expected_sdk_create_calls,
        "remote_committed_runs": contract.expected_remote_runs,
        "durable_invocations": contract.expected_invocation_count,
        "lifecycle_event_rows": expected_event_rows,
        "final_bindings": expected_final_bindings,
    }
    _expect_exact_keys(
        counts,
        set(expected_counts),
        code="rc_s3_107_receipt_counts_unknown_or_missing_field",
        path="$.counts",
    )
    for key, expected in expected_counts.items():
        _expect_exact(
            counts[key],
            expected,
            code="rc_s3_107_receipt_count_mismatch",
            path=f"$.counts.{key}",
        )

    sources = _expect_mapping(
        receipt["observation_sources"],
        code="rc_s3_107_receipt_observation_sources_invalid",
        path="$.observation_sources",
    )
    _expect_exact_keys(
        sources,
        set(OBSERVATION_SOURCES),
        code="rc_s3_107_receipt_observation_sources_unknown_or_missing_field",
        path="$.observation_sources",
    )
    for key, expected in OBSERVATION_SOURCES.items():
        _expect_exact(
            sources[key],
            expected,
            code="rc_s3_107_receipt_observation_source_mismatch",
            path=f"$.observation_sources.{key}",
        )

    proof = _expect_mapping(
        receipt["proof"],
        code="rc_s3_107_receipt_proof_invalid",
        path="$.proof",
    )
    expected_proof = rule["proof"]
    _expect_exact_keys(
        proof,
        set(expected_proof),
        code="rc_s3_107_receipt_proof_unknown_or_missing_field",
        path="$.proof",
    )
    for key, expected in expected_proof.items():
        _expect_exact(
            proof[key],
            expected,
            code="rc_s3_107_receipt_proof_mismatch",
            path=f"$.proof.{key}",
        )

    _validate_sanitized(receipt)
    return dict(receipt)


def validate_complete_receipts(
    value: Any, *, manifest: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    receipts = _expect_mapping(
        value,
        code="rc_s3_107_receipt_set_invalid",
        path="$",
    )
    if set(receipts) != set(SCENARIO_STEPS):
        raise QualificationError("rc_s3_107_receipt_set_incomplete_or_unknown")
    validated: dict[str, dict[str, Any]] = {}
    all_invocation_ids: list[str] = []
    for scenario_id in SCENARIO_STEPS:
        final = validate_scenario_receipt(
            receipts[scenario_id],
            manifest=manifest,
            expected_scenario_id=scenario_id,
        )
        validated[scenario_id] = final
        all_invocation_ids.extend(final["identity"]["invocation_ids"])
    if len(set(all_invocation_ids)) != len(all_invocation_ids):
        raise QualificationError("rc_s3_107_cross_scenario_identity_collision")
    return validated


def _parse_jsonl(stdout: str, scenario_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise QualificationError(
                "rc_s3_107_phase_non_json_output", f"{scenario_id}:{line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise QualificationError(
                "rc_s3_107_phase_non_object_output", f"{scenario_id}:{line_number}"
            )
        _validate_sanitized(value)
        records.append(value)
    if not records:
        raise QualificationError("rc_s3_107_phase_empty_output", scenario_id)
    return records


def _validate_step_observation(
    value: Any,
    *,
    manifest: Mapping[str, Any],
    scenario_id: str,
    step: PhaseStep,
) -> dict[str, Any]:
    observation = _expect_mapping(
        value,
        code="rc_s3_107_step_observation_invalid",
        path="$",
    )
    _expect_exact_keys(
        observation,
        {
            "schema_version",
            "attempt_id",
            "project",
            "scenario_id",
            "step_id",
            "milestone",
            "sdk_create_calls",
            "remote_run_count",
        },
        code="rc_s3_107_step_observation_unknown_or_missing_field",
        path="$",
    )
    expected_counts = STEP_OBSERVATION_EXPECTATIONS.get((scenario_id, step.step_id))
    if step.expected_milestone is None or expected_counts is None:
        raise QualificationError("rc_s3_107_step_observation_not_allowed", step.step_id)
    expected = {
        "schema_version": "fin.rc_s3_107.killpoint_observation.v1",
        "attempt_id": manifest.get("attempt_id"),
        "project": manifest.get("project"),
        "scenario_id": scenario_id,
        "step_id": step.step_id,
        "milestone": step.expected_milestone,
        "sdk_create_calls": expected_counts[0],
        "remote_run_count": expected_counts[1],
    }
    for key, expected_value in expected.items():
        _expect_exact(
            observation[key],
            expected_value,
            code="rc_s3_107_step_observation_semantics_mismatch",
            path=f"$.{key}",
        )
    _validate_sanitized(observation)
    return dict(observation)


def _validate_phase_blocker(
    value: Any,
    *,
    manifest: Mapping[str, Any],
    scenario_id: str,
    step: PhaseStep,
) -> dict[str, Any]:
    blocker = _expect_mapping(
        value,
        code="rc_s3_107_phase_blocker_invalid",
        path="$",
    )
    _expect_exact_keys(
        blocker,
        {
            "schema_version",
            "attempt_id",
            "project",
            "scenario_id",
            "step_id",
            "status",
            "code",
        },
        code="rc_s3_107_phase_blocker_unknown_or_missing_field",
        path="$",
    )
    exact = {
        "schema_version": "fin.rc_s3_107.phase_blocker.v1",
        "attempt_id": manifest.get("attempt_id"),
        "project": manifest.get("project"),
        "scenario_id": scenario_id,
        "step_id": step.step_id,
        "status": "BLOCKED",
    }
    for key, expected in exact.items():
        _expect_exact(
            blocker[key],
            expected,
            code="rc_s3_107_phase_blocker_identity_mismatch",
            path=f"$.{key}",
        )
    if not isinstance(blocker["code"], str) or not blocker["code"].startswith(
        "rc_s3_107_"
    ):
        raise QualificationError("rc_s3_107_phase_blocker_code_invalid")
    _validate_sanitized(blocker)
    return dict(blocker)


def _validate_operator_observation(
    value: Any,
    *,
    manifest: Mapping[str, Any],
    scenario_id: str,
    step: PhaseStep,
) -> dict[str, Any]:
    observation = _expect_mapping(
        value,
        code="rc_s3_107_operator_observation_invalid",
        path="$",
    )
    _expect_exact_keys(
        observation,
        {
            "schema_version",
            "attempt_id",
            "project",
            "scenario_id",
            "step_id",
            "milestone",
            "source_invocation_id",
            "canonical_recovery_decision",
            "exact_ambiguous_action_binding",
        },
        code="rc_s3_107_operator_observation_unknown_or_missing_field",
        path="$",
    )
    role_by_scenario = {
        "K4": "primary",
        "K5": "unresolved_orphan_restart",
    }
    role = role_by_scenario.get(scenario_id)
    if role is None or step.expected_milestone is None:
        raise QualificationError(
            "rc_s3_107_operator_observation_not_allowed", step.step_id
        )
    identity_rows = _expected_identity_rows(manifest, scenario_id)
    invocation_ids = [
        row["invocation_id"] for row in identity_rows if row["role"] == role
    ]
    if len(invocation_ids) != 1:
        raise QualificationError("rc_s3_107_operator_identity_invalid")
    expected = {
        "schema_version": "fin.rc_s3_107.operator_observation.v1",
        "attempt_id": manifest.get("attempt_id"),
        "project": manifest.get("project"),
        "scenario_id": scenario_id,
        "step_id": step.step_id,
        "milestone": step.expected_milestone,
        "source_invocation_id": invocation_ids[0],
        "canonical_recovery_decision": "DO_NOT_RETRY",
        "exact_ambiguous_action_binding": True,
    }
    for key, expected_value in expected.items():
        _expect_exact(
            observation[key],
            expected_value,
            code="rc_s3_107_operator_observation_semantics_mismatch",
            path=f"$.{key}",
        )
    _validate_sanitized(observation)
    return dict(observation)


def _compose_env(port: int) -> dict[str, str]:
    environment = dict(os.environ)
    environment["FINSIGHT_AGENT_SERVER_HOST_PORT"] = str(port)
    return environment


def _run_phase_step(
    *,
    project: str,
    port: int,
    scenario_id: str,
    step: PhaseStep,
    manifest: Mapping[str, Any],
    timeout: float = 120.0,
) -> dict[str, Any]:
    if step.kind != "phase" or step.expected_exit_code is None:
        raise QualificationError("rc_s3_107_phase_step_contract_invalid", step.step_id)
    command = (
        *_compose_prefix(project),
        "exec",
        "-T",
        "langgraph-api",
        "python",
        PHASE_SCRIPT_IN_CONTAINER,
        "--scenario",
        scenario_id,
        "--step",
        step.step_id,
    )
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        input=json.dumps(manifest, ensure_ascii=True),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=_compose_env(port),
    )
    records = _parse_jsonl(completed.stdout, scenario_id)
    if completed.returncode == 78:
        if len(records) != 1:
            raise QualificationError("rc_s3_107_phase_blocker_stream_invalid")
        blocker = _validate_phase_blocker(
            records[0],
            manifest=manifest,
            scenario_id=scenario_id,
            step=step,
        )
        raise QualificationError(str(blocker["code"]), scenario_id)
    if completed.returncode != step.expected_exit_code:
        raise QualificationError(
            "rc_s3_107_phase_exit_code_mismatch",
            f"{scenario_id}:{step.step_id}",
        )
    if step.produces_final_receipt:
        if len(records) != 1:
            raise QualificationError("rc_s3_107_final_receipt_stream_invalid")
        return validate_scenario_receipt(
            records[0],
            manifest=manifest,
            expected_scenario_id=scenario_id,
        )
    if len(records) != 1:
        raise QualificationError("rc_s3_107_step_observation_stream_invalid")
    return _validate_step_observation(
        records[0],
        manifest=manifest,
        scenario_id=scenario_id,
        step=step,
    )


def _run_operator_step(
    *,
    project: str,
    port: int,
    scenario_id: str,
    step: PhaseStep,
    manifest: Mapping[str, Any],
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Run the one-shot recovery authority outside the API process/credential."""

    if step.kind != "operator" or step.expected_exit_code is None:
        raise QualificationError(
            "rc_s3_107_operator_step_contract_invalid", step.step_id
        )
    command = (
        *_compose_prefix(project),
        "run",
        "--rm",
        "-T",
        "--no-deps",
        "fin-recovery-operator",
        "python",
        PHASE_SCRIPT_IN_CONTAINER,
        "--scenario",
        scenario_id,
        "--step",
        step.step_id,
    )
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        input=json.dumps(manifest, ensure_ascii=True),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=_compose_env(port),
    )
    records = _parse_jsonl(completed.stdout, scenario_id)
    if completed.returncode == 78:
        if len(records) != 1:
            raise QualificationError("rc_s3_107_phase_blocker_stream_invalid")
        blocker = _validate_phase_blocker(
            records[0],
            manifest=manifest,
            scenario_id=scenario_id,
            step=step,
        )
        raise QualificationError(str(blocker["code"]), scenario_id)
    if completed.returncode != step.expected_exit_code:
        raise QualificationError(
            "rc_s3_107_operator_exit_code_mismatch",
            f"{scenario_id}:{step.step_id}",
        )
    if len(records) != 1:
        raise QualificationError("rc_s3_107_step_observation_stream_invalid")
    return _validate_operator_observation(
        records[0],
        manifest=manifest,
        scenario_id=scenario_id,
        step=step,
    )


def _restart_service(*, project: str, port: int, service: str) -> None:
    if service not in {"langgraph-api", "langgraph-postgres"}:
        raise QualificationError("rc_s3_107_restart_service_invalid", service)
    prefix = _compose_prefix(project)
    environment = _compose_env(port)
    restarted = _run_readonly(
        (*prefix, "restart", service),
        timeout=120.0,
        env=environment,
    )
    _require_success(restarted, "rc_s3_107_compose_restart_failed")
    wait_services = (
        ("langgraph-api",)
        if service == "langgraph-api"
        else ("langgraph-postgres", "langgraph-api")
    )
    healthy = _run_readonly(
        (*prefix, "up", "-d", "--wait", *wait_services),
        timeout=180.0,
        env=environment,
    )
    _require_success(healthy, "rc_s3_107_compose_restart_health_failed")


def _run_scenario(
    *,
    project: str,
    port: int,
    scenario_id: str,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    steps = SCENARIO_STEPS.get(scenario_id)
    if steps is None:
        raise QualificationError("rc_s3_107_scenario_plan_missing", scenario_id)
    final_receipt: dict[str, Any] | None = None
    for step in steps:
        if step.kind == "restart":
            if step.service is None:
                raise QualificationError(
                    "rc_s3_107_restart_step_contract_invalid", step.step_id
                )
            _restart_service(project=project, port=port, service=step.service)
            continue
        if step.kind == "operator":
            _run_operator_step(
                project=project,
                port=port,
                scenario_id=scenario_id,
                step=step,
                manifest=manifest,
            )
            continue
        result = _run_phase_step(
            project=project,
            port=port,
            scenario_id=scenario_id,
            step=step,
            manifest=manifest,
        )
        if step.produces_final_receipt:
            if final_receipt is not None:
                raise QualificationError(
                    "rc_s3_107_multiple_final_receipts", scenario_id
                )
            final_receipt = result
    if final_receipt is None:
        raise QualificationError("rc_s3_107_final_receipt_missing", scenario_id)
    return final_receipt


def _run_live(args: argparse.Namespace) -> int:
    # No attempt identifier, directory, container, or volume is created before
    # both preflight layers have passed.
    static = static_preflight()
    attempt_id = _attempt_id()
    project = _project_name(attempt_id)
    runtime_preflight(project, args.api_port)

    manifest = _manifest(
        attempt_id=attempt_id,
        project=project,
        port=args.api_port,
        commit=static["commit"],
        catalog_hash=static["catalog_sha256"],
    )
    attempt_dir = args.artifact_root / attempt_id
    _write_json_exclusive(attempt_dir / "manifest.json", manifest)

    try:
        prefix = _compose_prefix(project)
        compose_environment = _compose_env(args.api_port)
        config = _run_readonly(
            (*prefix, "config", "--quiet"),
            timeout=60.0,
            env=compose_environment,
        )
        _require_success(config, "rc_s3_107_compose_config_failed")
        started = _run_readonly(
            (*prefix, "up", "-d", "--build", "--wait"),
            timeout=600.0,
            env=compose_environment,
        )
        _require_success(started, "rc_s3_107_compose_start_failed")

        scenario_receipts: dict[str, Any] = {}
        for scenario in SCENARIOS:
            # There is intentionally no retry loop and no alternate attempt.
            scenario_receipt = _run_scenario(
                project=project,
                port=args.api_port,
                scenario_id=scenario.scenario_id,
                manifest=manifest,
            )
            scenario_receipts[scenario.scenario_id] = scenario_receipt
            _write_json_in_existing_attempt(
                attempt_dir / f"{scenario.scenario_id.lower()}-receipt.json",
                scenario_receipt,
            )
        validated_receipts = validate_complete_receipts(
            scenario_receipts,
            manifest=manifest,
        )

        receipt = {
            "schema_version": "fin.rc_s3_107.qualification_receipt.v1",
            "attempt_id": attempt_id,
            "project": project,
            "status": "PASS",
            "execution_boundary": dict(EXECUTION_BOUNDARY),
            "scenario_receipts": validated_receipts,
            "claim_boundary": manifest["claim_boundary"],
        }
        _write_json_in_existing_attempt(attempt_dir / "receipt.json", receipt)
    except QualificationError as exc:
        _write_json_in_existing_attempt(
            attempt_dir / "blocked.json",
            {
                "schema_version": "fin.rc_s3_107.qualification_blocker.v1",
                "attempt_id": attempt_id,
                "project": project,
                "status": "BLOCKED",
                "code": exc.code,
                "detail_present": bool(exc.detail),
            },
        )
        raise
    print(json.dumps({"status": "PASS", "attempt_id": attempt_id}))
    return 0


def _contract_only() -> int:
    value = {
        "schema_version": "fin.rc_s3_107.contract_projection.v1",
        "scenario_ids": [item.scenario_id for item in SCENARIOS],
        "blockers": list(incomplete_scenario_blockers()),
        "claim_boundary": {
            "local": "at_most_one_sdk_create_attempt_per_durable_invocation",
            "remote": "one_observed_committed_run_in_tested_single_host_topology",
            "excluded": "provider_or_network_exactly_once",
        },
        "execution_boundary": dict(EXECUTION_BOUNDARY),
    }
    _validate_sanitized(value)
    print(json.dumps(value, ensure_ascii=True, sort_keys=True))
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract-only", action="store_true")
    parser.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.contract_only:
        return _contract_only()
    try:
        return _run_live(args)
    except QualificationError as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "code": exc.code,
                    "detail_present": bool(exc.detail),
                },
                sort_keys=True,
            )
        )
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
