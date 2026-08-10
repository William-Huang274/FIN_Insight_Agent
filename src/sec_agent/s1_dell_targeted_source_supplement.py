from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.official_source_attempt_program import (
    CaptureFirstOfficialSourceClient,
    SourceResponse,
    SourceTransport,
    parse_source_document,
)
from sec_agent.s1_six_case_local_evidence_pack import (
    CASES,
    file_sha256,
    validate_local_evidence_pack,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


POLICY_SCHEMA = "fin_ia_0_1_3_s1_dell_targeted_source_supplement_policy_v1_0"
PROOF_SCHEMA = "fin_ia_0_1_3_s1_dell_targeted_source_supplement_clean_proof_v1_0"
AUTHORITY_SCHEMA = "fin_ia_0_1_3_s1_dell_targeted_source_supplement_authority_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_dell_targeted_source_supplement_result_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.dell_targeted_source_supplement:v1"
RUN_SCOPE = "FIN_0_1_3_S1_DELL_TARGETED_SOURCE_SUPPLEMENT_EXACT_ONCE"
PRIVATE_NAMESPACE = "fin-0.1.3/s1/dell-targeted-source-supplement"
PACK_NAMESPACE = "fin-0.1.3/s1/dell-targeted-source-supplement/packs"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class DellTargetedSourceSupplementError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellTargetedSourceSupplementError(code)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DellTargetedSourceSupplementError(code) from exc
    _require(isinstance(value, dict), code)
    return value


def _resolve(root: Path, ref: str) -> Path:
    value = Path(ref)
    return value.resolve() if value.is_absolute() else (root / value).resolve()


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DellTargetedSourceSupplementError(
            "dell_targeted_source_timestamp_invalid"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_dell_targeted_source_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(
        Path(path), "dell_targeted_source_policy_json_invalid"
    )
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("contract_ref") == CONTRACT_REF
        and policy.get("case_key") == "DELL"
        and policy.get("research_as_of") == "2026-08-06",
        "dell_targeted_source_policy_identity_invalid",
    )
    for key in ("base_pack_result", "local_corpus"):
        binding = dict(policy.get(key) or {})
        source = _resolve(root, str(binding.get("ref") or ""))
        _require(
            source.is_file()
            and _HEX64.fullmatch(str(binding.get("sha256") or "")) is not None
            and file_sha256(source) == str(binding["sha256"]),
            f"dell_targeted_source_policy_binding_invalid:{key}",
        )
    result = _read_json(
        _resolve(root, str(policy["base_pack_result"]["ref"])),
        "dell_targeted_source_base_result_invalid",
    )
    _require(
        result.get("result_digest")
        == policy["base_pack_result"].get("expected_result_digest")
        and set(result.get("pack_artifacts") or {}) == set(CASES),
        "dell_targeted_source_base_result_binding_invalid",
    )
    base_root = _resolve(root, str(policy.get("base_pack_artifact_root") or ""))
    for case_key, reference in result["pack_artifacts"].items():
        source = base_root / str(reference.get("object_key") or "")
        _require(
            source.is_file()
            and file_sha256(source) == str(reference.get("digest") or ""),
            f"dell_targeted_source_base_pack_invalid:{case_key}",
        )
        pack = _read_json(source, "dell_targeted_source_base_pack_json_invalid")
        validate_local_evidence_pack(pack)
        _require(
            pack.get("case_key") == case_key
            and pack.get("pack_payload_digest")
            == (result.get("pack_payload_digests") or {}).get(case_key),
            f"dell_targeted_source_base_pack_binding_invalid:{case_key}",
        )
    local = [dict(row) for row in policy.get("local_source_adjudications") or ()]
    routes = [dict(row) for row in policy.get("external_routes") or ()]
    _require(
        local
        and routes
        and len({row.get("target_id") for row in local}) == len(local)
        and len({row.get("route_id") for row in routes}) == len(routes)
        and int((policy.get("budget") or {}).get("source_network_calls") or 0)
        == len(routes)
        and int((policy.get("budget") or {}).get("model_calls", -1)) == 0
        and int((policy.get("budget") or {}).get("retries", -1)) == 0,
        "dell_targeted_source_policy_population_or_budget_invalid",
    )
    for row in (*local, *routes):
        _require(
            row.get("evidence_owner_ticker")
            and row.get("publication_date")
            and row.get("relationship_directions")
            and (
                row.get("slot_bindings")
                or row.get("fragments")
                or row.get("extractor") == "nasdaq_historical_json"
            ),
            "dell_targeted_source_policy_adjudication_invalid",
        )
    for route in routes:
        parsed = urlsplit(str(route.get("url") or ""))
        allowed = set(route.get("allowed_hosts") or ())
        _require(
            parsed.scheme == "https"
            and (parsed.hostname or "").lower() in allowed
            and route.get("required_for_model_live_gate") in {True, False},
            "dell_targeted_source_policy_route_invalid",
        )
    return policy


def _load_base_packs(
    *, policy: Mapping[str, Any], repo_root: Path
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    result = _read_json(
        _resolve(repo_root, str(policy["base_pack_result"]["ref"])),
        "dell_targeted_source_base_result_invalid",
    )
    root = _resolve(repo_root, str(policy["base_pack_artifact_root"]))
    packs: dict[str, dict[str, Any]] = {}
    for case_key in CASES:
        reference = result["pack_artifacts"][case_key]
        packs[case_key] = _read_json(
            root / str(reference["object_key"]),
            f"dell_targeted_source_base_pack_json_invalid:{case_key}",
        )
        validate_local_evidence_pack(packs[case_key])
    return result, packs


def _load_local_records(
    *, policy: Mapping[str, Any], repo_root: Path
) -> dict[str, dict[str, Any]]:
    wanted = {
        str(row["source_record_id"]): dict(row)
        for row in policy["local_source_adjudications"]
    }
    found: dict[str, dict[str, Any]] = {}
    source = _resolve(repo_root, str(policy["local_corpus"]["ref"]))
    try:
        with source.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                source_id = str(row.get("evidence_id") or "")
                if source_id in wanted:
                    found[source_id] = row
    except (OSError, json.JSONDecodeError) as exc:
        raise DellTargetedSourceSupplementError(
            "dell_targeted_source_local_corpus_invalid"
        ) from exc
    _require(
        set(found) == set(wanted),
        "dell_targeted_source_local_record_missing",
    )
    for source_id, row in found.items():
        spec = wanted[source_id]
        _require(
            str(row.get("ticker") or "") == str(spec["evidence_owner_ticker"])
            and str(row.get("publication_date") or "")
            == str(spec["publication_date"])
            and str(row.get("source_url") or "").startswith("https://"),
            f"dell_targeted_source_local_record_identity_invalid:{source_id}",
        )
    return found


def _extract_fragment(
    text: str,
    *,
    required_patterns: Sequence[str],
    before: int,
    after: int,
    code: str,
) -> str:
    matches: list[re.Match[str]] = []
    for pattern in required_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        _require(match is not None, code)
        matches.append(match)
    start = max(0, min(match.start() for match in matches) - before)
    end = min(len(text), max(match.end() for match in matches) + after)
    while start > 0 and text[start - 1] not in ".!?\n":
        start -= 1
        if min(match.start() for match in matches) - start > before * 2:
            break
    while end < len(text) and text[end - 1] not in ".!?\n":
        end += 1
        if end - max(match.end() for match in matches) > after * 2:
            break
    excerpt = re.sub(r"\s+", " ", text[start:end]).strip()
    _require(
        excerpt and len(excerpt) <= 4000,
        "dell_targeted_source_fragment_size_invalid",
    )
    return excerpt


def _slot_bindings(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    values = [
        {
            "slot_id": str(row["slot_id"]),
            "facet_ids": [str(value) for value in row.get("facet_ids") or ()],
            "business_meaning_zh": str(row.get("business_meaning_zh") or ""),
            "claim_boundary_zh": str(row.get("claim_boundary_zh") or ""),
        }
        for row in rows
    ]
    _require(
        values
        and all(
            row["slot_id"]
            and row["facet_ids"]
            and row["business_meaning_zh"]
            and row["claim_boundary_zh"]
            for row in values
        ),
        "dell_targeted_source_slot_binding_invalid",
    )
    return values


def _compile_material_and_evidence(
    *,
    spec: Mapping[str, Any],
    source_record_id: str,
    source_text: str,
    source_url: str,
    source_type: str,
    source_tier: str,
    period_end: str,
    source_lineage: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    text_digest = _sha256_text(source_text)
    material_ref = "source_material_" + text_digest[:24]
    material = {
        "material_ref": material_ref,
        "source_record_id": source_record_id,
        "source_text": source_text,
        "source_text_digest": text_digest,
        "source_url": source_url,
        "source_type": source_type,
        "source_tier": source_tier,
        "evidence_owner_ticker": str(spec["evidence_owner_ticker"]),
        "publication_date": str(spec["publication_date"]),
        "period_end": period_end,
        "license_scope": "public_official_source_research_use",
        "redistributable": False,
        "source_lineage": deepcopy(dict(source_lineage)),
    }
    owner = str(spec["evidence_owner_ticker"])
    role = str(spec.get("evidence_role") or "")
    if role == "independent_market_point_in_time":
        disposition = "accepted_independent_market_evidence"
        evidence_role = role
    elif owner == "DELL":
        disposition = "accepted_direct_source_evidence"
        evidence_role = "issuer_direct_source"
    else:
        disposition = "accepted_bounded_context_evidence"
        evidence_role = "counterparty_or_ecosystem_readthrough"
    body = {
        "case_key": "DELL",
        "target_id": str(spec["target_id"]),
        "source_record_id": source_record_id,
        "source_material_ref": material_ref,
        "source_content_digest": text_digest,
        "object_type": "source_segment",
        "disposition": disposition,
        "evidence_role": evidence_role,
        "slot_bindings": _slot_bindings(spec.get("slot_bindings") or ()),
        "publication_date": str(spec["publication_date"]),
        "source_reporting_period_end": period_end,
        "research_as_of": "2026-08-06",
        "relationship_directions": [
            str(value) for value in spec.get("relationship_directions") or ()
        ],
        "writer_citable": True,
        "numeric_use_boundary": (
            "Only exact values visible in this bounded source excerpt may be quoted; "
            "derived arithmetic requires the signed deterministic numeric authority."
        ),
        "causal_attribution_authorized": False,
    }
    return material, {**body, "evidence_item_digest": canonical_digest(body)}


def _compile_local_supplements(
    *, policy: Mapping[str, Any], records: Mapping[str, Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    materials: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for spec in policy["local_source_adjudications"]:
        row = records[str(spec["source_record_id"])]
        excerpt = _extract_fragment(
            str(row.get("text") or ""),
            required_patterns=[str(value) for value in spec["required_patterns"]],
            before=int(spec.get("excerpt_before") or 100),
            after=int(spec.get("excerpt_after") or 500),
            code=(
                "dell_targeted_source_local_anchor_missing:"
                + str(spec["source_record_id"])
            ),
        )
        material, item = _compile_material_and_evidence(
            spec=spec,
            source_record_id=str(spec["source_record_id"]),
            source_text=excerpt,
            source_url=str(row.get("source_url") or ""),
            source_type=str(row.get("source_type") or ""),
            source_tier="primary_sec_filing",
            period_end=str(row.get("period_end") or ""),
            source_lineage={
                "lineage_kind": "bound_local_corpus_exact_excerpt",
                "corpus_ref": str(policy["local_corpus"]["ref"]),
                "corpus_sha256": str(policy["local_corpus"]["sha256"]),
                "full_source_text_sha256": _sha256_text(str(row.get("text") or "")),
                "selection_rule_id": str(spec["target_id"]),
            },
        )
        materials.append(material)
        evidence.append(item)
    return materials, evidence


def _find_nasdaq_row(payload: Any, target_date: str) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        if str(payload.get("date") or "") == target_date and "close" in payload:
            return dict(payload)
        for value in payload.values():
            found = _find_nasdaq_row(value, target_date)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _find_nasdaq_row(value, target_date)
            if found is not None:
                return found
    return None


def _compile_external_route(
    *,
    route: Mapping[str, Any],
    response: SourceResponse | None,
    attempt: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    public_attempt = {
        "route_id": str(route["route_id"]),
        "status": str(attempt.get("status") or ""),
        "failure_code": str(attempt.get("failure_code") or ""),
        "request_capture": deepcopy(dict(attempt.get("request_capture") or {})),
        "response_capture": deepcopy(dict(attempt.get("response_capture") or {})),
        "fragments_expected": (
            1
            if route.get("extractor") == "nasdaq_historical_json"
            else len(route.get("fragments") or ())
        ),
        "fragments_materialized": 0,
    }
    if response is None or attempt.get("status") != "captured":
        return [], [], public_attempt
    response_capture = dict(attempt["response_capture"])
    materials: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    if route.get("extractor") == "nasdaq_historical_json":
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            public_attempt["status"] = "parser_failure"
            public_attempt["failure_code"] = "nasdaq_historical_json_invalid"
            return [], [], public_attempt
        market = dict(route["market_point"])
        row = _find_nasdaq_row(payload, str(market["provider_date_value"]))
        if row is None or str(row.get("close") or "") != str(market["close_token"]):
            public_attempt["status"] = "anchor_failure"
            public_attempt["failure_code"] = "nasdaq_historical_target_row_missing"
            return [], [], public_attempt
        source_text = json.dumps(row, ensure_ascii=False, sort_keys=True)
        material, item = _compile_material_and_evidence(
            spec={**route, **market},
            source_record_id=str(market["source_record_id"]),
            source_text=source_text,
            source_url=response.final_url,
            source_type=str(route["source_type"]),
            source_tier=str(route["source_tier"]),
            period_end=str(market["period_end"]),
            source_lineage={
                "lineage_kind": "capture_first_official_market_json_row",
                "response_capture_ref": response_capture["object_key"],
                "response_capture_digest": response_capture["digest"],
                "response_body_sha256": response_capture.get("body_sha256"),
                "selection_rule_id": str(market["target_id"]),
            },
        )
        materials.append(material)
        evidence.append(item)
    else:
        parsed = parse_source_document(response)
        if parsed.get("status") != "parsed":
            public_attempt["status"] = "parser_failure"
            public_attempt["failure_code"] = "official_source_all_parsers_failed"
            return [], [], public_attempt
        for fragment in route.get("fragments") or ():
            try:
                excerpt = _extract_fragment(
                    str(parsed["text"]),
                    required_patterns=[
                        str(value) for value in fragment["required_patterns"]
                    ],
                    before=int(fragment.get("excerpt_before") or 120),
                    after=int(fragment.get("excerpt_after") or 500),
                    code=(
                        "dell_targeted_source_external_anchor_missing:"
                        + str(fragment["target_id"])
                    ),
                )
            except DellTargetedSourceSupplementError as exc:
                public_attempt["status"] = "anchor_failure"
                public_attempt["failure_code"] = exc.code
                continue
            spec = {**route, **dict(fragment)}
            material, item = _compile_material_and_evidence(
                spec=spec,
                source_record_id=(
                    str(route["route_id"]) + "::" + str(fragment["fragment_id"])
                ),
                source_text=excerpt,
                source_url=response.final_url,
                source_type=str(route["source_type"]),
                source_tier=str(route["source_tier"]),
                period_end=str(route.get("period_end") or ""),
                source_lineage={
                    "lineage_kind": "capture_first_official_document_exact_excerpt",
                    "response_capture_ref": response_capture["object_key"],
                    "response_capture_digest": response_capture["digest"],
                    "response_body_sha256": response_capture.get("body_sha256"),
                    "parsed_text_sha256": parsed.get("text_sha256"),
                    "parser_adapter": parsed.get("adapter"),
                    "selection_rule_id": str(fragment["target_id"]),
                },
            )
            materials.append(material)
            evidence.append(item)
    public_attempt["fragments_materialized"] = len(evidence)
    if len(evidence) == int(public_attempt["fragments_expected"]):
        public_attempt["status"] = "captured_parsed_and_adjudicated"
        public_attempt["failure_code"] = ""
    return materials, evidence, public_attempt


def _successor_dell_pack(
    *,
    base_pack: Mapping[str, Any],
    source_materials: Sequence[Mapping[str, Any]],
    evidence_items: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    route_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    body = deepcopy(dict(base_pack))
    body.pop("pack_payload_digest", None)
    materials = [deepcopy(dict(row)) for row in body["source_materials"]]
    evidence = [deepcopy(dict(row)) for row in body["evidence_items"]]
    material_index = {str(row["material_ref"]): row for row in materials}
    target_ids = {str(row["target_id"]) for row in evidence}
    for row in source_materials:
        value = deepcopy(dict(row))
        material_ref = str(value["material_ref"])
        if material_ref in material_index:
            existing = material_index[material_ref]
            _require(
                existing.get("source_text_digest")
                == value.get("source_text_digest")
                and existing.get("source_url") == value.get("source_url"),
                "dell_targeted_source_material_collision",
            )
            continue
        material_index[material_ref] = value
        materials.append(value)
    for row in evidence_items:
        value = deepcopy(dict(row))
        _require(
            str(value["target_id"]) not in target_ids,
            "dell_targeted_source_evidence_collision",
        )
        target_ids.add(str(value["target_id"]))
        evidence.append(value)
    disposition = dict(policy.get("gap_disposition") or {})
    removal_rules = [
        deepcopy(dict(row)) for row in disposition.get("remove_gaps") or ()
    ]
    present_targets = {str(row.get("target_id") or "") for row in evidence_items}
    removals = {
        str(row["gap_id"])
        for row in removal_rules
        if set(str(value) for value in row.get("requires_target_ids") or ())
        <= present_targets
    }
    replacements = {
        str(row["gap_id"]): deepcopy(dict(row))
        for row in disposition.get("replace_gaps") or ()
    }
    gaps: list[dict[str, Any]] = []
    for row in base_pack.get("residual_gaps") or ():
        gap_id = str(row.get("gap_id") or "")
        if gap_id in removals:
            continue
        gaps.append(replacements.pop(gap_id, deepcopy(dict(row))))
    _require(
        not replacements,
        "dell_targeted_source_gap_replacement_target_missing",
    )
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
                "reviewed_local_pack_plus_capture_first_targeted_official_supplement"
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
            },
            "supplement_lineage": {
                "contract_ref": CONTRACT_REF,
                "base_pack_payload_digest": base_pack["pack_payload_digest"],
                "local_corpus_sha256": policy["local_corpus"]["sha256"],
                "route_results": [deepcopy(dict(row)) for row in route_results],
                "gap_ids_removed_as_satisfied": sorted(removals),
                "gap_ids_not_removed_due_missing_evidence": sorted(
                    str(row["gap_id"])
                    for row in removal_rules
                    if str(row["gap_id"]) not in removals
                ),
                "gap_ids_narrowed": sorted(
                    str(row["gap_id"])
                    for row in disposition.get("replace_gaps") or ()
                ),
            },
            "known_boundary": (
                "This successor Evidence Pack adds bounded issuer, customer, competitor, "
                "supplier and market point-in-time evidence. Counterparty evidence remains "
                "read-through only and does not prove Dell-specific allocation, causality or "
                "a complete investment conclusion."
            ),
        }
    )
    successor = {**body, "pack_payload_digest": canonical_digest(body)}
    validate_local_evidence_pack(successor)
    return successor


def validate_dell_targeted_source_authority(
    authority: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    observed_at: str,
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
        and _HEX64.fullmatch(str(authority.get("clean_proof_digest") or ""))
        is not None
        and re.fullmatch(
            r"[0-9a-f]{40}", str(authority.get("implementation_commit") or "")
        )
        is not None,
        "dell_targeted_source_authority_identity_invalid",
    )
    _require(
        _utc(str(authority["issued_at"]))
        <= _utc(observed_at)
        <= _utc(str(authority["expires_at"]))
        and authority.get("maximum_executions") == 1
        and authority.get("automatic_retry") is False
        and authority.get("business_artifact_promotion") is False
        and authority.get("model_calls_allowed") == 0
        and authority.get("evidence_promotion_mode")
        == "local_deterministic_adjudication_only"
        and authority.get("budget") == policy.get("budget"),
        "dell_targeted_source_authority_boundary_invalid",
    )
    root = Path(repo_root).resolve()
    for ref, expected in (authority.get("file_bindings") or {}).items():
        path = _resolve(root, str(ref))
        _require(
            path.is_file() and file_sha256(path) == str(expected),
            "dell_targeted_source_authority_file_binding_invalid",
        )


def validate_dell_targeted_source_clean_proof(
    proof: Mapping[str, Any],
) -> None:
    body = deepcopy(dict(proof))
    digest = str(body.pop("proof_digest", ""))
    counts = dict(proof.get("observed_counts") or {})
    _require(
        proof.get("schema_version") == PROOF_SCHEMA
        and proof.get("status")
        == "clean_independent_dell_targeted_source_zero_call_proof_passed"
        and digest == canonical_digest(body)
        and proof.get("fresh_worker_count") == 2
        and proof.get("workers_byte_equivalent") is True
        and counts.get("network_calls") == 0
        and counts.get("provider_calls") == 0
        and counts.get("model_calls") == 0
        and counts.get("new_dell_evidence_items") == 12
        and counts.get("dell_evidence_items_after") == 27
        and counts.get("dell_residual_gaps_after") == 14,
        "dell_targeted_source_clean_proof_invalid",
    )


def execute_dell_targeted_source_supplement(
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
        not runtime.exists(), "dell_targeted_source_runtime_already_exists"
    )
    if transport.live_network:
        _require(
            authority is not None and shared_admission_ledger is not None,
            "dell_targeted_source_live_authority_required",
        )
        validate_dell_targeted_source_authority(
            authority,
            policy=policy,
            repo_root=root,
            observed_at=observed_at,
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
    client = CaptureFirstOfficialSourceClient(
        store=store,
        transport=transport,
        namespace=PRIVATE_NAMESPACE,
    )
    local_records = _load_local_records(policy=policy, repo_root=root)
    local_materials, local_evidence = _compile_local_supplements(
        policy=policy, records=local_records
    )
    external_materials: list[dict[str, Any]] = []
    external_evidence: list[dict[str, Any]] = []
    route_results: list[dict[str, Any]] = []
    for route in policy["external_routes"]:
        response, attempt = client.fetch(
            case_key="DELL",
            route_id=str(route["route_id"]),
            url=str(route["url"]),
            allowed_hosts=set(route["allowed_hosts"]),
            timeout_seconds=int(policy["budget"]["timeout_seconds_per_route"]),
            byte_ceiling=int(route["byte_ceiling"]),
        )
        materials, evidence, public_attempt = _compile_external_route(
            route=route,
            response=response,
            attempt=attempt,
        )
        external_materials.extend(materials)
        external_evidence.extend(evidence)
        public_attempt["required_for_model_live_gate"] = bool(
            route["required_for_model_live_gate"]
        )
        route_results.append(public_attempt)
    _require(
        client.network_calls
        == int(policy["budget"]["source_network_calls"])
        if transport.live_network
        else client.network_calls == 0,
        "dell_targeted_source_network_call_count_invalid",
    )
    base_result, base_packs = _load_base_packs(policy=policy, repo_root=root)
    dell = _successor_dell_pack(
        base_pack=base_packs["DELL"],
        source_materials=[*local_materials, *external_materials],
        evidence_items=[*local_evidence, *external_evidence],
        policy=policy,
        route_results=route_results,
    )
    successor_packs = {**base_packs, "DELL": dell}
    pack_artifacts: dict[str, dict[str, Any]] = {}
    for case_key in CASES:
        pack_artifacts[case_key] = store.put_json(
            successor_packs[case_key],
            namespace=f"{PACK_NAMESPACE}/{case_key.lower()}/v1",
            artifact_type=(
                "targeted_source_supplemented_local_evidence_pack"
                if case_key == "DELL"
                else "immutable_base_local_evidence_pack_copy"
            ),
        )
    required_routes = [
        row
        for row in route_results
        if row.get("required_for_model_live_gate") is True
    ]
    required_routes_pass = bool(required_routes) and all(
        row.get("status") == "captured_parsed_and_adjudicated"
        for row in required_routes
    )
    expected_external_fragments = sum(
        1
        if route.get("extractor") == "nasdaq_historical_json"
        else len(route.get("fragments") or ())
        for route in policy["external_routes"]
    )
    all_external_fragments = len(external_evidence) == expected_external_fragments
    ready = required_routes_pass and all_external_fragments
    status = (
        "terminal_succeeded_targeted_source_successor_pack_ready"
        if ready
        else "terminal_completed_targeted_source_successor_pack_with_typed_gaps"
    )
    public_body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "recorded_at": observed_at,
        "status": status,
        "source_commit": execution_commit,
        "attempt_id": (
            str(authority["attempt_id"])
            if authority is not None
            else "zero_call_fixture"
        ),
        "research_as_of": str(policy["research_as_of"]),
        "policy_digest": canonical_digest(policy),
        "base_pack_result_digest": base_result["result_digest"],
        "pack_payload_digests": {
            case_key: successor_packs[case_key]["pack_payload_digest"]
            for case_key in CASES
        },
        "pack_artifacts": pack_artifacts,
        "case_summaries": [
            {
                "case_key": case_key,
                **deepcopy(dict(successor_packs[case_key]["observed_counts"])),
            }
            for case_key in CASES
        ],
        "route_results": route_results,
        "observed_counts": {
            "local_source_records_adjudicated": len(local_evidence),
            "external_source_fragments_expected": expected_external_fragments,
            "external_source_fragments_adjudicated": len(external_evidence),
            "new_dell_evidence_items": len(local_evidence) + len(external_evidence),
            "dell_evidence_items_before": len(base_packs["DELL"]["evidence_items"]),
            "dell_evidence_items_after": len(dell["evidence_items"]),
            "dell_residual_gaps_before": len(base_packs["DELL"]["residual_gaps"]),
            "dell_residual_gaps_after": len(dell["residual_gaps"]),
            "network_calls": client.network_calls,
            "provider_calls": 0,
            "model_calls": 0,
            "retries": 0,
        },
        "stage_acceptance": {
            "capture_first": True,
            "all_required_routes_adjudicated": required_routes_pass,
            "all_planned_external_fragments_adjudicated": all_external_fragments,
            "counterparty_claim_boundaries_preserved": True,
            "market_point_in_time_source_bound": any(
                row.get("evidence_role") == "independent_market_point_in_time"
                for row in external_evidence
            ),
            "successor_pack_ready_for_zero_call_input_compilation": ready,
            "deepseek_exact_live_authorized": False,
            "business_artifact_promoted": False,
        },
        "known_boundary": (
            "This exact-once source run materializes a DELL successor Evidence Pack. "
            "It does not prove report quality, Dell-specific supplier allocation, target "
            "price, recommendation, or product promotion."
        ),
    }
    result = {**public_body, "result_digest": canonical_digest(public_body)}
    if transport.live_network and authority is not None and shared_admission_ledger is not None:
        terminal_code = (
            "targeted_source_successor_pack_ready"
            if ready
            else "targeted_source_successor_pack_completed_with_typed_gaps"
        )
        shared_admission_ledger.finalize(
            admission_digest=str(authority["authority_digest"]),
            run_id=str(authority["run_id"]),
            attempt_id=str(authority["attempt_id"]),
            terminal_status=("success" if ready else "completed_with_gaps"),
            terminal_phase="targeted_source_supplement_terminal",
            terminal_code=terminal_code,
            terminal_result_digest=result["result_digest"],
            finalized_at=observed_at,
        )
    return result


__all__ = [
    "AUTHORITY_SCHEMA",
    "CONTRACT_REF",
    "DellTargetedSourceSupplementError",
    "POLICY_SCHEMA",
    "PROOF_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "execute_dell_targeted_source_supplement",
    "load_dell_targeted_source_policy",
    "validate_dell_targeted_source_authority",
    "validate_dell_targeted_source_clean_proof",
]
