from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.official_source_attempt_program import (
    OfficialSourceAttemptError,
    SourceResponse,
    parse_source_document,
)
from sec_agent.s1_dell_targeted_source_supplement import (
    _extract_fragment,
    _smallest_regex_window,
)
from sec_agent.s1_six_case_local_evidence_pack import file_sha256


POLICY_SCHEMA = "fin_ia_0_1_3_s1_dell_targeted_source_recovery_policy_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_dell_targeted_source_recovery_result_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.dell_targeted_source_recovery:v1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class DellTargetedSourceRecoveryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellTargetedSourceRecoveryError(code)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DellTargetedSourceRecoveryError(code) from exc
    _require(isinstance(value, dict), code)
    return value


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def load_recovery_policy(path: str | Path, *, repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path), "dell_targeted_recovery_policy_json_invalid")
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("contract_ref") == CONTRACT_REF
        and policy.get("case_key") == "DELL"
        and policy.get("research_as_of") == "2026-08-06",
        "dell_targeted_recovery_policy_identity_invalid",
    )
    for key in ("historical_policy", "historical_result"):
        binding = dict(policy.get(key) or {})
        source = _resolve(root, str(binding.get("ref") or ""))
        _require(
            source.is_file()
            and _HEX64.fullmatch(str(binding.get("sha256") or "")) is not None
            and file_sha256(source) == binding["sha256"],
            f"dell_targeted_recovery_binding_invalid:{key}",
        )
    result = _read_json(
        _resolve(root, str(policy["historical_result"]["ref"])),
        "dell_targeted_recovery_historical_result_invalid",
    )
    _require(
        result.get("result_digest")
        == policy["historical_result"].get("expected_result_digest"),
        "dell_targeted_recovery_historical_result_digest_invalid",
    )
    replay = dict(policy.get("tsmc_capture_replay") or {})
    _require(
        _HEX64.fullmatch(str(replay.get("capture_digest") or "")) is not None
        and _HEX64.fullmatch(str(replay.get("body_sha256") or "")) is not None
        and replay.get("required_patterns")
        and 0 < int(replay.get("max_anchor_span") or 0) <= 4000,
        "dell_targeted_recovery_replay_contract_invalid",
    )
    routes = list(policy.get("route_qualification") or ())
    _require(
        {str(row.get("route_family") or "") for row in routes}
        == {"dell_issuer_transcript", "micron_supplier_disclosure", "market_point_in_time"},
        "dell_targeted_recovery_route_families_invalid",
    )
    return policy


def _load_response_capture(
    policy: Mapping[str, Any], *, repo_root: Path
) -> tuple[dict[str, Any], SourceResponse]:
    replay = dict(policy["tsmc_capture_replay"])
    path = _resolve(repo_root, str(replay["private_capture_ref"]))
    capture = _read_json(path, "dell_targeted_recovery_capture_missing_or_invalid")
    _require(
        file_sha256(path) == replay["capture_digest"]
        and capture.get("capture_kind") == "source_response"
        and capture.get("body_sha256") == replay["body_sha256"],
        "dell_targeted_recovery_capture_binding_invalid",
    )
    try:
        body = base64.b64decode(str(capture["body_base64"]), validate=True)
    except (KeyError, ValueError) as exc:
        raise DellTargetedSourceRecoveryError(
            "dell_targeted_recovery_capture_body_invalid"
        ) from exc
    _require(
        hashlib.sha256(body).hexdigest() == replay["body_sha256"],
        "dell_targeted_recovery_capture_body_digest_invalid",
    )
    response = SourceResponse(
        status_code=int(capture["status_code"]),
        final_url=str(capture["final_url"]),
        headers=dict(capture.get("headers") or {}),
        body=body,
        redirect_chain=tuple(capture.get("redirect_chain") or ()),
    )
    return capture, response


def _safe_failure_matrix() -> list[dict[str, str]]:
    codes = [
        "official_source_transport_timeout",
        "official_source_dns_resolution_failed",
        "official_source_tls_handshake_failed",
        "official_source_connection_refused",
        "official_source_connection_terminated",
        "official_source_transport_failed",
    ]
    return [
        {
            "failure_code": code,
            **OfficialSourceAttemptError(code).safe_failure_envelope(),
        }
        for code in codes
    ]


