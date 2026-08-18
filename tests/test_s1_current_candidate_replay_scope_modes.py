from __future__ import annotations

from retrieval.candidate_ceiling_provenance import (
    candidate_provenance_scope_mode_valid,
)


def test_candidate_provenance_accepts_ready_deterministic_scope() -> None:
    assert candidate_provenance_scope_mode_valid(
        {"mode": "deterministic_scope_ready", "required_request_ids": []}
    )


def test_candidate_provenance_retains_explicit_scope_pending_as_incomplete_audit() -> None:
    assert candidate_provenance_scope_mode_valid(
        {
            "mode": "explicit_scope_required",
            "required_request_ids": ["REQ::DELL::COUNTEREVIDENCE"],
        }
    )


def test_candidate_provenance_rejects_contradictory_scope_states() -> None:
    assert not candidate_provenance_scope_mode_valid(
        {
            "mode": "deterministic_scope_ready",
            "required_request_ids": ["REQ::unexpected"],
        }
    )
    assert not candidate_provenance_scope_mode_valid(
        {"mode": "explicit_scope_required", "required_request_ids": []}
    )
    assert not candidate_provenance_scope_mode_valid(
        {"mode": "unknown", "required_request_ids": []}
    )
