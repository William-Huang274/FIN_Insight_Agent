from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .reviewed_evidence_pack import canonical_digest


CLAIM_AUTHORITY_POLICY_SCHEMA_VERSION = "fin_ia_claim_authority_policy_v1_0"
CLAIM_AUTHORITY_DYNAMIC_POLICY_SCHEMA_VERSION = (
    "fin_ia_claim_authority_policy_v1_1"
)
CLAIM_AUTHORITY_INPUT_SCHEMA_VERSION = "fin_ia_current_research_input_v1_2"
CLAIM_AUTHORITY_DYNAMIC_INPUT_SCHEMA_VERSION = (
    "fin_ia_dynamic_current_research_input_v1_1"
)
CLAIM_AUTHORITY_JUDGMENT_SCHEMA_VERSION = (
    "fin_ia_current_research_judgment_payload_v1_3"
)
CLAIM_AUTHORITY_DELIVERABLE_SCHEMA_VERSION = (
    "fin_ia_current_research_deliverable_v1_3"
)
CLAIM_AUTHORITY_MODEL_FIELDS = (
    "claim_scope",
    "financial_scope",
    "causal_bridge_authority",
)


class ClaimAuthorityError(ValueError):
    """Fail-closed error for the model-owned claim-scope declaration."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ClaimAuthorityError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _strings(value: object, code: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list), code)
    rows = tuple(str(row).strip() for row in value)
    _require(
        (allow_empty or bool(rows))
        and all(rows)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


def load_claim_authority_policy(payload: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version",
        "status",
        "qualified_scope",
        "allowed_claim_scopes",
        "allowed_financial_scopes",
        "allowed_causal_bridge_authorities",
        "allowed_combinations",
        "evidence_bindings",
        "bridge_gap_refs",
        "cross_scope_language_guard",
        "authority",
    }
    _require(set(payload) == expected, "claim_authority_policy_fields_invalid")
    schema_version = str(payload.get("schema_version") or "")
    dynamic_mode = schema_version == CLAIM_AUTHORITY_DYNAMIC_POLICY_SCHEMA_VERSION
    _require(
        (
            schema_version == CLAIM_AUTHORITY_POLICY_SCHEMA_VERSION
            and payload.get("status")
            == "provider_neutral_fixed_pack_claim_authority"
        )
        or (
            dynamic_mode
            and payload.get("status")
            == "provider_neutral_dynamic_request_claim_authority"
        ),
        "claim_authority_policy_status_invalid",
    )
    qualified = _mapping(
        payload.get("qualified_scope"), "claim_authority_qualified_scope_invalid"
    )
    _require(
        set(qualified)
        == {
            "case_key",
            "cell_id",
            "base_research_input_digest",
            "base_judgment_schema_version",
        }
        and str(qualified.get("case_key") or "").strip().upper()
        and str(qualified.get("cell_id") or "").startswith("CELL::")
        and len(str(qualified.get("base_research_input_digest") or "")) == 64
        and qualified.get("base_judgment_schema_version")
        == "fin_ia_current_research_judgment_payload_v1_2",
        "claim_authority_qualified_scope_invalid",
    )
    claim_scopes = _strings(
        payload.get("allowed_claim_scopes"), "claim_authority_claim_scopes_invalid"
    )
    financial_scopes = _strings(
        payload.get("allowed_financial_scopes"),
        "claim_authority_financial_scopes_invalid",
    )
    bridge_authorities = _strings(
        payload.get("allowed_causal_bridge_authorities"),
        "claim_authority_bridge_authorities_invalid",
    )
    _require(
        "direct_cross_scope_bridge" not in bridge_authorities,
        "claim_authority_unavailable_direct_bridge_exposed",
    )
    combinations = payload.get("allowed_combinations")
    _require(
        isinstance(combinations, list) and bool(combinations),
        "claim_authority_combinations_invalid",
    )
    normalized_combinations = []
    seen_combinations: set[tuple[str, str, str]] = set()
    for raw in combinations:
        row = _mapping(raw, "claim_authority_combination_invalid")
        _require(
            set(row)
            == {
                "claim_scope",
                "financial_scope",
                "causal_bridge_authority",
                "allowed_inference_authorities",
                "allowed_judgment_statuses",
            },
            "claim_authority_combination_invalid",
        )
        key = (
            str(row.get("claim_scope") or ""),
            str(row.get("financial_scope") or ""),
            str(row.get("causal_bridge_authority") or ""),
        )
        inference = _strings(
            row.get("allowed_inference_authorities"),
            "claim_authority_combination_invalid",
        )
        statuses = _strings(
            row.get("allowed_judgment_statuses"),
            "claim_authority_combination_invalid",
        )
        _require(
            key[0] in claim_scopes
            and key[1] in financial_scopes
            and key[2] in bridge_authorities
            and key not in seen_combinations,
            "claim_authority_combination_invalid",
        )
        seen_combinations.add(key)
        normalized_combinations.append(
            {
                "claim_scope": key[0],
                "financial_scope": key[1],
                "causal_bridge_authority": key[2],
                "allowed_inference_authorities": list(inference),
                "allowed_judgment_statuses": list(statuses),
            }
        )
    bindings = _mapping(
        payload.get("evidence_bindings"), "claim_authority_evidence_bindings_invalid"
    )
    _require(
        set(bindings)
        == {
            "management_assertion_evidence_refs",
            "multi_driver_context_evidence_refs",
            "limiting_evidence_refs",
        },
        "claim_authority_evidence_bindings_invalid",
    )
    normalized_bindings = {
        key: list(
            _strings(
                bindings.get(key),
                "claim_authority_evidence_bindings_invalid",
                allow_empty=dynamic_mode,
            )
        )
        for key in bindings
    }
    gap_refs = _strings(
        payload.get("bridge_gap_refs"),
        "claim_authority_bridge_gaps_invalid",
        allow_empty=dynamic_mode,
    )
    guard = _mapping(
        payload.get("cross_scope_language_guard"),
        "claim_authority_language_guard_invalid",
    )
    _require(
        set(guard)
        == {
            "subject_terms",
            "financial_outcome_terms",
            "causal_terms",
            "management_attribution_terms",
        },
        "claim_authority_language_guard_invalid",
    )
    normalized_guard = {
        key: list(
            _strings(guard.get(key), "claim_authority_language_guard_invalid")
        )
        for key in guard
    }
    authority = _mapping(
        payload.get("authority"), "claim_authority_policy_authority_invalid"
    )
    expected_authority = {
            "model_owns_narrative_judgment": True,
            "model_must_declare_claim_and_financial_scope": True,
            "model_must_select_only_compiled_bridge_authority": True,
            "harness_may_validate_but_not_invent_causal_claim": True,
            "fixed_pack_test_is_not_agentic_research": True,
            "qualified_human_content_review_required": True,
        }
    if dynamic_mode:
        expected_authority = {
            **expected_authority,
            "dynamic_request_scoped_reselection": True,
            "candidate_promotion_forbidden": True,
        }
    _require(
        dict(authority) == expected_authority,
        "claim_authority_policy_authority_invalid",
    )
    return {
        **deepcopy(dict(payload)),
        "qualified_scope": deepcopy(dict(qualified)),
        "allowed_claim_scopes": list(claim_scopes),
        "allowed_financial_scopes": list(financial_scopes),
        "allowed_causal_bridge_authorities": list(bridge_authorities),
        "allowed_combinations": normalized_combinations,
        "evidence_bindings": normalized_bindings,
        "bridge_gap_refs": list(gap_refs),
        "cross_scope_language_guard": normalized_guard,
        "authority": deepcopy(dict(authority)),
    }


def compile_claim_authority_research_input(
    research_input: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Overlay a fixed-pack claim authority without mutating the v1.2 input."""

    loaded = load_claim_authority_policy(policy)
    qualified = loaded["qualified_scope"]
    dynamic_mode = (
        loaded["schema_version"] == CLAIM_AUTHORITY_DYNAMIC_POLICY_SCHEMA_VERSION
    )
    _require(
        research_input.get("schema_version")
        == (
            "fin_ia_dynamic_current_research_input_v1_0"
            if dynamic_mode
            else "fin_ia_current_research_input_v1_1"
        )
        and research_input.get("research_input_digest")
        == qualified["base_research_input_digest"]
        and research_input.get("model_output_contract", {}).get(
            "payload_schema_version"
        )
        == qualified["base_judgment_schema_version"]
        and research_input.get("case_identity", {}).get("case_key")
        == qualified["case_key"],
        "claim_authority_base_input_not_qualified",
    )
    cells = {
        str(row.get("cell_id") or ""): row
        for row in research_input.get("cells") or ()
        if isinstance(row, Mapping)
    }
    cell_id = str(qualified["cell_id"])
    _require(cell_id in cells, "claim_authority_cell_not_qualified")
    cell = cells[cell_id]
    allowed_evidence = set(cell.get("allowed_evidence_refs") or ())
    allowed_gaps = set(cell.get("visible_gap_refs") or ())
    bound_evidence = {
        ref
        for refs in loaded["evidence_bindings"].values()
        for ref in refs
    }
    _require(
        bound_evidence.issubset(allowed_evidence),
        "claim_authority_bound_evidence_drift",
    )
    _require(
        set(loaded["bridge_gap_refs"]).issubset(allowed_gaps),
        "claim_authority_bound_gap_drift",
    )
    card_body = {
        "card_schema_version": "fin_ia_claim_authority_card_v1_0",
        "case_key": qualified["case_key"],
        "cell_id": cell_id,
        "allowed_claim_scopes": deepcopy(loaded["allowed_claim_scopes"]),
        "allowed_financial_scopes": deepcopy(
            loaded["allowed_financial_scopes"]
        ),
        "allowed_causal_bridge_authorities": deepcopy(
            loaded["allowed_causal_bridge_authorities"]
        ),
        "allowed_combinations": deepcopy(loaded["allowed_combinations"]),
        "evidence_bindings": deepcopy(loaded["evidence_bindings"]),
        "bridge_gap_refs": deepcopy(loaded["bridge_gap_refs"]),
        "rules": [
            "Choose the narrowest claim and financial scope that the selected refs actually support.",
            "A management assertion proves only that management made the bounded statement; it is not an audited product-to-company bridge.",
            "Multi-driver context permits coexistence and bounded interpretation, not allocation of company or segment profit to one product.",
            "When the bridge is unavailable, preserve the typed gaps and abstain from the cross-scope causal claim.",
            "The harness validates authority only; it does not write the thesis, mechanism, counterargument or what-would-change for the model.",
        ],
    }
    card = {**card_body, "card_digest": canonical_digest(card_body)}
    unsigned = deepcopy(dict(research_input))
    unsigned.pop("research_input_digest", None)
    unsigned["schema_version"] = (
        CLAIM_AUTHORITY_DYNAMIC_INPUT_SCHEMA_VERSION
        if dynamic_mode
        else CLAIM_AUTHORITY_INPUT_SCHEMA_VERSION
    )
    for row in unsigned["cells"]:
        if row["cell_id"] == cell_id:
            row["claim_authority_card"] = deepcopy(card)
    output = unsigned["model_output_contract"]
    output["payload_schema_version"] = CLAIM_AUTHORITY_JUDGMENT_SCHEMA_VERSION
    output["model_owned_cell_fields"] = [
        *output["model_owned_cell_fields"],
        *CLAIM_AUTHORITY_MODEL_FIELDS,
    ]
    output["harness_injected_cell_fields"] = [
        *output["harness_injected_cell_fields"],
        "claim_authority_receipt",
    ]
    output["allowed_claim_scopes"] = deepcopy(loaded["allowed_claim_scopes"])
    output["allowed_financial_scopes"] = deepcopy(
        loaded["allowed_financial_scopes"]
    )
    output["allowed_causal_bridge_authorities"] = deepcopy(
        loaded["allowed_causal_bridge_authorities"]
    )
    unsigned["claim_authority_contract"] = {
        "policy_schema_version": loaded["schema_version"],
        "policy_digest": canonical_digest(loaded),
        "qualified_case_key": qualified["case_key"],
        "qualified_cell_ids": [cell_id],
        "base_research_input_digest": qualified["base_research_input_digest"],
        "fixed_pack_unit_test_only": not dynamic_mode,
        "dynamic_retrieval_executed": dynamic_mode,
        "agentic_research_claimed": False,
        **(
            {
                "qualification_mode": (
                    "dynamic_request_scoped_reviewed_evidence"
                ),
                "candidate_promotions": 0,
            }
            if dynamic_mode
            else {}
        ),
        "authority": deepcopy(loaded["authority"]),
        "cross_scope_language_guard": deepcopy(
            loaded["cross_scope_language_guard"]
        ),
    }
    return {**unsigned, "research_input_digest": canonical_digest(unsigned)}