def compile_recovery_result(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    recorded_at: str,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    _capture, response = _load_response_capture(policy, repo_root=root)
    parsed = parse_source_document(response)
    _require(
        parsed.get("status") == "parsed",
        "dell_targeted_recovery_capture_parse_failed",
    )
    replay = dict(policy["tsmc_capture_replay"])
    patterns = [str(value) for value in replay["required_patterns"]]
    text = str(parsed["text"])
    occurrence_counts = {
        pattern: len(list(re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL)))
        for pattern in patterns
    }
    first_matches = [
        re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        for pattern in patterns
    ]
    _require(
        all(match is not None for match in first_matches),
        "dell_targeted_recovery_required_pattern_missing",
    )
    first_start = min(match.start() for match in first_matches if match is not None)
    first_end = max(match.end() for match in first_matches if match is not None)
    selected_start, selected_end = _smallest_regex_window(
        text,
        required_patterns=patterns,
        max_anchor_span=int(replay["max_anchor_span"]),
        missing_code="dell_targeted_recovery_required_pattern_missing",
    )
    excerpt = _extract_fragment(
        text,
        required_patterns=patterns,
        before=int(replay["excerpt_before"]),
        after=int(replay["excerpt_after"]),
        max_anchor_span=int(replay["max_anchor_span"]),
        code="dell_targeted_recovery_required_pattern_missing",
    )
    implementation = (
        root / "src/sec_agent/s1_dell_targeted_source_supplement.py"
    ).read_text(encoding="utf-8")
    _require(
        "close_token" not in implementation,
        "dell_targeted_recovery_expected_market_value_leakage_present",
    )
    routes = [deepcopy(dict(row)) for row in policy["route_qualification"]]
    route_gates = {
        str(row["route_family"]): str(row["qualification_status"])
        for row in routes
    }
    dell_route_ready = route_gates["dell_issuer_transcript"] == (
        "official_direct_document_and_locator_qualified_for_one_capture"
    )
    market_route_ready = route_gates["market_point_in_time"] == (
        "executable_exact_date_route_qualified_without_expected_value"
    )
    authority_ready = dell_route_ready and market_route_ready
    blocking_gates: list[str] = []
    if not dell_route_ready:
        blocking_gates.append("dell_issuer_transcript_executable_route_unproven")
    if not market_route_ready:
        blocking_gates.append(
            "market_point_in_time_executable_exact_date_request_unproven"
        )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "recorded_at": recorded_at,
        "status": (
            "zero_call_recovery_proof_passed_authority_ready"
            if authority_ready
            else "zero_call_recovery_proof_passed_authority_not_ready"
        ),
        "case_key": "DELL",
        "research_as_of": str(policy["research_as_of"]),
        "policy_digest": canonical_digest(policy),
        "historical_result_digest": policy["historical_result"][
            "expected_result_digest"
        ],
        "tsmc_capture_replay": {
            "capture_digest": replay["capture_digest"],
            "body_sha256": replay["body_sha256"],
            "parser_adapter": parsed["adapter"],
            "parsed_text_sha256": parsed["text_sha256"],
            "parsed_text_chars": len(text),
            "required_pattern_occurrence_counts": occurrence_counts,
            "legacy_first_occurrence_anchor_span": first_end - first_start,
            "selected_coherent_anchor_span": selected_end - selected_start,
            "configured_max_anchor_span": int(replay["max_anchor_span"]),
            "excerpt_chars": len(excerpt),
            "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            "fragment_character_ceiling": 4000,
            "character_ceiling_increased": False,
            "raw_source_text_publicly_materialized": False,
            "status": "captured_parsed_and_coherently_adjudicated",
        },
        "safe_transport_failure_contract": {
            "capture_schema": "fin_ia_0_1_3_official_source_capture_v1_1",
            "typed_safe_cause_matrix": _safe_failure_matrix(),
            "raw_exception_text_persisted": False,
            "credential_cookie_authorization_persisted": False,
            "status": "zero_call_fault_injection_proven",
        },
        "market_point_in_time_contract": {
            "identity_fields_bound": [
                "ticker",
                "target_date",
                "currency",
                "source_lineage",
            ],
            "expected_close_value_bound": False,
            "captured_close_must_be_parseable": True,
            "exact_live_row_materialized": False,
            "status": "answer_leakage_removed_but_route_not_yet_proven",
        },
        "route_qualification": routes,
        "authority_decision": {
            "status": "ready" if authority_ready else "not_ready",
            "new_source_authority_issued": False,
            "blocking_gates": blocking_gates,
            "deepseek_or_report_comparison_authorized": False,
        },
        "observed_counts": {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "retries": 0,
            "tsmc_fragments_recovered": 1,
            "route_families_qualified": len(routes),
            "authority_blocking_gates": len(blocking_gates),
        },
    }
    result = {**body, "result_digest": canonical_digest(body)}
    validate_recovery_result(result, policy=policy)
    return result


def validate_recovery_result(
    result: Mapping[str, Any], *, policy: Mapping[str, Any]
) -> None:
    body = deepcopy(dict(result))
    supplied = body.pop("result_digest", None)
    replay = dict(result.get("tsmc_capture_replay") or {})
    decision = dict(result.get("authority_decision") or {})
    counts = dict(result.get("observed_counts") or {})
    _require(
        result.get("schema_version") == RESULT_SCHEMA
        and result.get("contract_ref") == CONTRACT_REF
        and supplied == canonical_digest(body)
        and result.get("policy_digest") == canonical_digest(policy)
        and replay.get("status") == "captured_parsed_and_coherently_adjudicated"
        and replay.get("character_ceiling_increased") is False
        and int(replay.get("selected_coherent_anchor_span") or 0)
        <= int(replay.get("configured_max_anchor_span") or 0)
        and decision.get("status") == "not_ready"
        and decision.get("new_source_authority_issued") is False
        and decision.get("deepseek_or_report_comparison_authorized") is False
        and counts
        == {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "retries": 0,
            "tsmc_fragments_recovered": 1,
            "route_families_qualified": 3,
            "authority_blocking_gates": 1,
        },
        "dell_targeted_recovery_result_invalid",
    )
