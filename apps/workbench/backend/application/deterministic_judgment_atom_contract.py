from __future__ import annotations

from datetime import date
import json
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest

from .bounded_agent_contract_policies import (
    CaseNumericAuthorityPolicy,
    ClaimFactAlias,
    ClaimFactLinkPolicy,
    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REF,
    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REFS,
    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
    S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF,
    SpecialistWWCJudgmentAtomPolicy,
)
from .fact_candidate_pool_planner import (
    FACT_CANDIDATE_POOL_MAXIMUM,
    FactCandidatePoolPlan,
    FactCandidatePoolPlanner,
)
from .fin_0_1_2_runtime_contract_binding import (
    FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF,
    Fin012RuntimeContractFamilyBinding,
    Fin012RuntimeContractBindingError,
    load_fin_0_1_2_runtime_contract_binding,
)


DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REFS = (
    *S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REFS,
    FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF,
)


class DeterministicJudgmentAtomCompiledContract:
    """Compile three alias/enum Provider families into canonical S4 output."""

    contract_ref = S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REF
    family_ids = (
        "specialist_fact_atoms",
        "claim_candidate_atoms",
        "what_would_change_atoms",
    )
    provider_output_max_utf8_bytes = 4800
    local_rendered_max_utf8_bytes = 16384
    provider_candidate_maximum = 6
    fact_selected_maximum = 3
    claim_selected_maximum = 2
    wwc_selected_maximum = 3
    local_item_max_unicode_characters = 2048

    causal_relations = ("supports", "challenges", "mixed", "unknown")
    materialities = ("high", "medium", "low")
    confidences = ("high", "medium", "low")
    priorities = ("critical", "high", "normal", "low")
    claim_kinds = (
        "evidence_direction",
        "economic_mechanism",
        "counterevidence",
        "insufficient_evidence",
    )
    trigger_codes = (
        "authority_confirmation",
        "authority_contradiction",
        "trend_persists",
        "bounded_event_occurs",
    )
    review_cadences = (
        "next_authority_event",
        "next_reporting_event",
        "next_month_end",
        "next_quarter_end",
        "bound_date",
        "unscheduled",
    )
    expected_transitions = (
        "strengthen",
        "weaken",
        "resolve_cannot_infer",
        "invalidate",
        "no_change",
    )

    _relation_text = {
        "supports": "支持",
        "challenges": "削弱",
        "mixed": "形成混合证据",
        "unknown": "尚不足以判断",
    }
    _claim_kind_text = {
        "evidence_direction": "证据方向",
        "economic_mechanism": "经济机制",
        "counterevidence": "反证机制",
        "insufficient_evidence": "证据缺口",
    }
    _priority_rank = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    _materiality_rank = {"high": 0, "medium": 1, "low": 2}
    _confidence_rank = {"high": 0, "medium": 1, "low": 2}
    _claim_epistemic_priority_rank = {
        "fact_supported": 0,
        "bounded_inference": 1,
        "hypothesis": 2,
        "cannot_infer": 3,
    }
    _authority_specificity_rank = {
        "Numeric": 0,
        "Evidence": 1,
        "Graph": 2,
    }
    _trigger_actionability_rank = {
        "authority_contradiction": 0,
        "authority_confirmation": 1,
        "bounded_event_occurs": 2,
        "trend_persists": 3,
    }
    _review_cadence_rank = {
        "bound_date": 0,
        "next_authority_event": 1,
        "next_reporting_event": 2,
        "next_month_end": 3,
        "next_quarter_end": 4,
        "unscheduled": 5,
    }
    _expected_transition_rank = {
        "invalidate": 0,
        "weaken": 1,
        "resolve_cannot_infer": 2,
        "strengthen": 3,
        "no_change": 4,
    }
    _trigger_to_rule = {
        "authority_confirmation": "evidence_confirmation",
        "authority_contradiction": "evidence_confirmation",
        "trend_persists": "trend_persists",
        "bounded_event_occurs": "event_occurs",
    }
    _trigger_text = {
        "authority_confirmation": "绑定权威来源确认当前方向",
        "authority_contradiction": "绑定权威来源出现相反证据",
        "trend_persists": "绑定权威观察持续",
        "bounded_event_occurs": "绑定权威事件发生",
    }
    _transition_text = {
        "strengthen": "strengthen the linked claim",
        "weaken": "weaken the linked claim",
        "resolve_cannot_infer": "resolve the linked claim from cannot_infer",
        "invalidate": "invalidate the linked claim",
        "no_change": "retain the linked claim state",
    }

    def __init__(
        self,
        *,
        cell_input: Mapping[str, Any],
        validated_segments: Mapping[str, Mapping[str, Any]],
        as_of: str,
        contract_ref: str = (
            S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REF
        ),
        research_profile_ref: str | None = None,
        runtime_contract_family_binding_ref: str | None = None,
        runtime_contract_family_source_digest: str | None = None,
    ) -> None:
        if contract_ref not in (
            DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REFS
        ):
            raise ValueError(
                "s4_compiled_judgment_atom_contract_unsupported"
            )
        self.contract_ref = contract_ref
        self.runtime_contract_binding: (
            Fin012RuntimeContractFamilyBinding | None
        ) = None
        if (
            contract_ref
            == FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF
        ):
            binding = load_fin_0_1_2_runtime_contract_binding()
            binding.assert_admission_binding(
                binding_ref=runtime_contract_family_binding_ref,
                source_digest=runtime_contract_family_source_digest,
            )
            binding.assert_runtime_compatibility(
                provider_candidate_maximum=self.provider_candidate_maximum,
                selected_maxima=(
                    self.fact_selected_maximum,
                    self.claim_selected_maximum,
                    self.wwc_selected_maximum,
                ),
                provider_output_max_utf8_bytes=(
                    self.provider_output_max_utf8_bytes
                ),
                local_rendered_max_utf8_bytes=(
                    self.local_rendered_max_utf8_bytes
                ),
            )
            self.runtime_contract_binding = binding
        elif (
            runtime_contract_family_binding_ref is not None
            or runtime_contract_family_source_digest is not None
        ):
            raise Fin012RuntimeContractBindingError(
                "fin012_runtime_contract_binding_requires_fin012_contract_ref"
            )
        self.cell_input = dict(cell_input)
        self.validated_segments = {
            str(key): dict(value)
            for key, value in validated_segments.items()
        }
        self.program_cell_id = str(cell_input.get("program_cell_id") or "")
        if not self.program_cell_id:
            raise ValueError("s4_compiled_atom_program_cell_missing")
        self.research_profile_ref = (
            str(research_profile_ref).strip()
            if research_profile_ref is not None
            else ""
        )
        self._fact_candidate_pool_plan_cache: (
            FactCandidatePoolPlan | None
        ) = None
        try:
            self.as_of = date.fromisoformat(str(as_of)[:10]).isoformat()
        except ValueError as exc:
            raise ValueError("s4_compiled_atom_as_of_invalid") from exc
        self.numeric_policy = CaseNumericAuthorityPolicy.from_cell_input(
            cell_input
        )

    @property
    def claim_epistemic_support_role_v2(self) -> bool:
        return (
            self.contract_ref
            in {
                S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
                FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF,
            }
        )

    def _consumer_binding(
        self,
        consumer_id: str,
    ) -> dict[str, Any] | None:
        if self.runtime_contract_binding is None:
            return None
        return self.runtime_contract_binding.consumer_receipt(consumer_id)

    def runtime_contract_binding_receipt(self) -> dict[str, Any] | None:
        binding = self.runtime_contract_binding
        if binding is None:
            return None
        return {
            "binding_ref": binding.binding_ref,
            "source_ref": binding.source_ref,
            "source_file_sha256": binding.source_file_sha256,
            "source_digest": binding.source_digest,
            "contract_id": binding.contract_id,
            "contract_version": binding.contract_version,
            "compiled_contract_ref": binding.compiled_contract_ref,
            "local_truth_fields": list(binding.local_truth_fields),
            "provider_surface": binding.provider_surface,
        }

    def claim_kind_support_role_contract(self) -> dict[str, Any]:
        """Single source for the v2 Claim kind/support cross-field invariant."""

        return {
            "rule_id": "claim_kind_support_fact_aliases_epistemic_role:v1",
            "insufficient_evidence": {
                "support_fact_aliases_cardinality": "exactly_zero",
                "local_epistemic_status": "cannot_infer",
                "local_support_fact_ids_cardinality": "exactly_zero",
                "local_cannot_support_cardinality": "one_or_more",
            },
            "supported_judgment_kinds": {
                "claim_kinds": [
                    "evidence_direction",
                    "economic_mechanism",
                    "counterevidence",
                ],
                "support_fact_aliases_cardinality": "one_or_more_unique",
                "local_epistemic_status_by_direction": {
                    "supports": "fact_supported",
                    "challenges": "fact_supported",
                    "mixed": "bounded_inference",
                    "unknown": "bounded_inference",
                },
                "local_support_fact_ids": "exact_alias_expansion",
                "local_cannot_support": "bound_fact_boundaries",
            },
            "boundary_backed_limitation_encoding": {
                "claim_kind": "evidence_direction",
                "direction": "unknown_or_mixed",
                "support_fact_aliases_cardinality": "one_or_more_unique",
                "insufficient_evidence_with_support_is_forbidden": True,
            },
            "invalid_failure_code": (
                "s4_compiled_claim_atom_epistemic_support_role_invalid"
            ),
        }

    @staticmethod
    def _walk_rows(value: Any) -> list[Mapping[str, Any]]:
        rows: list[Mapping[str, Any]] = []
        if isinstance(value, Mapping):
            rows.append(value)
            for child in value.values():
                rows.extend(
                    DeterministicJudgmentAtomCompiledContract._walk_rows(
                        child
                    )
                )
        elif isinstance(value, (list, tuple)):
            for child in value:
                rows.extend(
                    DeterministicJudgmentAtomCompiledContract._walk_rows(
                        child
                    )
                )
        return rows

    @staticmethod
    def _nonblank_strings(value: Any) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple, set, frozenset)):
            return ()
        return tuple(
            str(item)
            for item in value
            if isinstance(item, str) and item.strip()
        )

    def family_id(self, segment_id: str) -> str:
        try:
            return {
                "facts_explanation_and_terminal": self.family_ids[0],
                "owner_grade_claim_cards": self.family_ids[1],
                "actionable_what_would_change_tasks": self.family_ids[2],
            }[segment_id]
        except KeyError as exc:
            raise ValueError("s4_compiled_atom_segment_unknown") from exc

    def _evidence_catalog(self) -> tuple[dict[str, str], ...]:
        authority = self.cell_input.get("authority_refs")
        authority = authority if isinstance(authority, Mapping) else {}
        refs = sorted(
            set(
                self._nonblank_strings(
                    authority.get("accepted_evidence_refs")
                )
            )
        )
        rows = self._walk_rows(self.cell_input.get("evidence_input"))
        catalog: list[dict[str, str]] = []
        for ordinal, evidence_ref in enumerate(refs, 1):
            row = next(
                (
                    item
                    for item in rows
                    if item.get("evidence_ref") == evidence_ref
                ),
                None,
            )
            if row is None:
                raise ValueError(
                    "s4_compiled_atom_evidence_metadata_missing"
                )
            statement = str(row.get("statement") or "").strip()
            boundary = str(
                row.get("claim_boundary")
                or row.get("boundary")
                or ""
            ).strip()
            if not statement or not boundary:
                raise ValueError(
                    "s4_compiled_atom_evidence_metadata_missing"
                )
            role = str(
                row.get("evidence_role") or "issuer_evidence"
            )
            candidate = {
                "alias": f"E{ordinal:03d}",
                "authority_ref": evidence_ref,
                "statement": statement,
                "boundary": boundary,
                "role": role,
                "support_kind": "Evidence",
                "authority_kind": "Evidence",
                "scope_kind": (
                    "issuer_exact"
                    if str(row.get("entity_ref") or "").strip()
                    else "unknown"
                ),
            }
            candidate["canonical_support_digest"] = canonical_digest(
                candidate
            )
            catalog.append(candidate)
        return tuple(catalog)

    def _numeric_catalog(self) -> tuple[dict[str, str], ...]:
        catalog: list[dict[str, str]] = []
        for row in self.numeric_policy.rows:
            candidate = {
                "alias": row.alias,
                "authority_ref": row.numeric_ref,
                "statement": row.rendered_clause(),
                "boundary": (
                    "仅限本地绑定的实体、期间、口径、单位、符号与精度"
                ),
                "role": row.metric_family,
                "support_kind": "Numeric",
                "authority_kind": "Numeric",
                "scope_kind": (
                    "company_total"
                    if row.business_scope_ref == "__company_total__"
                    else "segment"
                ),
            }
            candidate["canonical_support_digest"] = canonical_digest(
                candidate
            )
            catalog.append(candidate)
        return tuple(catalog)

    def _fact_catalog(self) -> tuple[dict[str, str], ...]:
        return (*self._evidence_catalog(), *self._numeric_catalog())

    def fact_candidate_pool_plan(self) -> FactCandidatePoolPlan | None:
        if not self.research_profile_ref:
            return None
        if self._fact_candidate_pool_plan_cache is None:
            planner = FactCandidatePoolPlanner.from_registry(
                research_profile_ref=self.research_profile_ref,
                program_cell_id=self.program_cell_id,
            )
            self._fact_candidate_pool_plan_cache = planner.plan(
                self._fact_catalog()
            )
        return self._fact_candidate_pool_plan_cache

    def _provider_fact_catalog(self) -> tuple[dict[str, str], ...]:
        plan = self.fact_candidate_pool_plan()
        if plan is None:
            return self._fact_catalog()
        return tuple(dict(row) for row in plan.candidate_rows)

    def _claim_policy(self) -> ClaimFactLinkPolicy:
        first = self.validated_segments.get(
            "facts_explanation_and_terminal"
        )
        if not isinstance(first, Mapping):
            raise ValueError("s4_compiled_atom_prior_facts_missing")
        numeric_scopes = {
            row.numeric_ref: {
                "entity_ref": row.entity_ref,
                "business_scope_kind": (
                    "company_total"
                    if row.business_scope_ref == "__company_total__"
                    else "segment"
                ),
                "business_scope_ref": row.business_scope_ref,
                "period": row.period,
                "attribution_level": (
                    "company_total"
                    if row.business_scope_ref == "__company_total__"
                    else "segment"
                ),
            }
            for row in self.numeric_policy.rows
        }
        return ClaimFactLinkPolicy.from_validated_facts(
            program_cell_id=self.program_cell_id,
            facts=list(first.get("fact_layer") or ()),
            numeric_scopes=numeric_scopes,
        )

    def _wwc_policy(self) -> SpecialistWWCJudgmentAtomPolicy:
        claims = self.validated_segments.get("owner_grade_claim_cards")
        if not isinstance(claims, Mapping):
            raise ValueError("s4_compiled_atom_prior_claims_missing")
        return SpecialistWWCJudgmentAtomPolicy.from_cell_input(
            cell_input=self.cell_input,
            claims=list(claims.get("judgment_layer") or ()),
            as_of=self.as_of,
            contract_ref=S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF,
        )

    def model_visible_contract(self, segment_id: str) -> dict[str, Any]:
        prompt_binding = self._consumer_binding("prompt")
        family = self.family_id(segment_id)
        contract: dict[str, Any] = {
            "contract_ref": self.contract_ref,
            "family_id": family,
            "program_cell_id": self.program_cell_id,
            "provider_output_max_utf8_bytes": (
                self.provider_output_max_utf8_bytes
            ),
            "provider_free_material_narrative_allowed": False,
            "local_deterministic_owner": [
                "validity_filtering",
                "final_cardinality",
                "final_ordering",
                "canonical_ids_and_refs",
                "material_numbers_periods_thresholds_and_dates",
                "case_identity",
                "final_sentences",
                "lineage",
            ],
        }
        if prompt_binding is not None:
            contract["runtime_contract_family_binding"] = {
                **dict(prompt_binding),
                "provider_surface": (
                    self.runtime_contract_binding.provider_surface
                    if self.runtime_contract_binding is not None
                    else ""
                ),
            }
        if family == self.family_ids[0]:
            candidate_catalog = self._provider_fact_catalog()
            candidate_plan = self.fact_candidate_pool_plan()
            contract.update(
                {
                    "allowed_supports": [
                        {
                            "support_alias": row["alias"],
                            "support_kind": (
                                "Numeric"
                                if row["alias"].startswith("N")
                                else "Evidence"
                            ),
                            "semantic_role": row["role"],
                        }
                        for row in candidate_catalog
                    ],
                    "causal_relations": list(self.causal_relations),
                    "materialities": list(self.materialities),
                    "confidences": list(self.confidences),
                    "priorities": list(self.priorities),
                    "terminal_classes": [
                        "supported",
                        "mixed",
                        "insufficient",
                    ],
                    "provider_candidate_maximum": (
                        FACT_CANDIDATE_POOL_MAXIMUM
                        if candidate_plan is not None
                        else self.provider_candidate_maximum
                    ),
                    "local_selected_maximum": self.fact_selected_maximum,
                }
            )
            if candidate_plan is not None:
                receipt = candidate_plan.safe_receipt()
                contract.update(
                    {
                        "fact_candidate_pool_contract_ref": (
                            receipt["contract_ref"]
                        ),
                        "fact_candidate_profile_contract_ref": (
                            receipt["profile_contract_ref"]
                        ),
                        "fact_candidate_profile_digest": (
                            receipt["profile_digest"]
                        ),
                        "fact_candidate_pool_digest": (
                            receipt["candidate_pool_digest"]
                        ),
                        "eligible_support_count": (
                            receipt["eligible_support_count"]
                        ),
                        "visible_support_count": (
                            receipt["candidate_pool_count"]
                        ),
                    }
                )
        elif family == self.family_ids[1]:
            contract.update(
                {
                    "allowed_facts": [
                        row.provider_payload()
                        for row in self._claim_policy().alias_rows
                    ],
                    "claim_kinds": list(self.claim_kinds),
                    "directions": list(self.causal_relations),
                    "materialities": list(self.materialities),
                    "confidences": list(self.confidences),
                    "priorities": list(self.priorities),
                    "provider_candidate_maximum": (
                        self.provider_candidate_maximum
                    ),
                    "local_selected_maximum": self.claim_selected_maximum,
                }
            )
            if self.claim_epistemic_support_role_v2:
                contract["claim_kind_support_role_rules"] = (
                    self.claim_kind_support_role_contract()
                )
        else:
            policy = self._wwc_policy()
            contract.update(
                {
                    "allowed_claims": [
                        row.provider_payload()
                        for row in policy.claim_policy.alias_rows
                    ],
                    "allowed_authorities": [
                        row.provider_payload()
                        for row in policy.authority_aliases
                    ],
                    "allowed_date_aliases": [
                        row.provider_payload()
                        for row in policy.temporal_date_aliases
                    ],
                    "trigger_codes": list(self.trigger_codes),
                    "directions": list(self.causal_relations),
                    "review_cadences": list(self.review_cadences),
                    "expected_transitions": list(
                        self.expected_transitions
                    ),
                    "provider_candidate_maximum": (
                        self.provider_candidate_maximum
                    ),
                    "local_selected_maximum": self.wwc_selected_maximum,
                }
            )
        contract["contract_digest"] = canonical_digest(contract)
        return contract

    def wire_schema(self, segment_id: str) -> dict[str, Any]:
        self._consumer_binding("server_schema")
        family = self.family_id(segment_id)
        if family == self.family_ids[0]:
            return {
                "program_cell_id": "exact input program_cell_id",
                "fact_atoms": [
                    {
                        "support_alias": "exact allowed support alias",
                        "causal_relation": "|".join(self.causal_relations),
                        "materiality": "|".join(self.materialities),
                        "confidence": "|".join(self.confidences),
                        "priority": "|".join(self.priorities),
                    }
                ],
                "terminal_class": "supported|mixed|insufficient",
            }
        if family == self.family_ids[1]:
            if self.claim_epistemic_support_role_v2:
                support_alias_description = (
                    "exactly [] when claim_kind=insufficient_evidence; "
                    "otherwise one or more unique exact allowed fact aliases"
                )
                claim_kind_description = (
                    "|".join(self.claim_kinds)
                    + "; obey claim_kind_support_role_rules"
                )
            else:
                support_alias_description = (
                    "zero or more exact allowed fact aliases"
                )
                claim_kind_description = "|".join(self.claim_kinds)
            return {
                "program_cell_id": "exact input program_cell_id",
                "claim_candidate_atoms": [
                    {
                        "support_fact_aliases": [
                            support_alias_description
                        ],
                        "claim_kind": claim_kind_description,
                        "direction": "|".join(self.causal_relations),
                        "materiality": "|".join(self.materialities),
                        "confidence": "|".join(self.confidences),
                        "priority": "|".join(self.priorities),
                    }
                ],
            }
        return {
            "program_cell_id": "exact input program_cell_id",
            "what_would_change_atoms": [
                {
                    "claim_alias": "exact allowed claim alias",
                    "primary_authority_alias": (
                        "exact allowed authority alias"
                    ),
                    "authority_aliases": [
                        "one or more exact allowed authority aliases"
                    ],
                    "trigger_code": "|".join(self.trigger_codes),
                    "direction": "|".join(self.causal_relations),
                    "review_cadence": "|".join(self.review_cadences),
                    "start_date_alias": "exact allowed date alias or NONE",
                    "review_date_alias": "exact allowed date alias or NONE",
                    "expected_claim_transition": "|".join(
                        self.expected_transitions
                    ),
                }
            ],
        }

    def provider_system_instruction(self, segment_id: str) -> str:
        self._consumer_binding("prompt")
        instruction = (
            "Return exactly one native JSON object matching "
            "required_output_schema. Emit only exact request-local aliases "
            "and closed enum values listed in "
            "compiled_judgment_atom_contract. Do not emit final prose, "
            "material numbers, periods, thresholds, calendar dates, case "
            "identity, canonical IDs, raw refs, lineage, markdown, or extra "
            "fields. The local deterministic planner owns validation, "
            "selection, ordering, rendering, and final cardinality."
        )
        if (
            self.family_id(segment_id) == self.family_ids[1]
            and self.claim_epistemic_support_role_v2
        ):
            rule = self.claim_kind_support_role_contract()
            supported = ", ".join(
                rule["supported_judgment_kinds"]["claim_kinds"]
            )
            instruction += (
                " For claim_candidate_atoms, obey "
                "claim_kind_support_role_rules: claim_kind "
                "insufficient_evidence requires support_fact_aliases to be "
                "exactly []; claim_kind "
                f"{supported} requires one or more unique exact allowed fact "
                "aliases. When a selected fact boundary prevents a stronger "
                "inference, emit claim_kind evidence_direction with direction "
                "unknown or mixed and keep its support aliases; never emit "
                "insufficient_evidence with support aliases."
            )
        if self.family_id(segment_id) == self.family_ids[0]:
            instruction += (
                " For fact_atoms, return at least one and no more than the "
                "provider_candidate_maximum, selecting only from the already "
                "bounded allowed_supports pool. Do not recreate or infer hidden "
                "supports."
            )
        return instruction

    def compiled_surface(self, segment_id: str) -> dict[str, Any]:
        contract = self.model_visible_contract(segment_id)
        surface = {
            "contract_ref": self.contract_ref,
            "family_id": contract["family_id"],
            "model_visible_contract": contract,
            "wire_schema": self.wire_schema(segment_id),
            "local_validator": {
                "exact_top_level_shape": True,
                "request_local_alias_membership": True,
                "closed_enum_membership": True,
                "arbitrary_narrative_rejected": True,
                "every_candidate_validated_before_selection": True,
                "exact_duplicate_candidate_rejected": True,
            },
            "fake_provider_fixture": self.fake_provider_output(segment_id),
            "selector": {
                "validity_aware": True,
                "mixed_scope_rejected_before_selection": True,
                "stable_tie_break": True,
                "provider_candidate_maximum": contract.get(
                    "provider_candidate_maximum"
                ),
                "local_selected_maximum": contract.get(
                    "local_selected_maximum"
                ),
            },
            "renderer": {
                "local_deterministic_owner": True,
                "material_truth_provider_owned": False,
            },
            "capacity": self.capacity_declaration(segment_id),
            "budget": {
                "projected_input_unit": "estimated_input_tokens",
                "projected_output_unit": "reserved_output_tokens",
                "utf8_bytes_as_pricing_tokens": False,
            },
            "failure_descriptor": {
                "contract_ref": self.contract_ref,
                "phase": "post_provider_local_semantic_validation",
                "code": "s4_compiled_judgment_atom_contract_invalid",
                "family_id": contract["family_id"],
                "capture_preserved": True,
                "business_promotion_allowed": False,
            },
            "capture_safe_index_semantic_classes": [
                "family_id",
                "failure_code",
                "field_id",
                "failing_item_count",
                "provider_output_utf8_bytes",
                "capture_ref",
                "capture_digest",
            ],
        }
        if (
            contract["family_id"] == self.family_ids[1]
            and self.claim_epistemic_support_role_v2
        ):
            rule = self.claim_kind_support_role_contract()
            surface["local_validator"][
                "claim_kind_support_role_rules"
            ] = rule
            surface["selector"]["claim_kind_support_role_rules"] = rule
            surface["failure_descriptor"]["conditional_failure"] = {
                "rule_id": rule["rule_id"],
                "code": rule["invalid_failure_code"],
            }
        if contract["family_id"] == self.family_ids[0]:
            candidate_plan = self.fact_candidate_pool_plan()
            if candidate_plan is not None:
                surface["fact_candidate_pool_receipt"] = (
                    candidate_plan.safe_receipt()
                )
                surface["local_validator"].update(
                    {
                        "pre_provider_candidate_pool_bounded": True,
                        "hidden_support_alias_rejected": True,
                        "candidate_profile_digest_bound": True,
                    }
                )
        if self.runtime_contract_binding is not None:
            surface["runtime_contract_family_binding"] = (
                self.runtime_contract_binding_receipt()
            )
            surface["compiled_consumer_bindings"] = (
                self.runtime_contract_binding.all_consumer_receipts()
            )
        return surface

    def capacity_declaration(self, segment_id: str) -> dict[str, Any]:
        self._consumer_binding("capacity")
        family = self.family_id(segment_id)
        local_text: list[str] = []
        if family == self.family_ids[0]:
            for row in self._provider_fact_catalog():
                local_text.extend([row["statement"], row["boundary"]])
        elif family == self.family_ids[1]:
            local_text.extend(
                row.statement for row in self._claim_policy().alias_rows
            )
        else:
            local_text.extend(
                row.document_event_or_dataset
                for row in self._wwc_policy().authority_aliases
            )
        worst = max(map(len, local_text), default=0)
        if worst > self.local_item_max_unicode_characters:
            raise ValueError(
                "s4_compiled_atom_bound_catalog_item_capacity_exceeded"
            )
        declaration = {
            "provider_raw_output_max_utf8_bytes": (
                self.provider_output_max_utf8_bytes
            ),
            "local_rendered_item_max_unicode_characters": (
                self.local_item_max_unicode_characters
            ),
            "bound_catalog_worst_case_unicode_characters": worst,
            "provider_and_local_capacity_are_separate": True,
        }
        if self.runtime_contract_binding is not None:
            declaration["local_rendered_max_utf8_bytes"] = (
                self.local_rendered_max_utf8_bytes
            )
            declaration["consumer_binding"] = self._consumer_binding(
                "capacity"
            )
        return declaration

    @staticmethod
    def _exact_mapping(
        value: Any,
        expected_keys: set[str],
    ) -> Mapping[str, Any] | None:
        if isinstance(value, Mapping) and set(value) == expected_keys:
            return value
        return None

    @staticmethod
    def _validate_enum(
        atom: Mapping[str, Any],
        field_id: str,
        allowed: Sequence[str],
    ) -> None:
        if atom.get(field_id) not in allowed:
            raise ValueError(f"s4_compiled_atom_enum_invalid:{field_id}")

    def _assemble_facts(self, output: Mapping[str, Any]) -> dict[str, Any]:
        if set(output) != {
            "program_cell_id",
            "fact_atoms",
            "terminal_class",
        }:
            raise ValueError("s4_compiled_fact_atom_top_level_invalid")
        atoms = output.get("fact_atoms")
        if (
            output.get("program_cell_id") != self.program_cell_id
            or not isinstance(atoms, list)
            or not 1 <= len(atoms) <= self.provider_candidate_maximum
            or output.get("terminal_class")
            not in {"supported", "mixed", "insufficient"}
        ):
            raise ValueError("s4_compiled_fact_atom_shape_invalid")
        catalog = {
            row["alias"]: row for row in self._provider_fact_catalog()
        }
        expected = {
            "support_alias",
            "causal_relation",
            "materiality",
            "confidence",
            "priority",
        }
        valid: list[Mapping[str, Any]] = []
        observed: set[str] = set()
        for raw_atom in atoms:
            atom = self._exact_mapping(raw_atom, expected)
            if atom is None:
                raise ValueError("s4_compiled_fact_atom_shape_invalid")
            alias = str(atom.get("support_alias") or "")
            if alias not in catalog or alias in observed:
                raise ValueError(
                    "s4_compiled_fact_atom_alias_unknown_or_duplicate"
                )
            observed.add(alias)
            for field_id, allowed in (
                ("causal_relation", self.causal_relations),
                ("materiality", self.materialities),
                ("confidence", self.confidences),
                ("priority", self.priorities),
            ):
                self._validate_enum(atom, field_id, allowed)
            valid.append(atom)
        selected = sorted(
            valid,
            key=lambda atom: (
                self._priority_rank[str(atom["priority"])],
                self._materiality_rank[str(atom["materiality"])],
                self._confidence_rank[str(atom["confidence"])],
                str(atom["support_alias"]),
            ),
        )[: self.fact_selected_maximum]
        facts: list[dict[str, Any]] = []
        explanations: list[str] = []
        for ordinal, atom in enumerate(selected, 1):
            row = catalog[str(atom["support_alias"])]
            relation = self._relation_text[str(atom["causal_relation"])]
            support_type = (
                "Numeric"
                if str(atom["support_alias"]).startswith("N")
                else "Evidence"
            )
            statement = row["statement"]
            if support_type == "Numeric":
                statement = f"{statement}；该权威口径{relation}当前判断"
            facts.append(
                {
                    "fact_id": (
                        f"{self.program_cell_id}:local_fact:{ordinal:03d}"
                    ),
                    "statement": statement,
                    "support_type": support_type,
                    "support_refs": [row["authority_ref"]],
                    "boundary": row["boundary"],
                }
            )
            text = f"绑定权威事实{relation}当前判断"
            if text not in explanations:
                explanations.append(text)
        terminal = str(output["terminal_class"])
        gaps = {
            "supported": ["仍需持续核对新增反证与口径变化"],
            "mixed": ["当前证据方向混合，需补充独立权威证据"],
            "insufficient": ["当前绑定权威集合不足以形成更强结论"],
        }[terminal]
        return {
            "program_cell_id": self.program_cell_id,
            "fact_layer": facts,
            "explanation_layer": explanations or ["当前证据不足"],
            "remaining_gaps": gaps,
            "terminal_class": terminal,
        }

    def _claim_candidate_eligible(
        self,
        atom: Mapping[str, Any],
        aliases: Mapping[str, ClaimFactAlias],
    ) -> bool:
        values = atom.get("support_fact_aliases")
        if not isinstance(values, list):
            return False
        if atom.get("claim_kind") == "insufficient_evidence":
            return values == []
        if (
            not values
            or len(values) != len(set(map(str, values)))
            or any(value not in aliases for value in values)
        ):
            return False
        summaries: list[dict[str, str]] = []
        for value in values:
            scope = dict(
                aliases[str(value)].locally_assembled_scope_summary
            )
            if any(item == "mixed" for item in scope.values()):
                return False
            summaries.append(scope)
        for field_id in (
            "entity",
            "business_scope_kind",
            "business_scope",
            "period",
            "attribution_level",
        ):
            concrete = {
                scope.get(field_id, "unknown")
                for scope in summaries
                if scope.get(field_id, "unknown")
                not in {"unknown", "none"}
            }
            if len(concrete) > 1:
                return False
        return True

    def _claim_epistemic_support_role_valid(
        self,
        atom: Mapping[str, Any],
    ) -> bool:
        values = atom.get("support_fact_aliases")
        if not isinstance(values, list):
            return False
        if atom.get("claim_kind") == "insufficient_evidence":
            return values == []
        return bool(values) and len(values) == len(set(map(str, values)))

    def _assemble_claims(self, output: Mapping[str, Any]) -> dict[str, Any]:
        if set(output) != {"program_cell_id", "claim_candidate_atoms"}:
            raise ValueError("s4_compiled_claim_atom_top_level_invalid")
        atoms = output.get("claim_candidate_atoms")
        if (
            output.get("program_cell_id") != self.program_cell_id
            or not isinstance(atoms, list)
            or not 1 <= len(atoms) <= self.provider_candidate_maximum
        ):
            raise ValueError("s4_compiled_claim_atom_shape_invalid")
        aliases = {
            row.alias: row for row in self._claim_policy().alias_rows
        }
        expected = {
            "support_fact_aliases",
            "claim_kind",
            "direction",
            "materiality",
            "confidence",
            "priority",
        }
        eligible: list[Mapping[str, Any]] = []
        for raw_atom in atoms:
            atom = self._exact_mapping(raw_atom, expected)
            if atom is None:
                raise ValueError("s4_compiled_claim_atom_shape_invalid")
            for field_id, allowed in (
                ("claim_kind", self.claim_kinds),
                ("direction", self.causal_relations),
                ("materiality", self.materialities),
                ("confidence", self.confidences),
                ("priority", self.priorities),
            ):
                self._validate_enum(atom, field_id, allowed)
            support = atom.get("support_fact_aliases")
            if isinstance(support, list) and any(
                value not in aliases for value in support
            ):
                raise ValueError(
                    "s4_compiled_claim_atom_alias_unknown_or_cross_case"
                )
            if (
                self.claim_epistemic_support_role_v2
                and not self._claim_epistemic_support_role_valid(atom)
            ):
                raise ValueError(
                    "s4_compiled_claim_atom_"
                    "epistemic_support_role_invalid"
                )
            if self._claim_candidate_eligible(atom, aliases):
                eligible.append(atom)
        selected = sorted(
            eligible,
            key=lambda atom: (
                self._priority_rank[str(atom["priority"])],
                0
                if any(
                    aliases[str(alias)].support_type == "Evidence"
                    for alias in atom["support_fact_aliases"]
                )
                else 1,
                self._materiality_rank[str(atom["materiality"])],
                tuple(sorted(map(str, atom["support_fact_aliases"]))),
                str(atom["claim_kind"]),
            ),
        )[: self.claim_selected_maximum]
        if not selected:
            raise ValueError(
                "s4_compiled_claim_atom_no_valid_scope_compatible_subset"
            )
        claims: list[dict[str, Any]] = []
        for ordinal, atom in enumerate(selected, 1):
            support = list(map(str, atom["support_fact_aliases"]))
            cannot_infer = atom["claim_kind"] == "insufficient_evidence"
            kind = self._claim_kind_text[str(atom["claim_kind"])]
            relation = self._relation_text[str(atom["direction"])]
            boundaries = sorted(
                {
                    aliases[value].boundary
                    for value in support
                    if aliases[value].boundary.strip()
                }
            )
            claims.append(
                {
                    "claim_id": (
                        f"{self.program_cell_id}:local_claim:{ordinal:03d}"
                    ),
                    "statement": (
                        f"{kind}{relation}当前单元判断；详见本地绑定事实"
                    ),
                    "epistemic_status": (
                        "cannot_infer"
                        if cannot_infer
                        else "fact_supported"
                        if atom["direction"] in {"supports", "challenges"}
                        else "bounded_inference"
                    ),
                    "support_fact_aliases": support,
                    "context_refs": [],
                    "scope": {"metric_or_mechanism": kind},
                    "qualification": "",
                    "cannot_support": (
                        ["当前绑定事实不足以支持更强结论"]
                        if cannot_infer
                        else boundaries
                    ),
                }
            )
        return {
            "program_cell_id": self.program_cell_id,
            "judgment_layer": claims,
        }

    def _review_text(
        self,
        *,
        cadence: str,
        alias: str,
        policy: SpecialistWWCJudgmentAtomPolicy,
    ) -> str:
        if cadence == "bound_date":
            try:
                return policy.alias_to_iso_date[alias]
            except KeyError as exc:
                raise ValueError(
                    "s4_compiled_wwc_date_alias_unknown"
                ) from exc
        if alias != "NONE":
            raise ValueError("s4_compiled_wwc_unbound_date_alias_forbidden")
        return {
            "next_authority_event": "next authority event",
            "next_reporting_event": "next reporting event",
            "next_month_end": "next month end",
            "next_quarter_end": "next quarter end",
            "unscheduled": "unscheduled",
        }[cadence]

    def _assemble_wwc(self, output: Mapping[str, Any]) -> dict[str, Any]:
        if set(output) != {"program_cell_id", "what_would_change_atoms"}:
            raise ValueError("s4_compiled_wwc_atom_top_level_invalid")
        atoms = output.get("what_would_change_atoms")
        if (
            output.get("program_cell_id") != self.program_cell_id
            or not isinstance(atoms, list)
            or not 1 <= len(atoms) <= self.provider_candidate_maximum
        ):
            raise ValueError("s4_compiled_wwc_atom_shape_invalid")
        policy = self._wwc_policy()
        claims = policy.claim_policy.alias_to_claim_id
        claim_rows = {
            row.alias: row for row in policy.claim_policy.alias_rows
        }
        authorities = policy.alias_to_authority
        expected = {
            "claim_alias",
            "primary_authority_alias",
            "authority_aliases",
            "trigger_code",
            "direction",
            "review_cadence",
            "start_date_alias",
            "review_date_alias",
            "expected_claim_transition",
        }
        valid: list[dict[str, Any]] = []
        observed_candidates: set[str] = set()
        for provider_ordinal, raw_atom in enumerate(atoms, 1):
            atom = self._exact_mapping(raw_atom, expected)
            if atom is None:
                raise ValueError("s4_compiled_wwc_atom_shape_invalid")
            for field_id, allowed in (
                ("trigger_code", self.trigger_codes),
                ("direction", self.causal_relations),
                ("review_cadence", self.review_cadences),
                (
                    "expected_claim_transition",
                    self.expected_transitions,
                ),
            ):
                self._validate_enum(atom, field_id, allowed)
            claim_alias = str(atom["claim_alias"])
            primary_alias = str(atom["primary_authority_alias"])
            authority_aliases = atom.get("authority_aliases")
            if claim_alias not in claims:
                raise ValueError(
                    "s4_compiled_wwc_claim_alias_unknown_or_cross_case"
                )
            if (
                primary_alias not in authorities
                or not isinstance(authority_aliases, list)
                or not authority_aliases
                or primary_alias not in authority_aliases
                or len(authority_aliases)
                != len(set(map(str, authority_aliases)))
                or any(alias not in authorities for alias in authority_aliases)
            ):
                raise ValueError(
                    "s4_compiled_wwc_authority_alias_invalid"
                )
            start_alias = str(atom["start_date_alias"])
            if start_alias == "NONE":
                start = "when bound rule condition is met"
            elif start_alias in policy.alias_to_iso_date:
                start = policy.alias_to_iso_date[start_alias]
            else:
                raise ValueError(
                    "s4_compiled_wwc_start_date_alias_unknown"
                )
            review = self._review_text(
                cadence=str(atom["review_cadence"]),
                alias=str(atom["review_date_alias"]),
                policy=policy,
            )
            normalized_atom = {
                **dict(atom),
                "authority_aliases": sorted(
                    map(str, authority_aliases)
                ),
            }
            candidate_digest = canonical_digest(normalized_atom)
            if candidate_digest in observed_candidates:
                raise ValueError(
                    "s4_compiled_wwc_atom_exact_duplicate"
                )
            observed_candidates.add(candidate_digest)
            primary = authorities[primary_alias]
            trigger = str(atom["trigger_code"])
            direction = self._relation_text[str(atom["direction"])]
            valid.append(
                {
                    "atom": normalized_atom,
                    "provider_ordinal": provider_ordinal,
                    "candidate_digest": candidate_digest,
                    "start": start,
                    "review": review,
                    "primary": primary,
                    "trigger": trigger,
                    "direction": direction,
                }
            )

        selected = sorted(
            valid,
            key=lambda row: (
                self._claim_epistemic_priority_rank[
                    claim_rows[str(row["atom"]["claim_alias"])]
                    .epistemic_status
                ],
                self._authority_specificity_rank.get(
                    row["primary"].authority_kind, 99
                ),
                self._trigger_actionability_rank[
                    str(row["atom"]["trigger_code"])
                ],
                self._review_cadence_rank[
                    str(row["atom"]["review_cadence"])
                ],
                self._expected_transition_rank[
                    str(row["atom"]["expected_claim_transition"])
                ],
                str(row["candidate_digest"]),
                int(row["provider_ordinal"]),
            ),
        )[: self.wwc_selected_maximum]

        tasks: list[dict[str, Any]] = []
        for ordinal, row in enumerate(selected, 1):
            atom = row["atom"]
            primary = row["primary"]
            trigger = str(row["trigger"])
            direction = str(row["direction"])
            tasks.append(
                {
                    "task_id": (
                        f"{self.program_cell_id}:what_would_change:"
                        f"{ordinal:03d}"
                    ),
                    "claim_id": claims[claim_alias],
                    "source_target": primary.source_target(),
                    "metric_or_observation": (
                        primary.document_event_or_dataset
                    ),
                    "decision_rule": {
                        "rule_type": self._trigger_to_rule[trigger],
                        "comparator_or_condition": (
                            self._trigger_text[trigger]
                        ),
                        "threshold_or_observation": (
                            f"绑定权威观察{direction}当前判断"
                        ),
                    },
                    "time_window": {
                        "as_of": self.as_of,
                        "start_or_trigger": row["start"],
                        "deadline_or_review_date": row["review"],
                    },
                    "expected_claim_transition": self._transition_text[
                        str(atom["expected_claim_transition"])
                    ],
                    "fallback_stop_condition": (
                        "若绑定权威来源未出现可验证变化则保留当前边界"
                    ),
                    "authority_refs": [
                        authorities[str(alias)].authority_ref
                        for alias in sorted(map(str, authority_aliases))
                    ],
                }
            )
        return {
            "program_cell_id": self.program_cell_id,
            "what_would_change": tasks,
        }

    def assemble(
        self,
        segment_id: str,
        output: Mapping[str, Any],
        *,
        provider_output_utf8_bytes: int,
    ) -> dict[str, Any]:
        for consumer_id in (
            "local_validator",
            "selector",
            "renderer",
            "capacity",
            "budget",
        ):
            self._consumer_binding(consumer_id)
        if (
            type(provider_output_utf8_bytes) is not int
            or provider_output_utf8_bytes <= 0
            or provider_output_utf8_bytes
            > self.provider_output_max_utf8_bytes
        ):
            raise ValueError(
                "s4_compiled_atom_provider_output_capacity_invalid"
            )
        family = self.family_id(segment_id)
        if family == self.family_ids[0]:
            return self._assemble_facts(output)
        if family == self.family_ids[1]:
            return self._assemble_claims(output)
        return self._assemble_wwc(output)

    def assert_rendered_capacity(
        self,
        segment_id: str,
        output: Mapping[str, Any],
        *,
        post_local_expansion_limit_utf8_bytes: int,
    ) -> None:
        self._consumer_binding("capacity")
        self._consumer_binding("budget")
        self.capacity_declaration(segment_id)
        serialized = json.dumps(
            dict(output),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        effective_limit = post_local_expansion_limit_utf8_bytes
        if self.runtime_contract_binding is not None:
            effective_limit = min(
                effective_limit,
                self.local_rendered_max_utf8_bytes,
            )
        if len(serialized) > effective_limit:
            raise ValueError(
                "s4_compiled_atom_local_rendered_segment_capacity_exceeded"
            )
        if any(
            len(text) > self.local_item_max_unicode_characters
            for text in self._walk_text(output)
        ):
            raise ValueError(
                "s4_compiled_atom_local_rendered_item_capacity_exceeded"
            )

    @classmethod
    def _walk_text(cls, value: Any) -> list[str]:
        found: list[str] = []
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, Mapping):
            for child in value.values():
                found.extend(cls._walk_text(child))
        elif isinstance(value, (list, tuple)):
            for child in value:
                found.extend(cls._walk_text(child))
        return found

    def fake_provider_output(self, segment_id: str) -> dict[str, Any]:
        self._consumer_binding("fake_provider")
        family = self.family_id(segment_id)
        if family == self.family_ids[0]:
            catalog = self._provider_fact_catalog()
            if not catalog:
                raise ValueError("s4_compiled_atom_fake_catalog_empty")
            return {
                "program_cell_id": self.program_cell_id,
                "fact_atoms": [
                    {
                        "support_alias": catalog[0]["alias"],
                        "causal_relation": "supports",
                        "materiality": "high",
                        "confidence": "high",
                        "priority": "high",
                    }
                ],
                "terminal_class": "supported",
            }
        if family == self.family_ids[1]:
            aliases = self._claim_policy().alias_rows
            if not aliases:
                raise ValueError("s4_compiled_atom_fake_catalog_empty")
            if self.claim_epistemic_support_role_v2:
                return {
                    "program_cell_id": self.program_cell_id,
                    "claim_candidate_atoms": [
                        {
                            "support_fact_aliases": [aliases[0].alias],
                            "claim_kind": "evidence_direction",
                            "direction": "unknown",
                            "materiality": "high",
                            "confidence": "high",
                            "priority": "high",
                        },
                        {
                            "support_fact_aliases": [],
                            "claim_kind": "insufficient_evidence",
                            "direction": "unknown",
                            "materiality": "medium",
                            "confidence": "medium",
                            "priority": "normal",
                        },
                    ],
                }
            return {
                "program_cell_id": self.program_cell_id,
                "claim_candidate_atoms": [
                    {
                        "support_fact_aliases": [aliases[0].alias],
                        "claim_kind": "evidence_direction",
                        "direction": "supports",
                        "materiality": "high",
                        "confidence": "high",
                        "priority": "high",
                    }
                ],
            }
        policy = self._wwc_policy()
        if not policy.claim_policy.alias_rows or not policy.authority_aliases:
            raise ValueError("s4_compiled_atom_fake_catalog_empty")
        claim_alias = policy.claim_policy.alias_rows[0].alias
        authority_alias = policy.authority_aliases[0].alias
        patterns = (
            (
                "authority_contradiction",
                "challenges",
                "next_authority_event",
                "weaken",
            ),
            (
                "authority_confirmation",
                "supports",
                "next_reporting_event",
                "strengthen",
            ),
            (
                "bounded_event_occurs",
                "mixed",
                "next_month_end",
                "resolve_cannot_infer",
            ),
            (
                "trend_persists",
                "unknown",
                "next_quarter_end",
                "no_change",
            ),
            (
                "authority_contradiction",
                "challenges",
                "unscheduled",
                "invalidate",
            ),
            (
                "authority_confirmation",
                "supports",
                "next_quarter_end",
                "strengthen",
            ),
        )
        return {
            "program_cell_id": self.program_cell_id,
            "what_would_change_atoms": [
                {
                    "claim_alias": claim_alias,
                    "primary_authority_alias": authority_alias,
                    "authority_aliases": [authority_alias],
                    "trigger_code": trigger,
                    "direction": direction,
                    "review_cadence": cadence,
                    "start_date_alias": "NONE",
                    "review_date_alias": "NONE",
                    "expected_claim_transition": transition,
                }
                for trigger, direction, cadence, transition in patterns
            ],
        }
