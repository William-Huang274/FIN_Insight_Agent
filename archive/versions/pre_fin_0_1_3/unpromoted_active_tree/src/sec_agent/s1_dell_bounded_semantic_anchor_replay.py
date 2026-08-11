from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from sec_agent.bounded_semantic_anchor import (
    BoundedSemanticAnchorError,
    extract_bounded_semantic_excerpt,
    reject_legacy_unbounded_pattern_surface,
    validate_literal_anchor_groups,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.s1_dell_targeted_source_supplement import (
    _compile_material_and_evidence,
)
from sec_agent.s1_six_case_local_evidence_pack import (
    file_sha256,
    validate_local_evidence_pack,
)


POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_dell_bounded_semantic_anchor_replay_policy_v1_0"
)
PROOF_SCHEMA = (
    "fin_ia_0_1_3_s1_dell_bounded_semantic_anchor_replay_clean_proof_v1_0"
)
RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_dell_bounded_semantic_anchor_replay_result_v1_0"
)
CONTRACT_REF = "fin_0_1_3.S1.dell_bounded_semantic_anchor_replay:v1"
RUN_SCOPE = "FIN_0_1_3_S1_DELL_BOUNDED_SEMANTIC_ANCHOR_CAPTURE_REPLAY"
PRIVATE_NAMESPACE = "fin-0.1.3/s1/dell-bounded-semantic-anchor-replay"
PACK_NAMESPACE = f"{PRIVATE_NAMESPACE}/pack"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class DellBoundedSemanticAnchorReplayError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellBoundedSemanticAnchorReplayError(code)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DellBoundedSemanticAnchorReplayError(code) from exc
    _require(isinstance(payload, dict), code)
    return payload


