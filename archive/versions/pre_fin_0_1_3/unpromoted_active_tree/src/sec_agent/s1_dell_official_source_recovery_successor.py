from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.official_source_attempt_program import (
    CAPTURE_SCHEMA_SAFE_FAILURE_V1_1,
    CaptureFirstOfficialSourceClient,
    SourceTransport,
)
from sec_agent.s1_dell_targeted_source_supplement import _compile_external_route
from sec_agent.s1_six_case_local_evidence_pack import (
    file_sha256,
    validate_local_evidence_pack,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_dell_official_source_recovery_successor_policy_v1_0"
)
PROOF_SCHEMA = (
    "fin_ia_0_1_3_s1_dell_official_source_recovery_successor_clean_proof_v1_0"
)
AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s1_dell_official_source_recovery_successor_authority_v1_0"
)
RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_dell_official_source_recovery_successor_result_v1_0"
)
CONTRACT_REF = "fin_0_1_3.S1.dell_official_source_recovery_successor:v1"
RUN_SCOPE = "FIN_0_1_3_S1_DELL_ENRICHED_SOURCE_SUCCESSOR_EXACT_ONCE"
PRIVATE_NAMESPACE = "fin-0.1.3/s1/dell-official-source-recovery-successor"
PACK_NAMESPACE = f"{PRIVATE_NAMESPACE}/pack"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class DellOfficialSourceRecoverySuccessorError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellOfficialSourceRecoverySuccessorError(code)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DellOfficialSourceRecoverySuccessorError(code) from exc
    _require(isinstance(payload, dict), code)
    return payload


