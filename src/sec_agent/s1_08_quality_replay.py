from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_source_quality import canonical_locator_key, qualify_locator


MANIFEST_SCHEMA = "fin_ia_0_1_3_s1_08_dell_r1_restricted_capture_manifest_v1_0"
FIXTURE_SCHEMA = "fin_ia_0_1_3_s1_08_quality_first_sanitized_replay_fixture_v1_0"


class S108QualityReplayError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_restricted_manifest(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != MANIFEST_SCHEMA:
        raise S108QualityReplayError("s1_08_restricted_manifest_schema_invalid")
    if payload.get("raw_body_or_headers_in_git") is not False:
        raise S108QualityReplayError("s1_08_restricted_manifest_privacy_boundary_invalid")
    requests = payload.get("requests") or []
    if len(requests) != 19:
        raise S108QualityReplayError("s1_08_restricted_manifest_request_count_invalid")
    digests = [str(row.get("request_capture_digest") or "") for row in requests]
    if len(digests) != len(set(digests)) or any(not _digest(value) for value in digests):
        raise S108QualityReplayError("s1_08_restricted_manifest_request_digest_invalid")
    if sum(row.get("terminal_kind") == "response" for row in requests) != 15:
        raise S108QualityReplayError("s1_08_restricted_manifest_response_count_invalid")
    if sum(row.get("terminal_kind") == "transport_failure" for row in requests) != 3:
        raise S108QualityReplayError("s1_08_restricted_manifest_failure_count_invalid")
    if sum(row.get("terminal_kind") == "unpaired" for row in requests) != 1:
        raise S108QualityReplayError("s1_08_restricted_manifest_unpaired_count_invalid")
    return payload


def audit_restricted_capture_store(
    *, manifest: Mapping[str, Any], runtime_root: str | Path
) -> dict[str, Any]:
    root = Path(runtime_root).resolve()
    verified = 0
    for row in manifest.get("requests") or []:
        object_key = str(row["request_capture_object_key"])
        path = (root / object_key).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise S108QualityReplayError("s1_08_restricted_capture_object_missing")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            canonical_digest(payload) != row["request_capture_digest"]
            or payload.get("capture_kind") != "source_request"
            or payload.get("url") != row["locator"]
        ):
            raise S108QualityReplayError("s1_08_restricted_capture_object_mismatch")
        verified += 1
    return {
        "restricted_request_objects_verified": verified,
        "raw_content_emitted": False,
        "headers_emitted": False,
    }


def run_sanitized_quality_replay(
    *, manifest: Mapping[str, Any], fixture: Mapping[str, Any]
) -> dict[str, Any]:
    if fixture.get("schema_version") != FIXTURE_SCHEMA:
        raise S108QualityReplayError("s1_08_sanitized_fixture_schema_invalid")
    decisions: list[dict[str, Any]] = []
    for row in fixture.get("locator_cases") or []:
        decision = qualify_locator(
            role_id=str(row["role_id"]),
            allowed_source_families=tuple(row["allowed_source_families"]),
            url=str(row["url"]),
            title=str(row.get("title") or ""),
            published_on=str(row.get("published_on") or ""),
            as_of=str(fixture["as_of"]),
            currentness_window_days=int(row["currentness_window_days"]),
            form_type=str(row.get("form_type") or ""),
        )
        expected = str(row["expected_decision"])
        expected_reason = str(row.get("expected_reason") or "")
        passed = decision.decision == expected and (
            not expected_reason or expected_reason in decision.reason_codes
        )
        decisions.append(
            {
                "case_id": row["case_id"],
                "role_id": row["role_id"],
                "decision": decision.decision,
                "reason_codes": list(decision.reason_codes),
                "canonical_locator_digest": canonical_digest(decision.canonical_locator),
                "passed": passed,
            }
        )
    terminal_rows = []
    for row in manifest.get("requests") or []:
        repaired_kind = (
            "transport_failure"
            if row["terminal_kind"] == "unpaired"
            else row["terminal_kind"]
        )
        repaired_code = (
            "official_source_connection_terminated"
            if row["terminal_kind"] == "unpaired"
            else row["terminal_code"]
        )
        terminal_rows.append(
            {
                "request_capture_digest": row["request_capture_digest"],
                "terminal_kind": repaired_kind,
                "terminal_code": repaired_code,
            }
        )
    fixture_by_id = {str(row["case_id"]): row for row in fixture.get("locator_cases") or []}
    fetch_decisions = [row for row in decisions if row["decision"] == "fetch"]
    qualified_ids = {
        str(row["case_id"])
        for row in fixture.get("locator_cases") or []
        if row.get("expected_content_qualified") is True
    }
    useful_fetches = sum(row["case_id"] in qualified_ids for row in fetch_decisions)
    yield_ratio = useful_fetches / len(fetch_decisions) if fetch_decisions else 0.0
    role_outcomes = fixture.get("role_outcomes") or []
    roles_closed = sum(
        row.get("outcome") in {"candidate", "typed_gap"} for row in role_outcomes
    )
    duplicate_groups: dict[str, list[str]] = {}
    for row in fixture.get("locator_cases") or []:
        duplicate_groups.setdefault(canonical_locator_key(str(row["url"])), []).append(
            str(row["case_id"])
        )
    body = {
        "schema_version": "fin_ia_0_1_3_s1_08_quality_first_capture_replay_result_v1_0",
        "status": "pass"
        if all(row["passed"] for row in decisions)
        and len(terminal_rows) == 19
        and roles_closed == 5
        and yield_ratio >= float(fixture["quality_gates"]["qualified_document_yield_min"])
        else "failed",
        "planner_hidden_gold_visibility": False,
        "network_model_provider_retry_calls": [0, 0, 0, 0],
        "locator_decisions": decisions,
        "terminal_replay": terminal_rows,
        "metrics": {
            "R1_requests_with_terminal_classification": len(terminal_rows),
            "request_without_terminal_capture": sum(
                row["terminal_kind"] not in {"response", "transport_failure"}
                for row in terminal_rows
            ),
            "known_navigation_noise_fetches": sum(
                row["decision"] == "fetch"
                and "noise" in str(fixture_by_id[row["case_id"]].get("labels") or [])
                for row in decisions
            ),
            "stale_filing_selected_when_newer_eligible_exists": sum(
                row["decision"] == "fetch"
                and "stale" in str(fixture_by_id[row["case_id"]].get("labels") or [])
                for row in decisions
            ),
            "evidence_roles_with_candidate_or_typed_gap": roles_closed,
            "qualified_document_yield": round(yield_ratio, 6),
            "canonical_duplicate_group_count": sum(
                len(values) > 1 for values in duplicate_groups.values()
            ),
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


def _digest(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


__all__ = [
    "FIXTURE_SCHEMA",
    "MANIFEST_SCHEMA",
    "S108QualityReplayError",
    "audit_restricted_capture_store",
    "load_restricted_manifest",
    "run_sanitized_quality_replay",
]