def _resolve(root: Path, ref: str) -> Path:
    value = Path(ref)
    path = value.resolve() if value.is_absolute() else (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise DellBoundedSemanticAnchorReplayError(
            "bounded_anchor_binding_outside_repo"
        ) from exc
    return path


def _lf_normalized_utf8_sha256(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError as exc:
        raise DellBoundedSemanticAnchorReplayError(
            "bounded_anchor_bound_text_unreadable"
        ) from exc
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_binding(root: Path, binding: Mapping[str, Any], *, key: str) -> Path:
    path = _resolve(root, str(binding.get("ref") or ""))
    mode = str(binding.get("hash_mode") or "")
    expected = str(binding.get("sha256") or "")
    _require(
        path.is_file()
        and mode in {"lf_normalized_utf8", "raw_bytes"}
        and _HEX64.fullmatch(expected) is not None,
        f"bounded_anchor_binding_invalid:{key}",
    )
    observed = (
        _lf_normalized_utf8_sha256(path)
        if mode == "lf_normalized_utf8"
        else file_sha256(path)
    )
    _require(observed == expected, f"bounded_anchor_binding_invalid:{key}")
    return path


def _validate_fragment(fragment: Mapping[str, Any]) -> None:
    try:
        reject_legacy_unbounded_pattern_surface(fragment)
        contract = dict(fragment.get("anchor_contract") or {})
        _require(
            contract.get("kind") == "literal_phrase_groups_v1"
            and 0 < int(contract.get("max_anchor_span") or 0) <= 4000
            and 0 < int(contract.get("max_excerpt_chars") or 0) <= 4000
            and 0 <= int(contract.get("excerpt_before") or 0) <= 1000
            and 0 <= int(contract.get("excerpt_after") or 0) <= 2000,
            "bounded_anchor_fragment_contract_invalid",
        )
        validate_literal_anchor_groups(contract.get("required_anchor_groups") or ())
    except BoundedSemanticAnchorError as exc:
        raise DellBoundedSemanticAnchorReplayError(exc.code) from exc


def load_dell_bounded_semantic_anchor_replay_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path), "bounded_anchor_policy_json_invalid")
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("contract_ref") == CONTRACT_REF
        and policy.get("owner_stage") == "S1"
        and policy.get("case_key") == "DELL"
        and policy.get("research_as_of") == "2026-08-06",
        "bounded_anchor_policy_identity_invalid",
    )
    bindings = dict(policy.get("immutable_bindings") or {})
    _require(
        set(bindings)
        == {
            "predecessor_public_result",
            "predecessor_private_pack",
            "historical_recovery_policy",
            "historical_recovery_result",
            "response_captures",
        },
        "bounded_anchor_policy_bindings_invalid",
    )
    predecessor_result_path = _validate_binding(
        root,
        bindings["predecessor_public_result"],
        key="predecessor_public_result",
    )
    predecessor_result = _read_json(
        predecessor_result_path, "bounded_anchor_predecessor_result_invalid"
    )
    _require(
        predecessor_result.get("result_digest")
        == bindings["predecessor_public_result"].get("expected_result_digest"),
        "bounded_anchor_predecessor_result_digest_invalid",
    )
    predecessor_pack_path = _validate_binding(
        root,
        bindings["predecessor_private_pack"],
        key="predecessor_private_pack",
    )
    predecessor_pack = _read_json(
        predecessor_pack_path, "bounded_anchor_predecessor_pack_invalid"
    )
    validate_local_evidence_pack(predecessor_pack)
    _require(
        predecessor_pack.get("pack_payload_digest")
        == bindings["predecessor_private_pack"].get(
            "expected_pack_payload_digest"
        ),
        "bounded_anchor_predecessor_pack_digest_invalid",
    )
    _validate_binding(
        root, bindings["historical_recovery_policy"], key="historical_recovery_policy"
    )
    historical_result_path = _validate_binding(
        root, bindings["historical_recovery_result"], key="historical_recovery_result"
    )
    historical_result = _read_json(
        historical_result_path, "bounded_anchor_historical_result_invalid"
    )
    _require(
        historical_result.get("result_digest")
        == bindings["historical_recovery_result"].get("expected_result_digest")
        and historical_result.get("gate_status", {}).get("core_research_ready")
        is False
        and historical_result.get("observed_counts", {}).get("new_evidence_items")
        == 3,
        "bounded_anchor_historical_result_digest_invalid",
    )

    capture_bindings = [
        dict(value) for value in bindings.get("response_captures") or ()
    ]
    _require(
        {row.get("route_id") for row in capture_bindings}
        == {
            "dell_q1_fy27_earnings_transcript",
            "micron_q3_fy26_prepared_remarks",
        },
        "bounded_anchor_capture_set_invalid",
    )
    for capture_binding in capture_bindings:
        capture_path = _validate_binding(
            root,
            capture_binding,
            key=f"response_capture:{capture_binding.get('route_id')}",
        )
        capture = _read_json(capture_path, "bounded_anchor_capture_invalid")
        _require(
            capture.get("capture_kind") == "source_response"
            and capture.get("route_id") == capture_binding.get("route_id")
            and capture.get("status_code") == 200
            and capture.get("final_url") == capture_binding.get("official_url")
            and capture.get("transport_metadata", {}).get("origin_url_echo")
            == capture_binding.get("official_url")
            and capture.get("transport_metadata", {}).get(
                "retrieval_intermediary"
            )
            == "jina_reader",
            "bounded_anchor_capture_identity_invalid",
        )

    routes = [dict(value) for value in policy.get("replay_routes") or ()]
    _require(
        {row.get("route_id") for row in routes}
        == {row.get("route_id") for row in capture_bindings},
        "bounded_anchor_route_set_invalid",
    )
    captures_by_route = {str(row["route_id"]): row for row in capture_bindings}
    for route in routes:
        route_id = str(route.get("route_id") or "")
        parsed = urlparse(str(route.get("url") or ""))
        _require(
            parsed.scheme == "https"
            and (parsed.hostname or "").lower()
            in set(str(value) for value in route.get("allowed_hosts") or ())
            and route.get("url") == captures_by_route[route_id].get("official_url")
            and route.get("fragments"),
            "bounded_anchor_route_invalid",
        )
        for fragment in route["fragments"]:
            _validate_fragment(fragment)
    _require(
        policy.get("budget")
        == {"network_calls": 0, "model_calls": 0, "retries": 0},
        "bounded_anchor_budget_invalid",
    )
    return policy