def _resolve(root: Path, ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _lf_normalized_utf8_sha256(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError as exc:
        raise DellOfficialSourceRecoverySuccessorError(
            "dell_official_recovery_bound_text_unreadable"
        ) from exc
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DellOfficialSourceRecoverySuccessorError(
            "dell_official_recovery_timestamp_invalid"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_binding(root: Path, binding: Mapping[str, Any], *, key: str) -> Path:
    path = _resolve(root, str(binding.get("ref") or ""))
    mode = str(binding.get("hash_mode") or "")
    expected = str(binding.get("sha256") or "")
    _require(
        path.is_file()
        and mode in {"lf_normalized_utf8", "raw_bytes"}
        and _HEX64.fullmatch(expected) is not None,
        f"dell_official_recovery_binding_invalid:{key}",
    )
    observed = (
        _lf_normalized_utf8_sha256(path)
        if mode == "lf_normalized_utf8"
        else file_sha256(path)
    )
    _require(
        observed == expected,
        f"dell_official_recovery_binding_invalid:{key}",
    )
    return path


def load_dell_official_source_recovery_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path), "dell_official_recovery_policy_json_invalid")
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("contract_ref") == CONTRACT_REF
        and policy.get("owner_stage") == "S1"
        and policy.get("case_key") == "DELL"
        and policy.get("research_as_of") == "2026-08-06",
        "dell_official_recovery_policy_identity_invalid",
    )
    bindings = dict(policy.get("immutable_bindings") or {})
    _require(
        set(bindings)
        == {
            "predecessor_public_result",
            "predecessor_private_pack",
            "historical_route_policy",
            "timeout_capture_pairs",
        },
        "dell_official_recovery_policy_bindings_invalid",
    )
    public_path = _validate_binding(
        root, bindings["predecessor_public_result"], key="predecessor_public_result"
    )
    public_result = _read_json(
        public_path, "dell_official_recovery_predecessor_result_invalid"
    )
    _require(
        public_result.get("result_digest")
        == bindings["predecessor_public_result"].get("expected_result_digest"),
        "dell_official_recovery_predecessor_result_digest_invalid",
    )
    pack_path = _validate_binding(
        root, bindings["predecessor_private_pack"], key="predecessor_private_pack"
    )
    pack = _read_json(pack_path, "dell_official_recovery_predecessor_pack_invalid")
    validate_local_evidence_pack(pack)
    _require(
        pack.get("pack_payload_digest")
        == bindings["predecessor_private_pack"].get("expected_pack_payload_digest")
        and pack.get("case_key") == "DELL",
        "dell_official_recovery_predecessor_pack_digest_invalid",
    )
    _validate_binding(
        root, bindings["historical_route_policy"], key="historical_route_policy"
    )
    autopsy = dict(policy.get("timeout_autopsy_contract") or {})
    pairs = list(bindings.get("timeout_capture_pairs") or ())
    _require(len(pairs) == 2, "dell_official_recovery_timeout_pair_count_invalid")
    for index, raw in enumerate(pairs):
        pair = dict(raw)
        request_path = _resolve(root, str(pair.get("request_ref") or ""))
        failure_path = _resolve(root, str(pair.get("failure_ref") or ""))
        _require(
            request_path.is_file()
            and failure_path.is_file()
            and file_sha256(request_path) == pair.get("request_sha256")
            and file_sha256(failure_path) == pair.get("failure_sha256"),
            f"dell_official_recovery_timeout_binding_invalid:{index}",
        )
        request = _read_json(
            request_path, "dell_official_recovery_timeout_request_invalid"
        )
        failure = _read_json(
            failure_path, "dell_official_recovery_timeout_failure_invalid"
        )
        _require(
            request.get("capture_kind") == "source_request"
            and request.get("route_id") == pair.get("route_id")
            and failure.get("capture_kind") == "source_transport_failure"
            and failure.get("route_id") == pair.get("route_id")
            and failure.get("failure_code") == autopsy.get("required_failure_code")
            and failure.get("failure_phase") == autopsy.get("required_failure_phase")
            and failure.get("safe_cause_class")
            == autopsy.get("required_safe_cause_class")
            and "status_code" not in failure
            and "body_base64" not in failure,
            f"dell_official_recovery_timeout_autopsy_invalid:{index}",
        )
    transport = dict(policy.get("retrieval_transport") or {})
    _require(
        transport.get("transport_mode") == "managed_reader_exact_url"
        and transport.get("provider_id") == "jina_reader"
        and transport.get("endpoint") == "https://r.jina.ai/"
        and transport.get("provider_is_financial_authority") is False
        and transport.get("provider_is_numeric_authority") is False
        and transport.get("origin_official_url_must_round_trip_exactly") is True
        and transport.get("intermediary_raw_response_must_be_captured_before_parse")
        is True,
        "dell_official_recovery_transport_contract_invalid",
    )
    routes = [dict(row) for row in policy.get("recovery_routes") or ()]
    _require(
        {str(row.get("route_id") or "") for row in routes}
        == {
            "dell_q1_fy27_earnings_transcript",
            "micron_q3_fy26_prepared_remarks",
        },
        "dell_official_recovery_route_set_invalid",
    )
    for route in routes:
        parsed = urlparse(str(route.get("url") or ""))
        allowed = set(str(value) for value in route.get("allowed_hosts") or ())
        _require(
            parsed.scheme == "https"
            and (parsed.hostname or "").lower() in allowed
            and route.get("official_locator")
            and route.get("retrieval_intermediary") == "jina_reader"
            and route.get("fragments")
            and all(fragment.get("required_patterns") for fragment in route["fragments"]),
            "dell_official_recovery_route_invalid",
        )
    budget = dict(policy.get("budget") or {})
    _require(
        budget
        == {
            "official_source_network_calls": 2,
            "maximum_live_network_invocations": 2,
            "timeout_seconds_per_route": 45,
            "model_calls": 0,
            "retries": 0,
        },
        "dell_official_recovery_budget_invalid",
    )
    return policy


def _load_predecessor_pack(
    *, policy: Mapping[str, Any], repo_root: Path
) -> dict[str, Any]:
    ref = policy["immutable_bindings"]["predecessor_private_pack"]["ref"]
    pack = _read_json(
        _resolve(repo_root, str(ref)),
        "dell_official_recovery_predecessor_pack_invalid",
    )
    validate_local_evidence_pack(pack)
    return pack


