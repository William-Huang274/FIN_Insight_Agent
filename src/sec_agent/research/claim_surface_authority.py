from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping, Sequence

from .reviewed_evidence_pack import canonical_digest


CLAIM_SURFACE_AUTHORITY_POLICY_SCHEMA_VERSION = (
    "fin_ia_claim_surface_authority_policy_v1_0"
)
CLAIM_SURFACE_RELATION_ALIAS_POLICY_SCHEMA_VERSION = (
    "fin_ia_claim_surface_authority_policy_v1_1"
)
CLAIM_SURFACE_AUTHORITY_INPUT_SCHEMA_VERSION = (
    "fin_ia_current_research_input_v1_3"
)
CLAIM_SURFACE_AUTHORITY_JUDGMENT_SCHEMA_VERSION = (
    "fin_ia_current_research_judgment_payload_v1_4"
)
CLAIM_SURFACE_AUTHORITY_DELIVERABLE_SCHEMA_VERSION = (
    "fin_ia_current_research_deliverable_v1_4"
)
CLAIM_SURFACE_RELATION_ALIAS_INPUT_SCHEMA_VERSION = (
    "fin_ia_current_research_input_v1_4"
)
CLAIM_SURFACE_RELATION_ALIAS_JUDGMENT_SCHEMA_VERSION = (
    "fin_ia_current_research_judgment_payload_v1_5"
)
CLAIM_SURFACE_RELATION_ALIAS_DELIVERABLE_SCHEMA_VERSION = (
    "fin_ia_current_research_deliverable_v1_5"
)
CLAIM_SURFACE_AUTHORITY_MODEL_FIELDS = (
    "claim_relations",
    "qualitative_fact_refs",
)
CLAIM_SURFACE_AUTHORITY_ATOM_FIELDS = (
    "thesis_atom",
    "mechanism_atom",
    "counterargument_atom",
)


