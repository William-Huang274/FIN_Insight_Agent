from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.market_data_adapter import (
    AKSHARE_SHADOW_PROVIDER_ID,
    ALPHA_VANTAGE_PROVIDER_ID,
    CaptureFirstMarketDataClient,
    MarketDataAdapter,
    MarketPointRequest,
)
from sec_agent.official_source_attempt_program import (
    CAPTURE_SCHEMA_SAFE_FAILURE_V1_1,
    CaptureFirstOfficialSourceClient,
    SourceResponse,
    SourceTransport,
)
from sec_agent.s1_dell_targeted_source_supplement import (
    _compile_external_route,
    _compile_material_and_evidence,
)
from sec_agent.s1_six_case_local_evidence_pack import (
    file_sha256,
    validate_local_evidence_pack,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


POLICY_SCHEMA = "fin_ia_0_1_3_s1_dell_enriched_source_successor_policy_v1_0"
PROOF_SCHEMA = "fin_ia_0_1_3_s1_dell_enriched_source_successor_clean_proof_v1_0"
AUTHORITY_SCHEMA = "fin_ia_0_1_3_s1_dell_enriched_source_successor_authority_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_dell_enriched_source_successor_result_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.dell_enriched_source_successor:v1"
RUN_SCOPE = "FIN_0_1_3_S1_DELL_ENRICHED_SOURCE_SUCCESSOR_EXACT_ONCE"
PRIVATE_NAMESPACE = "fin-0.1.3/s1/dell-enriched-source-successor"
PACK_NAMESPACE = f"{PRIVATE_NAMESPACE}/pack"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class DellEnrichedSourceSuccessorError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellEnrichedSourceSuccessorError(code)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DellEnrichedSourceSuccessorError(code) from exc
    _require(isinstance(payload, dict), code)
    return payload


def _resolve(root: Path, ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _lf_normalized_utf8_sha256(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError as exc:
        raise DellEnrichedSourceSuccessorError(
            "dell_enriched_bound_text_unreadable"
        ) from exc
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DellEnrichedSourceSuccessorError("dell_enriched_timestamp_invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_dell_enriched_source_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path), "dell_enriched_policy_json_invalid")
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("contract_ref") == CONTRACT_REF
        and policy.get("owner_stage") == "S1"
        and policy.get("case_key") == "DELL"
        and policy.get("research_as_of") == "2026-08-06",
        "dell_enriched_policy_identity_invalid",
    )
    bindings = dict(policy.get("immutable_bindings") or {})
    required_bindings = {
        "historical_source_policy",
        "historical_source_result",
        "recovery_policy",
        "recovery_result",
        "predecessor_dell_pack",
    }
    _require(set(bindings) == required_bindings, "dell_enriched_policy_bindings_invalid")
    for key, binding in bindings.items():
        value = dict(binding)
        source = _resolve(root, str(value.get("ref") or ""))
        hash_mode = str(value.get("hash_mode") or "")
        _require(
            source.is_file()
            and hash_mode in {"lf_normalized_utf8", "raw_bytes"}
            and _HEX64.fullmatch(str(value.get("sha256") or "")) is not None,
            f"dell_enriched_policy_binding_invalid:{key}",
        )
        observed_hash = (
            _lf_normalized_utf8_sha256(source)
            if hash_mode == "lf_normalized_utf8"
            else file_sha256(source)
        )
        _require(
            observed_hash == value["sha256"],
            f"dell_enriched_policy_binding_invalid:{key}",
        )
        payload = _read_json(source, f"dell_enriched_bound_json_invalid:{key}")
        if value.get("expected_result_digest"):
            _require(
                payload.get("result_digest") == value["expected_result_digest"],
                f"dell_enriched_bound_result_digest_invalid:{key}",
            )
        if value.get("expected_pack_payload_digest"):
            validate_local_evidence_pack(payload)
            _require(
                payload.get("pack_payload_digest") == value["expected_pack_payload_digest"]
                and payload.get("case_key") == "DELL",
                "dell_enriched_predecessor_pack_digest_invalid",
            )
    historical = _read_json(
        _resolve(root, bindings["historical_source_policy"]["ref"]),
        "dell_enriched_historical_source_policy_invalid",
    )
    route_ids = {str(row["route_id"]) for row in historical["external_routes"]}
    _require(
        set(policy.get("official_route_ids") or ())
        == {
            "dell_q1_fy27_earnings_transcript",
            "micron_q3_fy26_earnings_slides",
        }
        and str(policy.get("saved_capture_route_id") or "") in route_ids,
        "dell_enriched_route_selection_invalid",
    )
    market = dict(policy.get("market_request") or {})
    _require(
        market.get("ticker") == "DELL"
        and market.get("exchange") == "NYSE"
        and market.get("exact_date") == policy["research_as_of"]
        and market.get("primary_provider") == ALPHA_VANTAGE_PROVIDER_ID
        and market.get("shadow_provider") == AKSHARE_SHADOW_PROVIDER_ID
        and re.fullmatch(r"1\.18\.\d+", str(market.get("shadow_dependency_version") or ""))
        is not None
        and market.get("slot_bindings")
        and market.get("target_id"),
        "dell_enriched_market_request_invalid",
    )
    gates = dict(policy.get("gate_contract") or {})
    _require(
        gates.get("core_research_may_proceed_when_valuation_input_missing") is True
        and gates.get("shadow_provider_may_promote") is False
        and gates.get("valuation_ready_display_alias") == "valuation_input_ready",
        "dell_enriched_gate_contract_invalid",
    )
    budget = dict(policy.get("budget") or {})
    _require(
        budget.get("official_source_network_calls") == 2
        and budget.get("primary_market_provider_invocations") == 1
        and budget.get("shadow_market_provider_invocations") == 1
        and budget.get("maximum_live_network_invocations") == 4
        and budget.get("model_calls") == 0
        and budget.get("retries") == 0,
        "dell_enriched_budget_invalid",
    )
    return policy


def _historical_policy(
    *, policy: Mapping[str, Any], repo_root: Path
) -> dict[str, Any]:
    ref = policy["immutable_bindings"]["historical_source_policy"]["ref"]
    return _read_json(
        _resolve(repo_root, str(ref)),
        "dell_enriched_historical_source_policy_invalid",
    )


def _load_predecessor_pack(
    *, policy: Mapping[str, Any], repo_root: Path
) -> dict[str, Any]:
    ref = policy["immutable_bindings"]["predecessor_dell_pack"]["ref"]
    pack = _read_json(_resolve(repo_root, str(ref)), "dell_enriched_predecessor_pack_invalid")
    validate_local_evidence_pack(pack)
    return pack


def _compile_saved_tsmc(
    *,
    policy: Mapping[str, Any],
    historical_policy: Mapping[str, Any],
    repo_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    recovery_ref = policy["immutable_bindings"]["recovery_policy"]["ref"]
    recovery = _read_json(
        _resolve(repo_root, str(recovery_ref)),
        "dell_enriched_recovery_policy_invalid",
    )
    replay = dict(recovery.get("tsmc_capture_replay") or {})
    capture_path = _resolve(repo_root, str(replay.get("private_capture_ref") or ""))
    capture = _read_json(
        capture_path,
        "dell_enriched_tsmc_capture_missing_or_invalid",
    )
    _require(
        file_sha256(capture_path) == str(replay.get("capture_digest") or "")
        and capture.get("capture_kind") == "source_response"
        and capture.get("body_sha256") == replay.get("body_sha256"),
        "dell_enriched_tsmc_capture_binding_invalid",
    )
    try:
        response_body = base64.b64decode(str(capture["body_base64"]), validate=True)
    except (KeyError, ValueError) as exc:
        raise DellEnrichedSourceSuccessorError(
            "dell_enriched_tsmc_capture_body_invalid"
        ) from exc
    _require(
        hashlib.sha256(response_body).hexdigest() == replay["body_sha256"],
        "dell_enriched_tsmc_capture_body_digest_invalid",
    )
    response = SourceResponse(
        status_code=int(capture["status_code"]),
        final_url=str(capture["final_url"]),
        headers=dict(capture.get("headers") or {}),
        body=response_body,
        redirect_chain=tuple(capture.get("redirect_chain") or ()),
    )
    route = next(
        dict(row)
        for row in historical_policy["external_routes"]
        if row["route_id"] == policy["saved_capture_route_id"]
    )
    response_ref = {
        "object_key": replay["private_capture_ref"],
        "digest": replay["capture_digest"],
        "body_sha256": replay["body_sha256"],
    }
    materials, evidence, route_result = _compile_external_route(
        route=route,
        response=response,
        attempt={
            "status": "captured",
            "failure_code": "",
            "request_capture": {},
            "response_capture": response_ref,
        },
    )
    route_result.update(
        {
            "capture_reused": True,
            "new_network_call": False,
            "historical_capture_kind": str(capture.get("capture_kind") or ""),
            "required_for_core_research_gate": True,
        }
    )
    return materials, evidence, route_result


def _compile_market_material_and_evidence(
    *,
    fact: Mapping[str, Any],
    market_spec: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_text = json.dumps(
        {
            "provider_id": fact["provider_id"],
            "ticker": fact["entity_ticker"],
            "exchange": fact["exchange"],
            "observation_date": fact["observation_date"],
            "raw_close": fact["normalized_value"],
            "currency": fact["currency"],
            "unit": fact["unit"],
            "price_basis": fact["price_basis"],
            "source_coordinate": fact["source_coordinate"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    material, evidence = _compile_material_and_evidence(
        spec={
            **dict(market_spec),
            "evidence_role": "independent_market_point_in_time",
        },
        source_record_id=str(market_spec["target_id"]),
        source_text=source_text,
        source_url=str(fact["source_endpoint"]),
        source_type="market_data_api_exact_date_raw_daily",
        source_tier="independent_market_data_primary",
        period_end=str(fact["observation_date"]),
        source_lineage={
            "lineage_kind": "capture_first_provider_neutral_market_numeric_fact",
            "numeric_fact_id": fact["numeric_fact_id"],
            "numeric_fact_digest": fact["numeric_fact_digest"],
            "response_capture_ref": fact["response_capture_ref"],
            "response_capture_digest": fact["response_capture_digest"],
            "provider_id": fact["provider_id"],
            "selection_rule_id": str(market_spec["target_id"]),
        },
    )
    evidence.update(
        {
            "object_type": "metric",
            "structured_metric": {
                "metric_name": "raw_daily_close",
                "row_label": "Close",
                "raw_value": str(fact["normalized_value"]),
                "normalized_value": str(fact["normalized_value"]),
                "currency": str(fact["currency"]),
                "unit": str(fact["unit"]),
                "scale_multiplier": 1,
                "period": str(fact["observation_date"]),
                "table_path": str(fact["source_coordinate"]),
                "price_basis": str(fact["price_basis"]),
                "numeric_fact_id": str(fact["numeric_fact_id"]),
                "numeric_fact_digest": str(fact["numeric_fact_digest"]),
                "currency_unit_authority": {
                    "status": "source_and_child_consistent",
                    "currency": str(fact["currency"]),
                    "unit": str(fact["unit"]),
                },
            },
        }
    )
    evidence_body = deepcopy(evidence)
    evidence_body.pop("evidence_item_digest", None)
    evidence["evidence_item_digest"] = canonical_digest(evidence_body)
    return material, evidence


def _merge_successor_pack(
    *,
    predecessor: Mapping[str, Any],
    materials_to_add: Sequence[Mapping[str, Any]],
    evidence_to_add: Sequence[Mapping[str, Any]],
    primary_fact: Mapping[str, Any] | None,
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
        material_ref = str(row["material_ref"])
        if material_ref in material_index:
            existing = material_index[material_ref]
            _require(
                existing.get("source_text_digest") == row.get("source_text_digest")
                and existing.get("source_url") == row.get("source_url"),
                "dell_enriched_source_material_collision",
            )
            continue
        material_index[material_ref] = row
        materials.append(row)
    for raw in evidence_to_add:
        row = deepcopy(dict(raw))
        _require(
            str(row["target_id"]) not in target_ids,
            "dell_enriched_evidence_target_collision",
        )
        target_ids.add(str(row["target_id"]))
        evidence.append(row)

    dispositions = dict(policy.get("gap_disposition") or {})
    never_remove = set(str(value) for value in dispositions.get("never_remove_from_single_close") or ())
    removals = {
        str(rule["gap_id"])
        for rule in dispositions.get("remove_when_satisfied") or ()
        if set(str(value) for value in rule.get("requires_target_ids") or ()) <= target_ids
    }
    _require(not (removals & never_remove), "dell_enriched_forbidden_gap_removal")
    gaps = [
        deepcopy(dict(row))
        for row in predecessor.get("residual_gaps") or ()
        if str(row.get("gap_id") or "") not in removals
    ]
    direct = sum(row.get("disposition") == "accepted_direct_source_evidence" for row in evidence)
    context = sum(row.get("disposition") == "accepted_bounded_context_evidence" for row in evidence)
    market = sum(row.get("disposition") == "accepted_independent_market_evidence" for row in evidence)
    body.update(
        {
            "content_gate_basis": "immutable_predecessor_plus_capture_first_enriched_successor",
            "source_materials": sorted(materials, key=lambda row: row["material_ref"]),
            "evidence_items": sorted(evidence, key=lambda row: row["target_id"]),
            "residual_gaps": sorted(gaps, key=lambda row: (row["slot_id"], row["facet_id"])),
            "numeric_facts": ([deepcopy(dict(primary_fact))] if primary_fact is not None else []),
            "observed_counts": {
                "accepted_evidence_items": len(evidence),
                "direct_evidence_items": direct,
                "bounded_context_items": context,
                "independent_market_items": market,
                "rejected_items": len(body.get("rejected_items") or ()),
                "residual_gaps": len(gaps),
                "source_materials": len(materials),
                "numeric_facts": int(primary_fact is not None),
            },
            "enriched_successor_lineage": {
                "contract_ref": CONTRACT_REF,
                "predecessor_pack_payload_digest": predecessor["pack_payload_digest"],
                "route_results": [deepcopy(dict(row)) for row in route_results],
                "gap_ids_removed_as_satisfied": sorted(removals),
                "gate_status": deepcopy(dict(gate_status)),
                "saved_capture_reused_without_network": True,
            },
            "known_boundary": (
                "This successor adds bounded issuer, supplier and exact-date market inputs. "
                "A market close is only a valuation operand; it does not authorize a fair "
                "value, target price, recommendation or Dell-specific supplier allocation."
            ),
        }
    )
    successor = {**body, "pack_payload_digest": canonical_digest(body)}
    validate_local_evidence_pack(successor)
    return successor


def validate_dell_enriched_source_authority(
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
        "dell_enriched_authority_identity_invalid",
    )
    _require(
        _utc(str(authority["issued_at"])) <= _utc(observed_at) <= _utc(str(authority["expires_at"]))
        and authority.get("maximum_executions") == 1
        and authority.get("automatic_retry") is False
        and authority.get("business_artifact_promotion") is False
        and authority.get("model_calls_allowed") == 0
        and authority.get("budget") == policy.get("budget"),
        "dell_enriched_authority_boundary_invalid",
    )
    root = Path(repo_root).resolve()
    for ref, expected in (authority.get("file_bindings") or {}).items():
        path = _resolve(root, str(ref))
        _require(
            path.is_file() and file_sha256(path) == str(expected),
            "dell_enriched_authority_file_binding_invalid",
        )


def validate_dell_enriched_source_clean_proof(proof: Mapping[str, Any]) -> None:
    body = deepcopy(dict(proof))
    digest = str(body.pop("proof_digest", ""))
    counts = dict(proof.get("observed_counts") or {})
    gates = dict(proof.get("gate_mutations") or {})
    _require(
        proof.get("schema_version") == PROOF_SCHEMA
        and proof.get("contract_ref") == CONTRACT_REF
        and proof.get("status") == "clean_independent_dell_enriched_successor_zero_call_proof_passed"
        and digest == canonical_digest(body)
        and proof.get("fresh_worker_count") == 2
        and proof.get("workers_byte_equivalent") is True
        and counts.get("network_calls") == 0
        and counts.get("model_calls") == 0
        and gates.get("core_true_valuation_false") is True
        and gates.get("core_false_valuation_true") is True
        and gates.get("both_true") is True
        and proof.get("credential_capture_mutation_rejected") is True,
        "dell_enriched_clean_proof_invalid",
    )


def execute_dell_enriched_source_successor(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    runtime_root: str | Path,
    official_transport: SourceTransport,
    primary_market_adapter: MarketDataAdapter,
    primary_market_credential: str | None,
    shadow_market_adapter: MarketDataAdapter | None,
    observed_at: str,
    execution_commit: str,
    authority: Mapping[str, Any] | None = None,
    shared_admission_ledger: SharedAdmissionConsumptionLedger | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    runtime = Path(runtime_root).resolve()
    _require(not runtime.exists(), "dell_enriched_runtime_already_exists")
    live = bool(official_transport.live_network or primary_market_adapter.live_network)
    if shadow_market_adapter is not None:
        live = live or bool(shadow_market_adapter.live_network)
    if live:
        _require(
            authority is not None and shared_admission_ledger is not None,
            "dell_enriched_live_authority_required",
        )
        validate_dell_enriched_source_authority(
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
    store = FileCanonicalObjectStore(runtime / "objects")
    historical = _historical_policy(policy=policy, repo_root=root)
    predecessor = _load_predecessor_pack(policy=policy, repo_root=root)
    route_index = {str(row["route_id"]): dict(row) for row in historical["external_routes"]}
    source_client = CaptureFirstOfficialSourceClient(
        store=store,
        transport=official_transport,
        namespace=f"{PRIVATE_NAMESPACE}/official",
        capture_schema=CAPTURE_SCHEMA_SAFE_FAILURE_V1_1,
    )
    materials: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    route_results: list[dict[str, Any]] = []
    tsmc_materials, tsmc_evidence, tsmc_result = _compile_saved_tsmc(
        policy=policy,
        historical_policy=historical,
        repo_root=root,
    )
    materials.extend(tsmc_materials)
    evidence.extend(tsmc_evidence)
    route_results.append(tsmc_result)
    for route_id in policy["official_route_ids"]:
        route = route_index[str(route_id)]
        response, attempt = source_client.fetch(
            case_key="DELL",
            route_id=str(route["route_id"]),
            url=str(route["url"]),
            allowed_hosts=set(route["allowed_hosts"]),
            timeout_seconds=int(policy["budget"]["timeout_seconds_per_route"]),
            byte_ceiling=int(route["byte_ceiling"]),
        )
        new_materials, new_evidence, route_result = _compile_external_route(
            route=route,
            response=response,
            attempt=attempt,
        )
        route_result.update(
            {
                "capture_reused": False,
                "new_network_call": bool(official_transport.live_network),
                "required_for_core_research_gate": route_id.startswith("dell_"),
                "required_for_supplier_context_gate": route_id.startswith("micron_"),
            }
        )
        materials.extend(new_materials)
        evidence.extend(new_evidence)
        route_results.append(route_result)

    market_spec = dict(policy["market_request"])
    market_request = MarketPointRequest(
        case_key="DELL",
        ticker=str(market_spec["ticker"]),
        exchange=str(market_spec["exchange"]),
        exact_date=str(market_spec["exact_date"]),
        currency=str(market_spec["currency"]),
        price_basis=str(market_spec["price_basis"]),
    )
    market_client = CaptureFirstMarketDataClient(
        store=store,
        namespace=f"{PRIVATE_NAMESPACE}/market",
    )
    primary_fact, primary_result = market_client.fetch_exact_close(
        request=market_request,
        adapter=primary_market_adapter,
        credential=primary_market_credential,
        timeout_seconds=int(policy["budget"]["timeout_seconds_per_route"]),
        byte_ceiling=int(policy["budget"]["market_response_byte_ceiling"]),
    )
    primary_result["authoritative_for_pack"] = primary_fact is not None
    route_results.append(primary_result)
    if primary_fact is not None:
        market_material, market_evidence = _compile_market_material_and_evidence(
            fact=primary_fact,
            market_spec=market_spec,
        )
        materials.append(market_material)
        evidence.append(market_evidence)

    shadow_fact: dict[str, Any] | None = None
    if shadow_market_adapter is not None:
        shadow_fact, shadow_result = market_client.fetch_exact_close(
            request=market_request,
            adapter=shadow_market_adapter,
            credential=None,
            timeout_seconds=int(policy["budget"]["timeout_seconds_per_route"]),
            byte_ceiling=int(policy["budget"]["market_response_byte_ceiling"]),
        )
        shadow_result["authoritative_for_pack"] = False
        route_results.append(shadow_result)
    shadow_comparison: dict[str, Any]
    if primary_fact is not None and shadow_fact is not None:
        delta = abs(
            Decimal(str(primary_fact["normalized_value"]))
            - Decimal(str(shadow_fact["normalized_value"]))
        )
        shadow_comparison = {
            "status": "compared_diagnostic_only",
            "absolute_difference_usd": format(delta, "f"),
            "equal_to_cent": delta <= Decimal("0.01"),
            "shadow_may_promote": False,
        }
    else:
        shadow_comparison = {
            "status": "comparison_unavailable",
            "absolute_difference_usd": None,
            "equal_to_cent": None,
            "shadow_may_promote": False,
        }

    by_route = {str(row.get("route_id") or row.get("provider_id") or ""): row for row in route_results}
    dell_route = by_route["dell_q1_fy27_earnings_transcript"]
    micron_route = by_route["micron_q3_fy26_earnings_slides"]
    tsmc_route = by_route["tsmc_q1_2026_earnings_transcript"]
    core_research_ready = (
        dell_route.get("status") == "captured_parsed_and_adjudicated"
        and int(dell_route.get("fragments_materialized") or 0)
        == int(dell_route.get("fragments_expected") or -1)
        and tsmc_route.get("status") == "captured_parsed_and_adjudicated"
        and int(tsmc_route.get("fragments_materialized") or 0) == 1
    )
    supplier_context_ready = (
        micron_route.get("status") == "captured_parsed_and_adjudicated"
        and int(micron_route.get("fragments_materialized") or 0)
        == int(micron_route.get("fragments_expected") or -1)
    )
    valuation_input_ready = primary_fact is not None
    gates = {
        "core_research_ready": core_research_ready,
        "supplier_context_ready": supplier_context_ready,
        "valuation_input_ready": valuation_input_ready,
        "valuation_ready": valuation_input_ready,
        "successor_pack_ready_for_model_input": core_research_ready,
    }
    successor = _merge_successor_pack(
        predecessor=predecessor,
        materials_to_add=materials,
        evidence_to_add=evidence,
        primary_fact=primary_fact,
        policy=policy,
        route_results=route_results,
        gate_status=gates,
    )
    pack_ref = store.put_json(
        successor,
        namespace=PACK_NAMESPACE,
        artifact_type="dell_enriched_capture_first_evidence_pack",
    )
    if core_research_ready and supplier_context_ready and valuation_input_ready:
        status = "terminal_succeeded_core_supplier_and_valuation_input_ready"
    elif core_research_ready:
        status = "terminal_succeeded_core_research_ready_with_typed_optional_gaps"
    else:
        status = "terminal_completed_core_research_not_ready"
    public_body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "recorded_at": observed_at,
        "status": status,
        "source_commit": execution_commit,
        "attempt_id": str(authority["attempt_id"]) if authority is not None else "zero_call_fixture",
        "research_as_of": str(policy["research_as_of"]),
        "policy_digest": canonical_digest(policy),
        "predecessor_pack_payload_digest": predecessor["pack_payload_digest"],
        "successor_pack_payload_digest": successor["pack_payload_digest"],
        "successor_pack_artifact": pack_ref,
        "route_results": route_results,
        "shadow_comparison": shadow_comparison,
        "gate_status": gates,
        "observed_counts": {
            "official_source_network_calls": source_client.network_calls,
            "market_provider_invocations": market_client.provider_invocations,
            "market_network_invocations": market_client.network_calls,
            "model_calls": 0,
            "retries": 0,
            "new_source_materials": len(materials),
            "new_evidence_items": len(evidence),
            "evidence_items_before": len(predecessor["evidence_items"]),
            "evidence_items_after": len(successor["evidence_items"]),
            "residual_gaps_before": len(predecessor["residual_gaps"]),
            "residual_gaps_after": len(successor["residual_gaps"]),
        },
        "stage_acceptance": {
            "capture_first": True,
            "credential_value_never_captured": True,
            "predecessor_attempt_immutable": True,
            "saved_tsmc_capture_reused_without_network": True,
            "core_and_valuation_gates_reported_separately": True,
            "counterparty_claim_boundary_preserved": True,
            "shadow_provider_promoted": False,
            "deepseek_exact_live_authorized": False,
            "business_artifact_promoted": False,
        },
        "known_boundary": (
            "This source result may authorize compilation of a changed Evidence Pack only "
            "when core_research_ready is true. It does not prove report quality, valuation, "
            "model gain, target price, recommendation or release readiness."
        ),
    }
    result = {**public_body, "result_digest": canonical_digest(public_body)}
    if live and authority is not None and shared_admission_ledger is not None:
        shared_admission_ledger.finalize(
            admission_digest=str(authority["authority_digest"]),
            run_id=str(authority["run_id"]),
            attempt_id=str(authority["attempt_id"]),
            terminal_status=("success" if core_research_ready else "completed_with_gaps"),
            terminal_phase="dell_enriched_source_successor_terminal",
            terminal_code=status,
            terminal_result_digest=result["result_digest"],
            finalized_at=observed_at,
        )
    return result


__all__ = [
    "AUTHORITY_SCHEMA",
    "CONTRACT_REF",
    "DellEnrichedSourceSuccessorError",
    "POLICY_SCHEMA",
    "PROOF_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "execute_dell_enriched_source_successor",
    "load_dell_enriched_source_policy",
    "validate_dell_enriched_source_authority",
    "validate_dell_enriched_source_clean_proof",
]