def _merge_pack(
    *,
    predecessor: Mapping[str, Any],
    materials_to_add: Sequence[Mapping[str, Any]],
    evidence_to_add: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    route_results: Sequence[Mapping[str, Any]],
    gate_status: Mapping[str, bool],
) -> dict[str, Any]:
    body = deepcopy(dict(predecessor))
    body.pop("pack_payload_digest", None)
    materials = [deepcopy(dict(row)) for row in body.get("source_materials") or ()]
    evidence = [deepcopy(dict(row)) for row in body.get("evidence_items") or ()]
    material_index = {str(row["material_ref"]): row for row in materials}
    target_ids = {str(row["target_id"]) for row in evidence}
    for raw in materials_to_add:
        row = deepcopy(dict(raw))
        ref = str(row["material_ref"])
        if ref in material_index:
            _require(
                material_index[ref].get("source_text_digest")
                == row.get("source_text_digest")
                and material_index[ref].get("source_url") == row.get("source_url"),
                "dell_official_recovery_material_collision",
            )
            continue
        material_index[ref] = row
        materials.append(row)
    for raw in evidence_to_add:
        row = deepcopy(dict(raw))
        _require(
            str(row["target_id"]) not in target_ids,
            "dell_official_recovery_evidence_collision",
        )
        target_ids.add(str(row["target_id"]))
        evidence.append(row)
    disposition = dict(policy.get("gap_disposition") or {})
    never_remove = set(str(value) for value in disposition.get("never_remove") or ())
    removals = {
        str(rule["gap_id"])
        for rule in disposition.get("remove_when_satisfied") or ()
        if set(str(value) for value in rule.get("requires_target_ids") or ())
        <= target_ids
    }
    _require(
        not (removals & never_remove),
        "dell_official_recovery_forbidden_gap_removal",
    )
    gaps = [
        deepcopy(dict(row))
        for row in predecessor.get("residual_gaps") or ()
        if str(row.get("gap_id") or "") not in removals
    ]
    direct = sum(
        row.get("disposition") == "accepted_direct_source_evidence"
        for row in evidence
    )
    context = sum(
        row.get("disposition") == "accepted_bounded_context_evidence"
        for row in evidence
    )
    market = sum(
        row.get("disposition") == "accepted_independent_market_evidence"
        for row in evidence
    )
    body.update(
        {
            "content_gate_basis": (
                "immutable_enriched_predecessor_plus_capture_first_managed_reader_"
                "official_document_recovery"
            ),
            "source_materials": sorted(materials, key=lambda row: row["material_ref"]),
            "evidence_items": sorted(evidence, key=lambda row: row["target_id"]),
            "residual_gaps": sorted(
                gaps, key=lambda row: (row["slot_id"], row["facet_id"])
            ),
            "observed_counts": {
                "accepted_evidence_items": len(evidence),
                "direct_evidence_items": direct,
                "bounded_context_items": context,
                "independent_market_items": market,
                "rejected_items": len(body.get("rejected_items") or ()),
                "residual_gaps": len(gaps),
                "source_materials": len(materials),
                "numeric_facts": len(body.get("numeric_facts") or ()),
            },
            "official_source_recovery_lineage": {
                "contract_ref": CONTRACT_REF,
                "predecessor_pack_payload_digest": predecessor["pack_payload_digest"],
                "predecessor_source_result_digest": policy["immutable_bindings"][
                    "predecessor_public_result"
                ]["expected_result_digest"],
                "failed_timeout_capture_count": 2,
                "route_results": [deepcopy(dict(row)) for row in route_results],
                "gap_ids_removed_as_satisfied": sorted(removals),
                "gate_status": deepcopy(dict(gate_status)),
                "successful_tsmc_and_alpha_inputs_reused_without_network": True,
                "retrieval_intermediary_is_not_financial_authority": True,
                "origin_direct_response_bytes_preserved": False,
                "intermediary_raw_response_preserved": True,
            },
            "known_boundary": (
                "Dell and Micron excerpts were retrieved from exact official URLs through "
                "a captured managed-reader intermediary. The intermediary is not financial "
                "or numeric authority. Supplier evidence remains bounded read-through, and "
                "the Pack still does not authorize fair value, target price or recommendation."
            ),
        }
    )
    successor = {**body, "pack_payload_digest": canonical_digest(body)}
    validate_local_evidence_pack(successor)
    return successor


def validate_dell_official_source_recovery_authority(
    authority: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    observed_at: str,
    execution_commit: str,
) -> None:
    body = deepcopy(dict(authority))
    digest = str(body.pop("authority_digest", ""))
    _require(
        authority.get("schema_version") == AUTHORITY_SCHEMA
        and authority.get("contract_ref") == CONTRACT_REF
        and authority.get("run_scope") == RUN_SCOPE
        and authority.get("status") == "issued_unconsumed"
        and digest == canonical_digest(body)
        and authority.get("policy_digest") == canonical_digest(policy)
        and authority.get("implementation_commit") == execution_commit
        and re.fullmatch(r"[0-9a-f]{40}", execution_commit) is not None,
        "dell_official_recovery_authority_identity_invalid",
    )
    _require(
        _utc(str(authority["issued_at"]))
        <= _utc(observed_at)
        <= _utc(str(authority["expires_at"]))
        and authority.get("maximum_executions") == 1
        and authority.get("automatic_retry") is False
        and authority.get("business_artifact_promotion") is False
        and authority.get("model_calls_allowed") == 0
        and authority.get("budget") == policy.get("budget"),
        "dell_official_recovery_authority_boundary_invalid",
    )
    root = Path(repo_root).resolve()
    for ref, expected in (authority.get("file_bindings") or {}).items():
        path = _resolve(root, str(ref))
        _require(
            path.is_file() and file_sha256(path) == str(expected),
            "dell_official_recovery_authority_file_binding_invalid",
        )