def _decode_reader_capture(
    *,
    root: Path,
    binding: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    capture_path = _validate_binding(
        root, binding, key=f"response_capture:{binding.get('route_id')}"
    )
    capture = _read_json(capture_path, "bounded_anchor_capture_invalid")
    try:
        body = base64.b64decode(str(capture["body_base64"]), validate=True)
        payload = json.loads(body)
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise DellBoundedSemanticAnchorReplayError(
            "bounded_anchor_capture_body_invalid"
        ) from exc
    _require(
        hashlib.sha256(body).hexdigest() == capture.get("body_sha256")
        and int(capture.get("body_bytes") or 0) == len(body),
        "bounded_anchor_capture_body_digest_invalid",
    )
    data = dict(payload.get("data") or {})
    text = str(data.get("content") or "")
    official_url = str(binding["official_url"])
    _require(
        payload.get("code") == 200
        and data.get("url") == official_url
        and capture.get("final_url") == official_url
        and len(text) >= 1000,
        "bounded_anchor_reader_payload_invalid",
    )
    return text, {
        "capture_ref": str(binding["ref"]),
        "capture_digest": str(binding["sha256"]),
        "response_body_sha256": str(capture["body_sha256"]),
        "body_bytes": len(body),
        "source_text_chars": len(text),
        "origin_url_echo": str(data["url"]),
        "retrieval_intermediary": "jina_reader",
        "capture_reused": True,
        "new_network_call": False,
    }


def _compile_route(
    *,
    route: Mapping[str, Any],
    source_text: str,
    capture_receipt: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    materials: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    fragment_results: list[dict[str, Any]] = []
    for fragment in route["fragments"]:
        contract = dict(fragment["anchor_contract"])
        try:
            excerpt, anchor_receipt = extract_bounded_semantic_excerpt(
                source_text,
                required_anchor_groups=contract["required_anchor_groups"],
                before=int(contract["excerpt_before"]),
                after=int(contract["excerpt_after"]),
                max_anchor_span=int(contract["max_anchor_span"]),
                max_excerpt_chars=int(contract["max_excerpt_chars"]),
            )
        except BoundedSemanticAnchorError as exc:
            fragment_results.append(
                {
                    "fragment_id": str(fragment["fragment_id"]),
                    "target_id": str(fragment["target_id"]),
                    "status": "rejected",
                    "failure_code": exc.code,
                }
            )
            continue
        material, item = _compile_material_and_evidence(
            spec={**dict(route), **dict(fragment)},
            source_record_id=(
                f"official_capture_replay::{route['route_id']}::{fragment['fragment_id']}"
            ),
            source_text=excerpt,
            source_url=str(route["url"]),
            source_type=str(route["source_type"]),
            source_tier=str(route["source_tier"]),
            period_end=str(route["period_end"]),
            source_lineage={
                "lineage_kind": (
                    "immutable_managed_reader_capture_bounded_semantic_anchor_replay"
                ),
                "official_origin_url": str(route["url"]),
                "official_locator": str(route["official_locator"]),
                "retrieval_intermediary": "jina_reader",
                "retrieval_intermediary_is_financial_authority": False,
                "origin_direct_response_bytes_preserved": False,
                "intermediary_raw_response_preserved": True,
                "response_capture_ref": str(capture_receipt["capture_ref"]),
                "response_capture_digest": str(capture_receipt["capture_digest"]),
                "response_body_sha256": str(
                    capture_receipt["response_body_sha256"]
                ),
                "semantic_anchor_receipt": anchor_receipt,
            },
        )
        materials.append(material)
        evidence.append(item)
        fragment_results.append(
            {
                "fragment_id": str(fragment["fragment_id"]),
                "target_id": str(fragment["target_id"]),
                "status": "materialized",
                "failure_code": "",
                "anchor_window_chars": int(
                    anchor_receipt["anchor_window_chars"]
                ),
                "excerpt_chars": int(anchor_receipt["excerpt_chars"]),
                "selected_anchor_groups": [
                    str(row["group_id"])
                    for row in anchor_receipt["selected_anchors"]
                ],
            }
        )
    complete = len(evidence) == len(route["fragments"])
    return materials, evidence, {
        "route_id": str(route["route_id"]),
        "status": (
            "capture_replayed_and_all_fragments_adjudicated"
            if complete
            else "capture_replayed_with_anchor_failures"
        ),
        "failure_code": "" if complete else "semantic_anchor_replay_incomplete",
        "fragments_expected": len(route["fragments"]),
        "fragments_materialized": len(evidence),
        "fragment_results": fragment_results,
        "official_origin_url": str(route["url"]),
        "official_locator": str(route["official_locator"]),
        **dict(capture_receipt),
    }


def _load_predecessor_pack(
    *, policy: Mapping[str, Any], repo_root: Path
) -> dict[str, Any]:
    binding = policy["immutable_bindings"]["predecessor_private_pack"]
    pack = _read_json(
        _resolve(repo_root, str(binding["ref"])),
        "bounded_anchor_predecessor_pack_invalid",
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
                "bounded_anchor_material_collision",
            )
            continue
        material_index[ref] = row
        materials.append(row)
    for raw in evidence_to_add:
        row = deepcopy(dict(raw))
        _require(
            str(row["target_id"]) not in target_ids,
            "bounded_anchor_evidence_collision",
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
    _require(not (removals & never_remove), "bounded_anchor_forbidden_gap_removal")
    gaps = [
        deepcopy(dict(row))
        for row in predecessor.get("residual_gaps") or ()
        if str(row.get("gap_id") or "") not in removals
    ]
    body.update(
        {
            "content_gate_basis": (
                "immutable_enriched_predecessor_plus_bounded_semantic_anchor_replay_"
                "of_immutable_managed_reader_captures"
            ),
            "source_materials": sorted(materials, key=lambda row: row["material_ref"]),
            "evidence_items": sorted(evidence, key=lambda row: row["target_id"]),
            "residual_gaps": sorted(
                gaps, key=lambda row: (row["slot_id"], row["facet_id"])
            ),
            "observed_counts": {
                "accepted_evidence_items": len(evidence),
                "direct_evidence_items": sum(
                    row.get("disposition") == "accepted_direct_source_evidence"
                    for row in evidence
                ),
                "bounded_context_items": sum(
                    row.get("disposition") == "accepted_bounded_context_evidence"
                    for row in evidence
                ),
                "independent_market_items": sum(
                    row.get("disposition") == "accepted_independent_market_evidence"
                    for row in evidence
                ),
                "rejected_items": len(body.get("rejected_items") or ()),
                "residual_gaps": len(gaps),
                "source_materials": len(materials),
                "numeric_facts": len(body.get("numeric_facts") or ()),
            },
            "bounded_semantic_anchor_replay_lineage": {
                "contract_ref": CONTRACT_REF,
                "predecessor_pack_payload_digest": predecessor["pack_payload_digest"],
                "historical_failed_result_digest": policy["immutable_bindings"][
                    "historical_recovery_result"
                ]["expected_result_digest"],
                "route_results": [deepcopy(dict(row)) for row in route_results],
                "gap_ids_removed_as_satisfied": sorted(removals),
                "gate_status": deepcopy(dict(gate_status)),
                "network_calls": 0,
                "model_calls": 0,
                "historical_result_preserved": True,
            },
            "known_boundary": (
                "The Pack re-adjudicates immutable official-document captures with a "
                "bounded literal-anchor compiler. It does not re-fetch sources, elevate "
                "the retrieval intermediary, prove report quality, fair value, target "
                "price, recommendation, Owner acceptance or release readiness."
            ),
        }
    )
    successor = {**body, "pack_payload_digest": canonical_digest(body)}
    validate_local_evidence_pack(successor)
    return successor


def execute_dell_bounded_semantic_anchor_replay(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    runtime_root: str | Path,
    observed_at: str,
    execution_commit: str,
    clean_proof_digest: str = "",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    runtime = Path(runtime_root).resolve()
    _require(not runtime.exists(), "bounded_anchor_runtime_already_exists")
    _require(
        re.fullmatch(r"[0-9a-f]{40}", execution_commit) is not None,
        "bounded_anchor_execution_commit_invalid",
    )
    runtime.mkdir(parents=True, exist_ok=False)
    predecessor = _load_predecessor_pack(policy=policy, repo_root=root)
    store = FileCanonicalObjectStore(runtime / "objects")
    capture_bindings = {
        str(row["route_id"]): row
        for row in policy["immutable_bindings"]["response_captures"]
    }
    materials: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    route_results: list[dict[str, Any]] = []
    for route in policy["replay_routes"]:
        source_text, capture_receipt = _decode_reader_capture(
            root=root,
            binding=capture_bindings[str(route["route_id"])],
        )
        new_materials, new_evidence, route_result = _compile_route(
            route=route,
            source_text=source_text,
            capture_receipt=capture_receipt,
        )
        materials.extend(new_materials)
        evidence.extend(new_evidence)
        route_results.append(route_result)

    by_route = {str(row["route_id"]): row for row in route_results}
    predecessor_targets = {
        str(row.get("target_id") or "")
        for row in predecessor.get("evidence_items") or ()
    }
    dell = by_route["dell_q1_fy27_earnings_transcript"]
    micron = by_route["micron_q3_fy26_prepared_remarks"]
    core_ready = (
        dell["status"] == "capture_replayed_and_all_fragments_adjudicated"
        and dell["fragments_materialized"] == dell["fragments_expected"]
        and "SUPPLEMENT::DELL::SUPPLIER::TSM::COWOS_CAPACITY"
        in predecessor_targets
    )
    supplier_ready = (
        micron["status"] == "capture_replayed_and_all_fragments_adjudicated"
        and micron["fragments_materialized"] == micron["fragments_expected"]
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
        artifact_type="dell_bounded_semantic_anchor_corrected_evidence_pack",
    )
    status = (
        "zero_network_replay_core_supplier_and_valuation_input_ready"
        if core_ready and supplier_ready and valuation_ready
        else "zero_network_replay_core_research_not_ready"
    )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "recorded_at": observed_at,
        "status": status,
        "source_commit": execution_commit,
        "clean_proof_digest": clean_proof_digest,
        "research_as_of": str(policy["research_as_of"]),
        "policy_digest": canonical_digest(policy),
        "historical_failed_result_digest": policy["immutable_bindings"][
            "historical_recovery_result"
        ]["expected_result_digest"],
        "predecessor_pack_payload_digest": predecessor["pack_payload_digest"],
        "corrected_pack_payload_digest": successor["pack_payload_digest"],
        "corrected_pack_artifact": pack_ref,
        "route_results": route_results,
        "gate_status": gates,
        "observed_counts": {
            "network_calls": 0,
            "model_calls": 0,
            "retries": 0,
            "immutable_response_captures_replayed": len(route_results),
            "new_source_materials": len(materials),
            "new_evidence_items": len(evidence),
            "evidence_items_before": len(predecessor["evidence_items"]),
            "evidence_items_after": len(successor["evidence_items"]),
            "residual_gaps_before": len(predecessor["residual_gaps"]),
            "residual_gaps_after": len(successor["residual_gaps"]),
            "reused_numeric_facts": len(successor.get("numeric_facts") or ()),
        },
        "stage_acceptance": {
            "historical_source_result_immutable": True,
            "source_refetch_performed": False,
            "arbitrary_regex_allowed": False,
            "bounded_literal_anchor_compiler": True,
            "long_document_mutation_required": True,
            "business_artifact_promoted": False,
            "deepseek_comparison_eligible": core_ready,
        },
        "known_boundary": (
            "A core-ready corrected Evidence Pack permits a separately authorized "
            "changed-input model comparison. It is not itself a report-quality, "
            "valuation, recommendation, Owner-acceptance or release pass."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def validate_dell_bounded_semantic_anchor_clean_proof(
    proof: Mapping[str, Any],
) -> None:
    body = deepcopy(dict(proof))
    digest = str(body.pop("proof_digest", ""))
    counts = dict(proof.get("observed_counts") or {})
    gates = dict(proof.get("gate_status") or {})
    mutations = dict(proof.get("mutations") or {})
    _require(
        proof.get("schema_version") == PROOF_SCHEMA
        and proof.get("contract_ref") == CONTRACT_REF
        and proof.get("status")
        == "clean_independent_bounded_semantic_anchor_replay_passed"
        and digest == canonical_digest(body)
        and proof.get("fresh_worker_count") == 2
        and proof.get("workers_byte_equivalent") is True
        and counts.get("network_calls") == 0
        and counts.get("model_calls") == 0
        and counts.get("new_evidence_items") == 5
        and counts.get("evidence_items_after") == 27
        and counts.get("residual_gaps_after") == 14
        and gates.get("core_research_ready") is True
        and gates.get("supplier_context_ready") is True
        and gates.get("valuation_input_ready") is True
        and mutations
        and all(mutations.values()),
        "bounded_anchor_clean_proof_invalid",
    )


__all__ = [
    "CONTRACT_REF",
    "DellBoundedSemanticAnchorReplayError",
    "POLICY_SCHEMA",
    "PROOF_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "execute_dell_bounded_semantic_anchor_replay",
    "load_dell_bounded_semantic_anchor_replay_policy",
    "validate_dell_bounded_semantic_anchor_clean_proof",
]