class ClaimSurfaceAuthorityError(ValueError):
    """Fail-closed error for source-bound qualitative facts and claim relations."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ClaimSurfaceAuthorityError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _strings(
    value: object,
    code: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    _require(isinstance(value, list), code)
    rows = tuple(str(row).strip() for row in value)
    _require(
        (allow_empty or bool(rows))
        and all(rows)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


def _normalized_source_surface(value: object) -> str:
    return re.sub(r"[\s\-_]+", "", str(value or "").casefold())


def load_claim_surface_authority_policy(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    expected = {
        "schema_version",
        "status",
        "qualified_scope",
        "allowed_claim_subjects",
        "allowed_claim_outcomes",
        "allowed_claim_relations",
        "allowed_attribution_bases",
        "source_bound_qualitative_facts",
        "allowed_structured_claim_combinations",
        "narrative_conflict_guard",
        "authority",
    }
    _require(
        set(payload) == expected,
        "claim_surface_policy_fields_invalid",
    )
    schema_version = str(payload.get("schema_version") or "")
    alias_mode = schema_version == CLAIM_SURFACE_RELATION_ALIAS_POLICY_SCHEMA_VERSION
    _require(
        (
            schema_version == CLAIM_SURFACE_AUTHORITY_POLICY_SCHEMA_VERSION
            and payload.get("status")
            == "provider_neutral_fixed_pack_claim_surface_authority"
        )
        or (
            alias_mode
            and payload.get("status")
            == "provider_neutral_fixed_pack_claim_relation_alias_authority"
        ),
        "claim_surface_policy_status_invalid",
    )
    qualified = _mapping(
        payload.get("qualified_scope"),
        "claim_surface_qualified_scope_invalid",
    )
    _require(
        set(qualified)
        == {
            "case_key",
            "cell_id",
            "base_claim_authority_input_digest",
            "base_claim_authority_judgment_schema_version",
        }
        and str(qualified.get("case_key") or "").strip().upper()
        and str(qualified.get("cell_id") or "").startswith("CELL::")
        and len(str(qualified.get("base_claim_authority_input_digest") or ""))
        == 64
        and qualified.get("base_claim_authority_judgment_schema_version")
        == "fin_ia_current_research_judgment_payload_v1_3",
        "claim_surface_qualified_scope_invalid",
    )
    subjects = _strings(
        payload.get("allowed_claim_subjects"),
        "claim_surface_subjects_invalid",
    )
    outcomes = _strings(
        payload.get("allowed_claim_outcomes"),
        "claim_surface_outcomes_invalid",
    )
    relations = _strings(
        payload.get("allowed_claim_relations"),
        "claim_surface_relations_invalid",
    )
    attribution_bases = _strings(
        payload.get("allowed_attribution_bases"),
        "claim_surface_attribution_bases_invalid",
    )

    raw_facts = payload.get("source_bound_qualitative_facts")
    _require(
        isinstance(raw_facts, list) and bool(raw_facts),
        "claim_surface_qualitative_facts_invalid",
    )
    facts: list[dict[str, Any]] = []
    fact_refs: set[str] = set()
    for raw in raw_facts:
        row = _mapping(raw, "claim_surface_qualitative_fact_invalid")
        _require(
            set(row)
            == {
                "qualitative_fact_ref",
                "fact_kind",
                "case_key",
                "cell_id",
                "subject",
                "metric_id",
                "qualitative_band",
                "unit",
                "fiscal_year",
                "fiscal_period",
                "period_end",
                "authority_mode",
                "source_evidence_ref",
                "source_evidence_item_digest",
                "source_text_digest",
                "source_surface",
                "display_surface_zh",
                "qualifier_zh",
                "point_estimate_forbidden",
                "audited_numeric_fact",
            },
            "claim_surface_qualitative_fact_invalid",
        )
        ref = str(row.get("qualitative_fact_ref") or "")
        _require(
            ref.startswith("QF::")
            and ref not in fact_refs
            and row.get("fact_kind") == "management_target"
            and str(row.get("case_key") or "") == qualified["case_key"]
            and str(row.get("cell_id") or "") == qualified["cell_id"]
            and str(row.get("subject") or "") in subjects
            and str(row.get("metric_id") or "").strip()
            and str(row.get("qualitative_band") or "").strip()
            and str(row.get("unit") or "") == "percentage_rate"
            and isinstance(row.get("fiscal_year"), int)
            and str(row.get("fiscal_period") or "").startswith("Q")
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(row.get("period_end") or ""))
            is not None
            and row.get("authority_mode") == "issuer_management_assertion"
            and str(row.get("source_evidence_ref") or "").startswith("EV::")
            and len(str(row.get("source_evidence_item_digest") or "")) == 64
            and len(str(row.get("source_text_digest") or "")) == 64
            and str(row.get("source_surface") or "").strip()
            and str(row.get("display_surface_zh") or "").strip()
            and str(row.get("qualifier_zh") or "").strip()
            and row.get("point_estimate_forbidden") is True
            and row.get("audited_numeric_fact") is False,
            "claim_surface_qualitative_fact_invalid",
        )
        fact_refs.add(ref)
        facts.append(deepcopy(dict(row)))

    raw_combinations = payload.get("allowed_structured_claim_combinations")
    _require(
        isinstance(raw_combinations, list) and bool(raw_combinations),
        "claim_surface_combinations_invalid",
    )
    combinations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str, str, str]] = set()
    seen_relation_refs: set[str] = set()
    for raw in raw_combinations:
        row = _mapping(raw, "claim_surface_combination_invalid")
        combination_fields = {
            "claim_subject",
            "claim_outcome",
            "claim_relation",
            "attribution_basis",
            "claim_scope",
            "financial_scope",
            "causal_bridge_authority",
            "allowed_atom_fields",
            "required_qualitative_fact_refs",
            "required_evidence_refs",
            "required_numeric_relation_refs",
            "required_gap_refs",
            "allowed_inference_authorities",
            "allowed_judgment_statuses",
        }
        if alias_mode:
            combination_fields.update(
                {"claim_relation_ref", "model_description_zh"}
            )
        _require(
            set(row) == combination_fields,
            "claim_surface_combination_invalid",
        )
        key = (
            str(row.get("claim_subject") or ""),
            str(row.get("claim_outcome") or ""),
            str(row.get("claim_relation") or ""),
            str(row.get("attribution_basis") or ""),
            str(row.get("claim_scope") or ""),
            str(row.get("financial_scope") or ""),
            str(row.get("causal_bridge_authority") or ""),
        )
        qualitative_refs = _strings(
            row.get("required_qualitative_fact_refs"),
            "claim_surface_combination_invalid",
            allow_empty=True,
        )
        atom_fields = _strings(
            row.get("allowed_atom_fields"),
            "claim_surface_combination_invalid",
        )
        evidence_refs = _strings(
            row.get("required_evidence_refs"),
            "claim_surface_combination_invalid",
            allow_empty=True,
        )
        numeric_relation_refs = _strings(
            row.get("required_numeric_relation_refs"),
            "claim_surface_combination_invalid",
            allow_empty=True,
        )
        gap_refs = _strings(
            row.get("required_gap_refs"),
            "claim_surface_combination_invalid",
            allow_empty=True,
        )
        inference = _strings(
            row.get("allowed_inference_authorities"),
            "claim_surface_combination_invalid",
        )
        statuses = _strings(
            row.get("allowed_judgment_statuses"),
            "claim_surface_combination_invalid",
        )
        relation_ref = str(row.get("claim_relation_ref") or "")
        model_description = str(row.get("model_description_zh") or "").strip()
        _require(
            key[0] in subjects
            and key[1] in outcomes
            and key[2] in relations
            and key[3] in attribution_bases
            and all(key[4:])
            and key not in seen
            and set(atom_fields).issubset(
                CLAIM_SURFACE_AUTHORITY_ATOM_FIELDS
            )
            and set(qualitative_refs).issubset(fact_refs)
            and all(ref.startswith("EV::") for ref in evidence_refs)
            and all(ref.startswith("REL::") for ref in numeric_relation_refs)
            and all(ref.startswith("GAP::") for ref in gap_refs),
            "claim_surface_combination_invalid",
        )
        if alias_mode:
            _require(
                relation_ref.startswith("CR::")
                and relation_ref not in seen_relation_refs
                and 1 <= len(model_description) <= 120,
                "claim_surface_relation_alias_invalid",
            )
            seen_relation_refs.add(relation_ref)
        seen.add(key)
        combination = {
                "claim_subject": key[0],
                "claim_outcome": key[1],
                "claim_relation": key[2],
                "attribution_basis": key[3],
                "claim_scope": key[4],
                "financial_scope": key[5],
                "causal_bridge_authority": key[6],
                "allowed_atom_fields": list(atom_fields),
                "required_qualitative_fact_refs": list(qualitative_refs),
                "required_evidence_refs": list(evidence_refs),
                "required_numeric_relation_refs": list(numeric_relation_refs),
                "required_gap_refs": list(gap_refs),
                "allowed_inference_authorities": list(inference),
                "allowed_judgment_statuses": list(statuses),
            }
        if alias_mode:
            combination = {
                "claim_relation_ref": relation_ref,
                "model_description_zh": model_description,
                **combination,
            }
        combinations.append(combination)

    guard = _mapping(
        payload.get("narrative_conflict_guard"),
        "claim_surface_narrative_guard_invalid",
    )
    _require(
        set(guard)
        == {
            "subject_terms",
            "financial_outcome_terms",
            "direct_causal_terms",
            "management_attribution_terms",
            "relations_requiring_attribution_for_direct_causal_surface",
            "relations_forbidding_direct_causal_surface",
        },
        "claim_surface_narrative_guard_invalid",
    )
    normalized_guard = {
        key: list(
            _strings(
                guard.get(key),
                "claim_surface_narrative_guard_invalid",
            )
        )
        for key in guard
    }
    _require(
        set(
            normalized_guard[
                "relations_requiring_attribution_for_direct_causal_surface"
            ]
        ).issubset(relations),
        "claim_surface_narrative_guard_invalid",
    )
    _require(
        set(
            normalized_guard[
                "relations_forbidding_direct_causal_surface"
            ]
        ).issubset(relations),
        "claim_surface_narrative_guard_invalid",
    )
    authority = _mapping(
        payload.get("authority"),
        "claim_surface_policy_authority_invalid",
    )
    _require(
        dict(authority)
        == {
            "model_selects_structured_claim_relation": True,
            "model_selects_only_source_bound_qualitative_fact_refs": True,
            "model_owns_narrative_judgment": True,
            "harness_renders_selected_fact_surface_without_point_estimate": True,
            "harness_may_validate_but_not_invent_claim_relation": True,
            "legacy_lexical_guard_is_defense_in_depth_only": True,
            "fixed_pack_test_is_not_agentic_research": True,
            "qualified_human_content_review_required": True,
        },
        "claim_surface_policy_authority_invalid",
    )
    return {
        **deepcopy(dict(payload)),
        "qualified_scope": deepcopy(dict(qualified)),
        "allowed_claim_subjects": list(subjects),
        "allowed_claim_outcomes": list(outcomes),
        "allowed_claim_relations": list(relations),
        "allowed_attribution_bases": list(attribution_bases),
        "source_bound_qualitative_facts": facts,
        "allowed_structured_claim_combinations": combinations,
        "narrative_conflict_guard": normalized_guard,
        "authority": deepcopy(dict(authority)),
    }


def compile_claim_surface_authority_research_input(
    claim_authority_input: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Overlay source-bound qualitative facts and structured claim relations."""

    loaded = load_claim_surface_authority_policy(policy)
    qualified = loaded["qualified_scope"]
    _require(
        claim_authority_input.get("schema_version")
        == "fin_ia_current_research_input_v1_2"
        and claim_authority_input.get("research_input_digest")
        == qualified["base_claim_authority_input_digest"]
        and claim_authority_input.get("model_output_contract", {}).get(
            "payload_schema_version"
        )
        == qualified["base_claim_authority_judgment_schema_version"]
        and claim_authority_input.get("case_identity", {}).get("case_key")
        == qualified["case_key"]
        and isinstance(
            claim_authority_input.get("claim_authority_contract"), Mapping
        ),
        "claim_surface_base_input_not_qualified",
    )
    cell_id = str(qualified["cell_id"])
    cells = {
        str(row.get("cell_id") or ""): row
        for row in claim_authority_input.get("cells") or ()
        if isinstance(row, Mapping)
    }
    _require(cell_id in cells, "claim_surface_cell_not_qualified")
    cell = cells[cell_id]
    _require(
        isinstance(cell.get("claim_authority_card"), Mapping),
        "claim_surface_claim_authority_card_missing",
    )
    evidence_by_ref = {
        str(row.get("evidence_ref") or ""): row
        for row in claim_authority_input.get("evidence_cards") or ()
        if isinstance(row, Mapping)
    }
    allowed_evidence = set(cell.get("allowed_evidence_refs") or ())
    allowed_relations = set(cell.get("allowed_numeric_relation_refs") or ())
    allowed_gaps = set(cell.get("visible_gap_refs") or ())
    compiled_facts: list[dict[str, Any]] = []
    for raw in loaded["source_bound_qualitative_facts"]:
        evidence_ref = str(raw["source_evidence_ref"])
        evidence = evidence_by_ref.get(evidence_ref)
        _require(
            evidence_ref in allowed_evidence
            and isinstance(evidence, Mapping)
            and evidence.get("evidence_owner_ticker") == qualified["case_key"]
            and evidence.get("evidence_item_digest")
            == raw["source_evidence_item_digest"]
            and evidence.get("source_text_digest") == raw["source_text_digest"]
            and _normalized_source_surface(raw["source_surface"])
            in _normalized_source_surface(
                evidence.get("source_visible_fact_excerpt")
            ),
            "claim_surface_qualitative_fact_source_drift",
        )
        body = deepcopy(raw)
        compiled_facts.append(
            {**body, "qualitative_fact_digest": canonical_digest(body)}
        )
    fact_refs = {
        str(row["qualitative_fact_ref"]) for row in compiled_facts
    }
    for row in loaded["allowed_structured_claim_combinations"]:
        _require(
            set(row["required_qualitative_fact_refs"]).issubset(fact_refs)
            and set(row["required_evidence_refs"]).issubset(allowed_evidence)
            and set(row["required_numeric_relation_refs"]).issubset(
                allowed_relations
            )
            and set(row["required_gap_refs"]).issubset(allowed_gaps),
            "claim_surface_combination_binding_drift",
        )
    alias_mode = (
        loaded["schema_version"]
        == CLAIM_SURFACE_RELATION_ALIAS_POLICY_SCHEMA_VERSION
    )
    relation_card_body = {
        "card_schema_version": (
            "fin_ia_structured_claim_relation_card_v1_1"
            if alias_mode
            else "fin_ia_structured_claim_relation_card_v1_0"
        ),
        "case_key": qualified["case_key"],
        "cell_id": cell_id,
        "allowed_claim_subjects": deepcopy(loaded["allowed_claim_subjects"]),
        "allowed_claim_outcomes": deepcopy(loaded["allowed_claim_outcomes"]),
        "allowed_claim_relations": deepcopy(loaded["allowed_claim_relations"]),
        "allowed_attribution_bases": deepcopy(
            loaded["allowed_attribution_bases"]
        ),
        "allowed_combinations": deepcopy(
            loaded["allowed_structured_claim_combinations"]
        ),
        **(
            {
                "model_relation_aliases": [
                    {
                        "claim_relation_ref": row["claim_relation_ref"],
                        "model_description_zh": row["model_description_zh"],
                        "allowed_atom_fields": deepcopy(
                            row["allowed_atom_fields"]
                        ),
                    }
                    for row in loaded[
                        "allowed_structured_claim_combinations"
                    ]
                ]
            }
            if alias_mode
            else {}
        ),
        "rules": [
            "The structured relation is the authoritative semantic commitment selected by the model.",
            "A management target remains an attributed, unaudited qualitative fact and never becomes a point estimate.",
            "Narrative atoms remain model-authored but may not contradict or broaden the selected relation.",
            "The harness renders the selected fact surface and receipt; it does not invent the research conclusion.",
        ],
    }
    relation_card = {
        **relation_card_body,
        "card_digest": canonical_digest(relation_card_body),
    }
    unsigned = deepcopy(dict(claim_authority_input))
    unsigned.pop("research_input_digest", None)
    unsigned["schema_version"] = (
        CLAIM_SURFACE_RELATION_ALIAS_INPUT_SCHEMA_VERSION
        if alias_mode
        else CLAIM_SURFACE_AUTHORITY_INPUT_SCHEMA_VERSION
    )
    unsigned["source_bound_qualitative_fact_cards"] = deepcopy(compiled_facts)
    for row in unsigned["cells"]:
        if row["cell_id"] == cell_id:
            row["allowed_qualitative_fact_refs"] = sorted(fact_refs)
            row["claim_relation_card"] = deepcopy(relation_card)
    output = unsigned["model_output_contract"]
    output["payload_schema_version"] = (
        CLAIM_SURFACE_RELATION_ALIAS_JUDGMENT_SCHEMA_VERSION
        if alias_mode
        else CLAIM_SURFACE_AUTHORITY_JUDGMENT_SCHEMA_VERSION
    )
    output["model_owned_cell_fields"] = [
        *output["model_owned_cell_fields"],
        *CLAIM_SURFACE_AUTHORITY_MODEL_FIELDS,
    ]
    output["harness_injected_cell_fields"] = [
        *output["harness_injected_cell_fields"],
        "claim_surface_authority_receipt",
    ]
    output["allowed_claim_subjects"] = deepcopy(
        loaded["allowed_claim_subjects"]
    )
    output["allowed_claim_outcomes"] = deepcopy(
        loaded["allowed_claim_outcomes"]
    )
    output["allowed_claim_relations"] = deepcopy(
        loaded["allowed_claim_relations"]
    )
    output["allowed_attribution_bases"] = deepcopy(
        loaded["allowed_attribution_bases"]
    )
    if alias_mode:
        output["allowed_claim_relation_refs"] = [
            row["claim_relation_ref"]
            for row in loaded["allowed_structured_claim_combinations"]
        ]
    unsigned["claim_surface_authority_contract"] = {
        "policy_schema_version": loaded["schema_version"],
        "policy_digest": canonical_digest(loaded),
        "qualified_case_key": qualified["case_key"],
        "qualified_cell_ids": [cell_id],
        "base_claim_authority_input_digest": qualified[
            "base_claim_authority_input_digest"
        ],
        "structured_claim_relation_primary": True,
        "model_view_mode": (
            "claim_relation_alias_compact_v1"
            if alias_mode
            else "full_structured_claim_relation_v1"
        ),
        "relation_alias_selection_primary": alias_mode,
        "qualitative_fact_surface_is_harness_rendered": True,
        "point_estimate_from_qualitative_band_forbidden": True,
        "narrative_conflict_guard": deepcopy(
            loaded["narrative_conflict_guard"]
        ),
        "fixed_pack_unit_test_only": True,
        "dynamic_retrieval_executed": False,
        "agentic_research_claimed": False,
        "authority": deepcopy(loaded["authority"]),
    }
    return {**unsigned, "research_input_digest": canonical_digest(unsigned)}