def validate_dell_official_source_recovery_clean_proof(
    proof: Mapping[str, Any],
) -> None:
    body = deepcopy(dict(proof))
    digest = str(body.pop("proof_digest", ""))
    counts = dict(proof.get("observed_counts") or {})
    mutations = dict(proof.get("mutations") or {})
    _require(
        proof.get("schema_version") == PROOF_SCHEMA
        and proof.get("contract_ref") == CONTRACT_REF
        and proof.get("status")
        == "clean_independent_dell_official_source_recovery_zero_call_proof_passed"
        and digest == canonical_digest(body)
        and proof.get("fresh_worker_count") == 2
        and proof.get("workers_byte_equivalent") is True
        and counts.get("network_calls") == 0
        and counts.get("model_calls") == 0
        and counts.get("new_evidence_items") == 5
        and counts.get("evidence_items_after") == 27
        and counts.get("residual_gaps_after") == 14
        and all(mutations.values()),
        "dell_official_recovery_clean_proof_invalid",
    )


def execute_dell_official_source_recovery_successor(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    runtime_root: str | Path,
    transport: SourceTransport,
    observed_at: str,
    execution_commit: str,
    authority: Mapping[str, Any] | None = None,
    shared_admission_ledger: SharedAdmissionConsumptionLedger | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    runtime = Path(runtime_root).resolve()
    _require(
        not runtime.exists(), "dell_official_recovery_runtime_already_exists"
    )
    if transport.live_network:
        _require(
            authority is not None and shared_admission_ledger is not None,
            "dell_official_recovery_live_authority_required",
        )
        validate_dell_official_source_recovery_authority(
            authority,
            policy=policy,
            repo_root=root,
            observed_at=observed_at,
            execution_commit=execution_commit,
        )
        shared_admission_ledger.reserve(
            admission_digest=str(authority["authority_digest"]),
            admission_id=str(authority["admission_id"]),
            scope=CONTRACT_REF,
            run_id=str(authority["run_id"]),
            attempt_id=str(authority["attempt_id"]),
            runtime_identity=str(runtime),
            reserved_at=observed_at,
        )
    runtime.mkdir(parents=True, exist_ok=False)
    predecessor = _load_predecessor_pack(policy=policy, repo_root=root)
    store = FileCanonicalObjectStore(runtime / "objects")
    client = CaptureFirstOfficialSourceClient(
        store=store,
        transport=transport,
        namespace=f"{PRIVATE_NAMESPACE}/official",
        capture_schema=CAPTURE_SCHEMA_SAFE_FAILURE_V1_1,
    )
    materials: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    route_results: list[dict[str, Any]] = []
    for route in policy["recovery_routes"]:
        response, attempt = client.fetch(
            case_key="DELL",
            route_id=str(route["route_id"]),
            url=str(route["url"]),
            allowed_hosts=set(str(value) for value in route["allowed_hosts"]),
            timeout_seconds=int(policy["budget"]["timeout_seconds_per_route"]),
            byte_ceiling=int(route["byte_ceiling"]),
        )
        new_materials, new_evidence, result = _compile_external_route(
            route=route,
            response=response,
            attempt=attempt,
        )
        result.update(
            {
                "capture_reused": False,
                "new_network_call": bool(transport.live_network),
                "official_origin_url": str(route["url"]),
                "official_locator": str(route["official_locator"]),
                "retrieval_intermediary": "jina_reader",
                "retrieval_intermediary_is_financial_authority": False,
            }
        )
        materials.extend(new_materials)
        evidence.extend(new_evidence)
        route_results.append(result)
    by_route = {str(row["route_id"]): row for row in route_results}
    predecessor_targets = {
        str(row.get("target_id") or "") for row in predecessor.get("evidence_items") or ()
    }
    dell = by_route["dell_q1_fy27_earnings_transcript"]
    micron = by_route["micron_q3_fy26_prepared_remarks"]
    core_ready = (
        dell.get("status") == "captured_parsed_and_adjudicated"
        and int(dell.get("fragments_materialized") or 0)
        == int(dell.get("fragments_expected") or -1)
        and "SUPPLEMENT::DELL::SUPPLIER::TSM::COWOS_CAPACITY"
        in predecessor_targets
    )
    supplier_ready = (
        micron.get("status") == "captured_parsed_and_adjudicated"
        and int(micron.get("fragments_materialized") or 0)
        == int(micron.get("fragments_expected") or -1)
    )
    valuation_ready = (
        "MARKET::DELL::RAW_CLOSE::2026-08-06" in predecessor_targets
        and len(predecessor.get("numeric_facts") or ()) == 1
    )
    gates = {
        "core_research_ready": core_ready,
        "supplier_context_ready": supplier_ready,
        "valuation_input_ready": valuation_ready,
        "valuation_ready": valuation_ready,
        "successor_pack_ready_for_model_input": core_ready,
    }
    successor = _merge_pack(
        predecessor=predecessor,
        materials_to_add=materials,
        evidence_to_add=evidence,
        policy=policy,
        route_results=route_results,
        gate_status=gates,
    )
    pack_ref = store.put_json(
        successor,
        namespace=PACK_NAMESPACE,
        artifact_type="dell_official_source_recovered_evidence_pack",
    )
    status = (
        "terminal_succeeded_core_supplier_and_valuation_input_ready"
        if core_ready and supplier_ready and valuation_ready
        else (
            "terminal_succeeded_core_research_ready_with_typed_optional_gaps"
            if core_ready
            else "terminal_completed_core_research_not_ready"
        )
    )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "recorded_at": observed_at,
        "status": status,
        "source_commit": execution_commit,
        "attempt_id": (
            str(authority["attempt_id"]) if authority is not None else "zero_call_fixture"
        ),
        "research_as_of": str(policy["research_as_of"]),
        "policy_digest": canonical_digest(policy),
        "predecessor_source_result_digest": policy["immutable_bindings"][
            "predecessor_public_result"
        ]["expected_result_digest"],
        "predecessor_pack_payload_digest": predecessor["pack_payload_digest"],
        "successor_pack_payload_digest": successor["pack_payload_digest"],
        "successor_pack_artifact": pack_ref,
        "timeout_autopsy": {
            "capture_pairs_replayed": 2,
            "earliest_failure_phase": "connect_or_read",
            "safe_cause_class": "timeout",
            "http_response_observed": False,
            "parser_reached": False,
        },
        "route_results": route_results,
        "gate_status": gates,
        "observed_counts": {
            "official_source_network_calls": client.network_calls,
            "model_calls": 0,
            "retries": 0,
            "new_source_materials": len(materials),
            "new_evidence_items": len(evidence),
            "evidence_items_before": len(predecessor["evidence_items"]),
            "evidence_items_after": len(successor["evidence_items"]),
            "residual_gaps_before": len(predecessor["residual_gaps"]),
            "residual_gaps_after": len(successor["residual_gaps"]),
            "reused_numeric_facts": len(successor.get("numeric_facts") or ()),
        },
        "stage_acceptance": {
            "capture_first": True,
            "timeout_capture_replay_passed": True,
            "official_origin_identity_round_trip_required": True,
            "intermediary_raw_response_preserved_before_parse": True,
            "managed_reader_promoted_as_financial_authority": False,
            "predecessor_attempt_immutable": True,
            "successful_tsmc_and_alpha_inputs_reused_without_network": True,
            "deepseek_exact_live_authorized": False,
            "business_artifact_promoted": False,
        },
        "known_boundary": (
            "Core readiness authorizes only compilation of a changed fixed Evidence Pack. "
            "It does not prove report quality, fair value, target price, recommendation, "
            "Owner acceptance or release readiness."
        ),
    }
    result = {**body, "result_digest": canonical_digest(body)}
    if transport.live_network and authority is not None and shared_admission_ledger is not None:
        shared_admission_ledger.finalize(
            admission_digest=str(authority["authority_digest"]),
            run_id=str(authority["run_id"]),
            attempt_id=str(authority["attempt_id"]),
            terminal_status=("success" if core_ready else "completed_with_gaps"),
            terminal_phase="dell_official_source_recovery_successor_terminal",
            terminal_code=status,
            terminal_result_digest=result["result_digest"],
            finalized_at=observed_at,
        )
    return result


__all__ = [
    "AUTHORITY_SCHEMA",
    "CONTRACT_REF",
    "DellOfficialSourceRecoverySuccessorError",
    "POLICY_SCHEMA",
    "PROOF_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "execute_dell_official_source_recovery_successor",
    "load_dell_official_source_recovery_policy",
    "validate_dell_official_source_recovery_authority",
    "validate_dell_official_source_recovery_clean_proof",
]
