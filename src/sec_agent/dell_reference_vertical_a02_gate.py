from __future__ import annotations

from collections.abc import Mapping
import hashlib
from pathlib import Path
import re
from typing import Any


DELL_REFERENCE_VERTICAL_A02_DECISION_SCHEMA = (
    "fin_ia_dell_reference_vertical_a02_paid_start_scope_decision_v1_0"
)
DELL_REFERENCE_VERTICAL_A02_RUN_SCOPE = (
    "one_DELL_reference_vertical_structured_A02_start_to_HITL_exact_once"
)
DELL_REFERENCE_VERTICAL_A02_STATUS = (
    "owner_authorized_one_A02_paid_start_to_HITL_after_clean_pushed_commit_"
    "and_zero_call_preflights"
)
_IDENTITY = {
    "schema_version": DELL_REFERENCE_VERTICAL_A02_DECISION_SCHEMA,
    "status": DELL_REFERENCE_VERTICAL_A02_STATUS,
    "case_key": "DELL",
    "cell_id": "DELL_AI_INFRA_REFERENCE_VERTICAL::STRUCTURED_A02",
    "run_scope_id": DELL_REFERENCE_VERTICAL_A02_RUN_SCOPE,
    "attempt_id": "20260902-dell-reference-vertical-structured-a02",
    "run_id": "dell-reference-vertical-structured-run-a02",
    "snapshot_id": "20260902-dell-structured-s1-s2-external-a02",
    "research_as_of": "2026-09-02T23:59:59+08:00",
    "credential_presence_required": True,
    "api_key_env": "DEEPSEEK_API_KEY",
}
_AUTHORITY = {
    "automatic_human_approval": False,
    "candidate_promotion_authorized": False,
    "evidence_admission_authorized": False,
    "formal_qualification_authorized": False,
    "model_fallback_authorized": False,
    "model_retry_authorized": False,
    "paid_start_to_hitl_attempts": 1,
    "product_acceptance_authorized": False,
    "publication_authorized": False,
    "release_authorized": False,
    "render_authorized": False,
    "resume_approve_authorized": False,
    "resume_reject_authorized": False,
}
_LAUNCHER_REF = "scripts/research/run_dell_reference_vertical_structured_a02.ps1"
_LEGACY_RUNTIME_RETIREMENT_CODE = (
    "dell_legacy_runtime_retired_agent_server_langsmith_required"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_dell_reference_vertical_a02_paid_start_scope_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    expected_keys = {*_IDENTITY, "authority", "launcher_binding", "known_boundary"}
    if set(decision) != expected_keys:
        raise ValueError("dell_a02_decision_shape_invalid")
    if any(decision.get(key) != value for key, value in _IDENTITY.items()):
        raise ValueError("dell_a02_decision_identity_invalid")
    if decision.get("authority") != _AUTHORITY:
        raise ValueError("dell_a02_authority_invalid")

    launcher = decision.get("launcher_binding")
    if not isinstance(launcher, Mapping) or set(launcher) != {"ref", "sha256"}:
        raise ValueError("dell_a02_launcher_binding_invalid")
    launcher_sha = str(launcher.get("sha256") or "")
    if launcher.get("ref") != _LAUNCHER_REF or not _SHA256.fullmatch(launcher_sha):
        raise ValueError("dell_a02_launcher_binding_invalid")
    launcher_path = (root.resolve() / _LAUNCHER_REF).resolve()
    launcher_path.relative_to(root.resolve())
    if not launcher_path.is_file():
        raise ValueError("dell_a02_launcher_binding_drift")
    try:
        launcher_text = launcher_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError("dell_a02_launcher_binding_drift") from exc
    if _LEGACY_RUNTIME_RETIREMENT_CODE in launcher_text:
        raise ValueError("dell_a02_launcher_retired")
    if _sha256(launcher_path) != launcher_sha:
        raise ValueError("dell_a02_launcher_binding_drift")

    known_boundary = str(decision.get("known_boundary") or "")
    required_terms = (
        "one paid A02 start to HITL",
        "candidate-only",
        "no automatic Evidence admission",
        "no approve or reject resume",
        "no render, publication, formal qualification, product acceptance, or release",
        "new owner-authorized attempt identity",
    )
    if not all(term in known_boundary for term in required_terms):
        raise ValueError("dell_a02_known_boundary_invalid")

    return {
        "dell_reference_vertical_a02_paid_start": True,
        "run_scope_id": decision["run_scope_id"],
        "case_key": decision["case_key"],
        "cell_id": decision["cell_id"],
        "api_key_env": decision["api_key_env"],
        "attempt_id": decision["attempt_id"],
        "run_id": decision["run_id"],
        "snapshot_id": decision["snapshot_id"],
        "evidence_mode": (
            "reviewed_evidence_plus_structured_candidate_plus_fresh_S2_plus_"
            "frozen_external_candidate_pack"
        ),
        "start_to_hitl_only": True,
        "resume_authorized": False,
        "render_authorized": False,
        "publication_authorized": False,
        "formal_qualification_authorized": False,
    }


__all__ = [
    "DELL_REFERENCE_VERTICAL_A02_DECISION_SCHEMA",
    "DELL_REFERENCE_VERTICAL_A02_RUN_SCOPE",
    "DELL_REFERENCE_VERTICAL_A02_STATUS",
    "validate_dell_reference_vertical_a02_paid_start_scope_decision",
]