def validate_claim_surface_authority_selection(
    raw: Mapping[str, Any],
    *,
    claim_relation_card: Mapping[str, Any],
    claim_surface_contract: Mapping[str, Any],
    qualitative_fact_cards: Sequence[Mapping[str, Any]],
    evidence_uses: Sequence[Mapping[str, str]],
    numeric_relation_refs: Sequence[str],
    remaining_gap_refs: Sequence[str],
    inference_authority: str,
    judgment_status: str,
    narrative_atoms: Sequence[str],
) -> dict[str, Any]:
    raw_relations = raw.get("claim_relations")
    _require(
        isinstance(raw_relations, list)
        and len(raw_relations) == len(CLAIM_SURFACE_AUTHORITY_ATOM_FIELDS),
        "claim_surface_claim_relations_invalid",
    )
    qualitative_refs = _strings(
        raw.get("qualitative_fact_refs"),
        "claim_surface_qualitative_fact_refs_invalid",
        allow_empty=True,
    )
    facts = {
        str(row["qualitative_fact_ref"]): row
        for row in qualitative_fact_cards
    }
    roles_by_ref = {
        str(row["evidence_ref"]): str(row["use_role"])
        for row in evidence_uses
    }
    guard = claim_surface_contract["narrative_conflict_guard"]
    guarded_relations = set(
        guard[
            "relations_requiring_attribution_for_direct_causal_surface"
        ]
    )
    forbidden_causal_relations = set(
        guard["relations_forbidding_direct_causal_surface"]
    )
    narrative_by_field = dict(
        zip(CLAIM_SURFACE_AUTHORITY_ATOM_FIELDS, narrative_atoms)
    )
    validated_relations: list[dict[str, str]] = []
    seen_atom_fields: set[str] = set()
    required_qualitative_refs: set[str] = set()
    alias_mode = (
        claim_surface_contract.get("model_view_mode")
        == "claim_relation_alias_compact_v1"
    )
    for raw_relation in raw_relations:
        row = _mapping(
            raw_relation,
            "claim_surface_claim_relation_invalid",
        )
        atom_field = str(row.get("atom_field") or "")
        per_atom_inference_explicit = "inference_authority" in row
        atom_inference_authority = str(
            row.get("inference_authority") or inference_authority
        )
        if alias_mode:
            _require(
                frozenset(row)
                in {
                    frozenset({"atom_field", "claim_relation_ref"}),
                    frozenset(
                        {
                            "atom_field",
                            "claim_relation_ref",
                            "inference_authority",
                        }
                    ),
                },
                "claim_surface_claim_relation_invalid",
            )
            relation_ref = str(row.get("claim_relation_ref") or "")
            combination = next(
                (
                    candidate
                    for candidate in claim_relation_card["allowed_combinations"]
                    if candidate.get("claim_relation_ref") == relation_ref
                    and atom_field in candidate["allowed_atom_fields"]
                ),
                None,
            )
            _require(
                combination is not None,
                "claim_surface_relation_alias_invalid",
            )
            subject = str(combination["claim_subject"])
            outcome = str(combination["claim_outcome"])
            relation = str(combination["claim_relation"])
            attribution = str(combination["attribution_basis"])
            claim_scope = str(combination["claim_scope"])
            financial_scope = str(combination["financial_scope"])
            bridge = str(combination["causal_bridge_authority"])
        else:
            full_relation_fields = {
                "atom_field",
                "claim_subject",
                "claim_outcome",
                "claim_relation",
                "attribution_basis",
                "claim_scope",
                "financial_scope",
                "causal_bridge_authority",
            }
            _require(
                frozenset(row)
                in {
                    frozenset(full_relation_fields),
                    frozenset(
                        full_relation_fields | {"inference_authority"}
                    ),
                },
                "claim_surface_claim_relation_invalid",
            )
            relation_ref = ""
            subject = str(row.get("claim_subject") or "")
            outcome = str(row.get("claim_outcome") or "")
            relation = str(row.get("claim_relation") or "")
            attribution = str(row.get("attribution_basis") or "")
            claim_scope = str(row.get("claim_scope") or "")
            financial_scope = str(row.get("financial_scope") or "")
            bridge = str(row.get("causal_bridge_authority") or "")
        _require(
            atom_field in CLAIM_SURFACE_AUTHORITY_ATOM_FIELDS
            and atom_field not in seen_atom_fields
            and subject in set(claim_relation_card["allowed_claim_subjects"])
            and outcome in set(claim_relation_card["allowed_claim_outcomes"])
            and relation in set(claim_relation_card["allowed_claim_relations"])
            and attribution
            in set(claim_relation_card["allowed_attribution_bases"]),
            "claim_surface_output_enum_invalid",
        )
        seen_atom_fields.add(atom_field)
        if not alias_mode:
            combination = next(
                (
                    candidate
                    for candidate in claim_relation_card["allowed_combinations"]
                    if candidate["claim_subject"] == subject
                    and candidate["claim_outcome"] == outcome
                    and candidate["claim_relation"] == relation
                    and candidate["attribution_basis"] == attribution
                    and candidate["claim_scope"] == claim_scope
                    and candidate["financial_scope"] == financial_scope
                    and candidate["causal_bridge_authority"] == bridge
                    and atom_field in candidate["allowed_atom_fields"]
                ),
                None,
            )
        _require(
            combination is not None
            and atom_inference_authority
            in set(combination["allowed_inference_authorities"])
            and judgment_status
            in set(combination["allowed_judgment_statuses"]),
            "claim_surface_combination_invalid",
        )
        required_qualitative_refs.update(
            combination["required_qualitative_fact_refs"]
        )
        _require(
            all(
                roles_by_ref.get(ref) == "support"
                for ref in combination["required_evidence_refs"]
            )
            and set(combination["required_numeric_relation_refs"]).issubset(
                numeric_relation_refs
            )
            and set(combination["required_gap_refs"]).issubset(
                remaining_gap_refs
            ),
            "claim_surface_required_authority_missing",
        )
        text = str(narrative_by_field[atom_field]).casefold()
        if relation in guarded_relations:
            has_subject = any(
                term.casefold() in text for term in guard["subject_terms"]
            )
            has_outcome = any(
                term.casefold() in text
                for term in guard["financial_outcome_terms"]
            )
            has_causal = any(
                term.casefold() in text
                for term in guard["direct_causal_terms"]
            )
            attributed = any(
                term.casefold() in text
                for term in guard["management_attribution_terms"]
            )
            _require(
                not (
                    has_subject
                    and has_outcome
                    and has_causal
                    and not attributed
                ),
                "claim_surface_narrative_relation_conflict",
            )
        if relation in forbidden_causal_relations:
            has_subject = any(
                term.casefold() in text for term in guard["subject_terms"]
            )
            has_outcome = any(
                term.casefold() in text
                for term in guard["financial_outcome_terms"]
            )
            has_causal = any(
                term.casefold() in text
                for term in guard["direct_causal_terms"]
            )
            _require(
                not (has_subject and has_outcome and has_causal),
                "claim_surface_narrative_relation_conflict",
            )
        validated_relations.append(
            {
                "atom_field": atom_field,
                **(
                    {"claim_relation_ref": relation_ref}
                    if alias_mode
                    else {}
                ),
                "claim_subject": subject,
                "claim_outcome": outcome,
                "claim_relation": relation,
                "attribution_basis": attribution,
                "claim_scope": claim_scope,
                "financial_scope": financial_scope,
                "causal_bridge_authority": bridge,
                **(
                    {"inference_authority": atom_inference_authority}
                    if per_atom_inference_explicit
                    else {}
                ),
            }
        )
    _require(
        seen_atom_fields == set(CLAIM_SURFACE_AUTHORITY_ATOM_FIELDS),
        "claim_surface_claim_relation_coverage_invalid",
    )
    _require(
        set(qualitative_refs).issubset(facts)
        and set(qualitative_refs) == required_qualitative_refs,
        "claim_surface_qualitative_fact_boundary_invalid",
    )
    _require(
        all(
            roles_by_ref.get(str(facts[ref]["source_evidence_ref"]))
            == "support"
            for ref in qualitative_refs
        ),
        "claim_surface_qualitative_fact_source_not_supported",
    )
    receipt_body = {
        "claim_relations": validated_relations,
        "qualitative_fact_refs": list(qualitative_refs),
        "claim_relation_card_digest": claim_relation_card["card_digest"],
        "structured_claim_relation_primary": True,
        "narrative_conflict_guard_pass": True,
        "qualitative_fact_point_estimate_generated": False,
        "harness_generated_research_judgment": False,
    }
    return {**receipt_body, "receipt_digest": canonical_digest(receipt_body)}


__all__ = [
    "CLAIM_SURFACE_AUTHORITY_DELIVERABLE_SCHEMA_VERSION",
    "CLAIM_SURFACE_AUTHORITY_INPUT_SCHEMA_VERSION",
    "CLAIM_SURFACE_AUTHORITY_JUDGMENT_SCHEMA_VERSION",
    "CLAIM_SURFACE_AUTHORITY_MODEL_FIELDS",
    "CLAIM_SURFACE_AUTHORITY_POLICY_SCHEMA_VERSION",
    "CLAIM_SURFACE_RELATION_ALIAS_DELIVERABLE_SCHEMA_VERSION",
    "CLAIM_SURFACE_RELATION_ALIAS_INPUT_SCHEMA_VERSION",
    "CLAIM_SURFACE_RELATION_ALIAS_JUDGMENT_SCHEMA_VERSION",
    "CLAIM_SURFACE_RELATION_ALIAS_POLICY_SCHEMA_VERSION",
    "ClaimSurfaceAuthorityError",
    "compile_claim_surface_authority_research_input",
    "load_claim_surface_authority_policy",
    "validate_claim_surface_authority_selection",
]