def validate_claim_authority_selection(
    raw: Mapping[str, Any],
    *,
    claim_authority_card: Mapping[str, Any],
    claim_authority_contract: Mapping[str, Any],
    evidence_uses: Sequence[Mapping[str, str]],
    numeric_refs: Sequence[str],
    numeric_relation_refs: Sequence[str] = (),
    remaining_gap_refs: Sequence[str],
    inference_authority: str,
    judgment_status: str,
    narrative_atoms: Sequence[str],
    structured_claim_relation_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    claim_scope = str(raw.get("claim_scope") or "")
    financial_scope = str(raw.get("financial_scope") or "")
    bridge = str(raw.get("causal_bridge_authority") or "")
    _require(
        claim_scope in set(claim_authority_card["allowed_claim_scopes"])
        and financial_scope
        in set(claim_authority_card["allowed_financial_scopes"])
        and bridge
        in set(claim_authority_card["allowed_causal_bridge_authorities"]),
        "claim_authority_output_enum_invalid",
    )
    combination = next(
        (
            row
            for row in claim_authority_card["allowed_combinations"]
            if row["claim_scope"] == claim_scope
            and row["financial_scope"] == financial_scope
            and row["causal_bridge_authority"] == bridge
        ),
        None,
    )
    _require(
        combination is not None
        and inference_authority
        in set(combination["allowed_inference_authorities"])
        and judgment_status in set(combination["allowed_judgment_statuses"]),
        "claim_authority_scope_combination_invalid",
    )
    roles_by_ref: dict[str, set[str]] = {}
    for row in evidence_uses:
        roles_by_ref.setdefault(str(row["evidence_ref"]), set()).add(
            str(row["use_role"])
        )
    bindings = claim_authority_card["evidence_bindings"]
    claim_local_limit = False
    typed_bridge_gap_boundary = False
    typed_same_scope_counter_boundary = False
    if bridge == "management_assertion_only":
        _require(
            any(
                "support" in roles_by_ref.get(ref, set())
                for ref in bindings["management_assertion_evidence_refs"]
            ),
            "claim_authority_management_assertion_evidence_missing",
        )
        combined = " ".join(narrative_atoms).casefold()
        attribution = claim_authority_contract["cross_scope_language_guard"][
            "management_attribution_terms"
        ]
        _require(
            any(term.casefold() in combined for term in attribution),
            "claim_authority_management_attribution_missing",
        )
    if bridge == "multi_driver_context_only":
        structured_relations = (
            structured_claim_relation_receipt.get("claim_relations", ())
            if structured_claim_relation_receipt is not None
            else ()
        )
        claim_local_limit = any(
            str(use.get("use_role") or "") == "limit"
            and str(use.get("evidence_ref") or "")
            in set(bindings["limiting_evidence_refs"])
            for relation in structured_relations
            if isinstance(relation, Mapping)
            for use in relation.get("evidence_uses", ())
            if isinstance(use, Mapping)
        )
        typed_bridge_gap_boundary = (
            set(claim_authority_card["bridge_gap_refs"]).issubset(
                remaining_gap_refs
            )
            and any(
                isinstance(relation, Mapping)
                and relation.get("claim_relation")
                == "bridge_not_established"
                for relation in structured_relations
            )
        )
        typed_same_scope_counter_boundary = (
            bool(numeric_relation_refs)
            and any(
                isinstance(relation, Mapping)
                and relation.get("atom_field") == "counterargument_atom"
                and relation.get("claim_relation")
                == "same_scope_numeric_observation"
                for relation in structured_relations
            )
        )
        _require(
            any(
                bool(
                    roles_by_ref.get(ref, set())
                    & {"support", "context"}
                )
                for ref in bindings["multi_driver_context_evidence_refs"]
            )
            and (
                any(
                    "limit" in roles_by_ref.get(ref, set())
                    for ref in bindings["limiting_evidence_refs"]
                )
                or claim_local_limit
                or typed_bridge_gap_boundary
                or typed_same_scope_counter_boundary
            ),
            "claim_authority_multi_driver_boundary_missing",
        )
    if bridge == "bridge_unavailable":
        _require(
            inference_authority == "not_inferable"
            and judgment_status == "insufficient_evidence"
            and set(claim_authority_card["bridge_gap_refs"]).issubset(
                remaining_gap_refs
            ),
            "claim_authority_unavailable_bridge_without_abstention",
        )
    if bridge == "same_scope_observation_only":
        _require(
            bool(numeric_refs),
            "claim_authority_same_scope_without_numeric_fact",
        )
    combined = " ".join(narrative_atoms).casefold()
    guard = claim_authority_contract["cross_scope_language_guard"]
    has_subject = any(
        term.casefold() in combined for term in guard["subject_terms"]
    )
    has_financial = any(
        term.casefold() in combined for term in guard["financial_outcome_terms"]
    )
    has_causal = any(
        term.casefold() in combined for term in guard["causal_terms"]
    )
    lexical_risk_detected = has_subject and has_financial and has_causal
    if structured_claim_relation_receipt is None:
        _require(
            not lexical_risk_detected,
            "claim_authority_cross_scope_causal_language_unbound",
        )
    else:
        _require(
            structured_claim_relation_receipt.get(
                "structured_claim_relation_primary"
            )
            is True
            and structured_claim_relation_receipt.get(
                "narrative_conflict_guard_pass"
            )
            is True,
            "claim_authority_structured_relation_receipt_invalid",
        )
    receipt = {
        "claim_scope": claim_scope,
        "financial_scope": financial_scope,
        "causal_bridge_authority": bridge,
        "claim_authority_card_digest": claim_authority_card["card_digest"],
        "cross_scope_causal_language_guard_pass": not lexical_risk_detected,
        "cross_scope_language_guard_mode": (
            "primary_fail_closed"
            if structured_claim_relation_receipt is None
            else "secondary_defense_in_depth"
        ),
        "structured_claim_relation_primary": (
            structured_claim_relation_receipt is not None
        ),
        "boundary_authority_sources": (
            [
                source
                for source, present in (
                    (
                        "limiting_evidence",
                        any(
                            "limit" in roles_by_ref.get(ref, set())
                            for ref in bindings["limiting_evidence_refs"]
                        ),
                    ),
                    (
                        "claim_local_limiting_evidence",
                        claim_local_limit,
                    ),
                    (
                        "typed_bridge_gap_relation",
                        typed_bridge_gap_boundary,
                    ),
                    (
                        "typed_same_scope_counter_relation",
                        typed_same_scope_counter_boundary,
                    ),
                )
                if present
            ]
        ),
        "harness_generated_research_judgment": False,
    }
    return receipt


__all__ = [
    "CLAIM_AUTHORITY_DYNAMIC_INPUT_SCHEMA_VERSION",
    "CLAIM_AUTHORITY_DYNAMIC_POLICY_SCHEMA_VERSION",
    "CLAIM_AUTHORITY_DELIVERABLE_SCHEMA_VERSION",
    "CLAIM_AUTHORITY_INPUT_SCHEMA_VERSION",
    "CLAIM_AUTHORITY_JUDGMENT_SCHEMA_VERSION",
    "CLAIM_AUTHORITY_MODEL_FIELDS",
    "CLAIM_AUTHORITY_POLICY_SCHEMA_VERSION",
    "ClaimAuthorityError",
    "compile_claim_authority_research_input",
    "load_claim_authority_policy",
    "validate_claim_authority_selection",
]
