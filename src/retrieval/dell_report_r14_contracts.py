from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from .dell_report_r14_common import (
    DellReportR14ContractError,
    canonical_digest,
    canonical_json_bytes,
    file_sha256,
    read_json,
    repository_root,
    require,
    require_identifier,
    require_sha256,
    resolve_repo_relative_path,
    sha256_bytes,
    TARGET_IDS,
    validate_result_digest,
)


GRAMMAR_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_r14_structural_proof_grammar_v1_0.json"
)
TOPOLOGY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_r14_target_topology_contract_v1_0.json"
)
LIFECYCLE_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_r14_lifecycle_transition_table_v1_0.json"
)
REQUIREMENT_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_r14_requirement_manifest_v1_0.json"
)

RULE_IDS = (
    "G00-MALFORMED",
    "G10-SENTENCE",
    "G11-HARD-CLAUSE",
    "G20-EXPLICIT-EVENT",
    "G21-COORD-EVENT",
    "G22-OBJECT-LIST",
    "G23-SUBJECT-INHERIT",
    "G30-ROLE-LOCAL",
    "G31-TEMPORAL-LOCAL",
    "G40-NOMINAL-HEAD",
    "G50-PRICE-DIRECT",
    "G51-PRICE-NOMINAL",
    "G52-HARDWARE-BUNDLE",
    "G90-CONFLICT",
)

PROOF_STATES = ("PROVED", "AMBIGUOUS", "UNSUPPORTED", "MALFORMED")

EXPECTED_NORMALIZATION = {
    "proof_form": ["NFKC", "casefold", "frozen_punctuation_class_map"],
    "punctuation_class_map": {
        "\u2010": "-",
        "\u2011": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    },
}

EXPECTED_TOKENIZER = {
    "longest_match": True,
    "priority": ["MONEY", "PERCENT", "NUMBER", "WORD", "PUNCT", "WHITESPACE"],
    "priority_collision_state": "MALFORMED",
    "word_internal_joiners": ["-", "'"],
    "word_joiner_requires_word_on_both_sides": True,
}

EXPECTED_SCOPE = {
    "paragraph_boundary": "newline",
    "hard_boundary_surface": [".", "?", "!", ";", ":", "\u2014"],
    "soft_coordinators": ["and", "but", "or", "while", "whereas", "then", "yet"],
    "parenthetical_pairs": ["()", "[]", "{}"],
    "quotation_pairs": ['""', "''", "\u201c\u201d", "\u2018\u2019"],
    "cross_hard_scope_material_edges": "forbidden_unless_target_contract_bridge",
}

EXPECTED_STRUCTURAL_RESOURCES = {
    "auxiliaries": [
        "am", "are", "be", "been", "being", "can", "could", "did", "do",
        "does", "had", "has", "have", "is", "may", "might", "must", "shall",
        "should", "was", "were", "will", "would",
    ],
    "finite_or_participle_suffixes": ["ed", "en", "es", "ing", "s"],
    "irregular_finite_forms": [
        "became", "began", "bought", "brought", "built", "came", "did",
        "fell", "grew", "had", "made", "ran", "rose", "said", "sold",
        "took", "was", "went", "were", "won", "wrote",
    ],
    "subject_pronouns": ["he", "i", "it", "she", "they", "we", "you"],
    "function_words": [
        "a", "an", "as", "at", "by", "for", "from", "in", "of", "on", "the",
        "to", "with",
    ],
    "resource_use": "event_barrier_or_structural_premise_only_never_target_truth",
}

EXPECTED_VOCABULARY_USE_MATRIX = {
    "target_entity_product_measure_ontology": {
        "allowed": ["candidate_discovery", "mention_typing"],
        "forbidden": ["event_split", "role_ownership", "complete_or_negative"],
    },
    "target_predicate_ontology": {
        "allowed": ["event_semantic_label", "candidate_discovery"],
        "forbidden": ["event_scope_existence", "cross_event_merge", "complete"],
    },
    "structural_function_resources": {
        "allowed": ["structural_premise", "conservative_event_barrier"],
        "forbidden": ["target_meaning", "complete"],
    },
    "company_verb_service_connector_lists": {
        "allowed": ["provenance", "positive_typing"],
        "forbidden": [
            "event_barrier",
            "priced_head",
            "complete_partial_or_negative",
        ],
    },
    "unknown_nonce_head_link_owner": {
        "allowed": ["node_creation", "ambiguity_proof"],
        "forbidden": ["denylist_negative", "absence_from_denylist_complete"],
    },
}

EXPECTED_LIFECYCLE_SEMANTICS_DIGEST = (
    "7b471f46fefe07e1d2352df305c8b42d8077e1a0ca1b36c1dd5caa71cccacb0a"
)

REQUIREMENT_FROZEN_SEMANTIC_FIELDS = (
    "authority",
    "finding_registry",
    "evidence_separation_contract",
    "positive_controls",
    "critical_operator_families",
    "r17_report_quality_carry_forward",
    "TokenBudgetBasis",
    "implementation_changed_path_allowlist",
    "forbidden_in_implementation_commit",
    "hard_stops",
)

EXPECTED_REQUIREMENT_FROZEN_SEMANTICS_DIGEST = (
    "aa0089b811a50a5edf43d4ea5789bc626dba1a2a2f0dd11b7817e6285c520f9f"
)


EXPECTED_RULE_SPECS = {
    "G00-MALFORMED": (0, ("input_key_is_pre_registered_malformed_or_token_priority_collides",), "terminal_typed_malformed", "MALFORMED"),
    "G10-SENTENCE": (10, ("sentence_or_paragraph_boundary_outside_nested_scope",), "new_hard_scope", "PROVED"),
    "G11-HARD-CLAUSE": (11, ("hard_boundary_surface_outside_nested_scope",), "material_roles_cannot_cross_boundary", "PROVED"),
    "G20-EXPLICIT-EVENT": (20, ("finite_auxiliary_or_morphological_predicate_candidate_has_exact_span",), "new_event_candidate", "PROVED"),
    "G21-COORD-EVENT": (21, ("coordinator_right_side_has_predicate_candidate_or_new_subject_or_nonce_head_cannot_be_excluded", "G22_no_new_event_proof_absent"), "new_event_or_ambiguous_event_barrier", "AMBIGUOUS"),
    "G22-OBJECT-LIST": (22, ("left_and_right_items_share_one_typed_role_slot", "no_subject_auxiliary_predicate_or_hard_boundary_between_items", "no_independent_event_complement_after_right_item"), "no_new_event_object_list", "PROVED"),
    "G23-SUBJECT-INHERIT": (23, ("coordinated_events", "left_event_has_explicit_subject", "right_event_has_no_competing_explicit_subject"), "copy_actor_edge_only", "PROVED"),
    "G30-ROLE-LOCAL": (30, ("directed_role_proof_edge_exists_within_event_local_scope",), "material_mention_owned_by_event", "PROVED"),
    "G31-TEMPORAL-LOCAL": (31, ("period_and_event_share_clause_without_competing_event_or_each_event_has_independent_edge",), "period_owned_by_event", "PROVED"),
    "G40-NOMINAL-HEAD": (40, ("directed_chunk_complement_relative_participial_apposition_or_coordination_edge_has_exact_endpoints",), "nominal_path_candidate_preserving_all_competing_heads", "PROVED"),
    "G50-PRICE-DIRECT": (50, ("single_pricing_event", "single_product_or_hardware_object", "single_price_complement", "no_competing_head_event_owner_or_price"), "unique_priced_hardware_path", "PROVED"),
    "G51-PRICE-NOMINAL": (51, ("product_priced_at_price_or_explicit_price_cost_of_for_product_copular_amount", "single_directed_path", "no_competing_head_event_owner_or_price"), "unique_priced_hardware_path", "PROVED"),
    "G52-HARDWARE-BUNDLE": (52, ("all_bundle_members_are_typed_hardware_or_configuration", "bounded_total_price", "single_event_and_single_path"), "unique_priced_hardware_bundle_path", "PROVED"),
    "G90-CONFLICT": (90, ("multiple_event_owner_head_price_or_path_or_unclosed_required_path",), "material_proof_conflict_preempts_complete", "AMBIGUOUS"),
}

EXPECTED_TOPOLOGY_OUTCOME_PRECEDENCE = [
    "MALFORMED_TO_E",
    "CANDIDATE_WITH_CONFLICT_MISSING_AMBIGUOUS_OR_UNSUPPORTED_TO_P",
    "CANDIDATE_WITH_ALL_REQUIRED_PROVED_TO_C",
    "NO_CANDIDATE_TO_N",
]

EXPECTED_GRAPH_REGISTRY_DIGEST = (
    "0248126b03a448bd103bb661953245deb21f2a810a3c6d2b3001a3b1cb6e4c1e"
)

EXPECTED_TARGET_SEMANTIC_DIGESTS = {
    "DELL-RSQ-03A-TARGET-ASP": "d881760ab2b37e4f7a341bfacfc414e133668976d8126b16c72d980cb7537229",
    "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH": "3cd02c06f3067a589932eb06f58a18585b68f470dbf3d6f3cdb018bab7357fd9",
    "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE": "29547053785b53cff11ff5908c3aaf4d920b4b2a6a0b3bf32acd541b67d1d986",
    "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD": "cd415b5a208be0eca7e6d6bd2fa14e884fdbe2c2ce554fb1add0cd5f46c32113",
    "DELL-RSQ-03A-TARGET-HBM-SUPPLY": "679bf338a45f500c1e7e43693015719b941a3c9eed55167791fcd2b5f45b5123",
    "DELL-RSQ-03A-TARGET-UNITS": "b5fb34c1e1796707e84ed0a626a7280d33387dba0c76d30f8347dbdb2621e9da",
}


@dataclass(frozen=True)
class R14ContractBundle:
    requirement: Mapping[str, Any]
    grammar: Mapping[str, Any]
    topology: Mapping[str, Any]
    lifecycle: Mapping[str, Any]

    @property
    def target_by_id(self) -> dict[str, Mapping[str, Any]]:
        return {
            str(row["target_id"]): row
            for row in self.topology["targets"]
        }


def _expect_exact_keys(
    value: Mapping[str, Any], expected: set[str], *, code: str
) -> None:
    require(set(value) == expected, f"{code}_keys_invalid")


def validate_structural_proof_grammar(value: Mapping[str, Any]) -> None:
    validate_result_digest(value, code="R14_grammar")
    _expect_exact_keys(
        value,
        {
            "schema_version",
            "grammar_id",
            "parser_id",
            "span_contract",
            "normalization",
            "proof_states",
            "tokenizer",
            "scope",
            "structural_resources",
            "resource_versions",
            "rules",
            "deterministic_procedure",
            "outcome_mapping",
            "vocabulary_use_matrix",
            "result_digest",
        },
        code="R14_grammar",
    )
    require(
        value.get("schema_version")
        == "fin_ia_dell_03B_R14_structural_proof_grammar_v1_0",
        "R14_grammar_schema_invalid",
    )
    require(
        value.get("grammar_id")
        == "FIN-0.1.3-S1-DELL-03B-R14-STRUCTURAL-PROOF-GRAMMAR-V1"
        and value.get("parser_id") == "conservative_event_proof_v1",
        "R14_grammar_identity_invalid",
    )
    require(
        tuple(value.get("proof_states") or ()) == PROOF_STATES,
        "R14_grammar_proof_states_invalid",
    )
    span = dict(value.get("span_contract") or {})
    require(
        span
        == {
            "coordinate_system": "unicode_code_point",
            "interval": "half_open_start_inclusive_end_exclusive",
            "raw_text_rewritten": False,
            "raw_span_rewritten": False,
        },
        "R14_grammar_span_contract_invalid",
    )
    require(
        value.get("normalization") == EXPECTED_NORMALIZATION,
        "R14_grammar_normalization_invalid",
    )
    tokenizer = dict(value.get("tokenizer") or {})
    require(tokenizer == EXPECTED_TOKENIZER, "R14_grammar_tokenizer_invalid")
    require(value.get("scope") == EXPECTED_SCOPE, "R14_grammar_scope_invalid")
    structural = dict(value.get("structural_resources") or {})
    require(
        structural == EXPECTED_STRUCTURAL_RESOURCES,
        "R14_grammar_structural_resources_invalid",
    )
    resources = dict(value.get("resource_versions") or {})
    _expect_exact_keys(
        resources,
        {"abbreviation_policy", "function_word_resource"},
        code="R14_grammar_resources",
    )
    abbreviation = dict(resources.get("abbreviation_policy") or {})
    function_words = dict(resources.get("function_word_resource") or {})
    _expect_exact_keys(
        abbreviation,
        {"resource_id", "entries", "entries_digest"},
        code="R14_grammar_abbreviation_resource",
    )
    _expect_exact_keys(
        function_words,
        {"resource_id", "entries_digest"},
        code="R14_grammar_function_word_resource",
    )
    require(
        abbreviation.get("resource_id")
        == "R14_abbreviation_boundary_exceptions_v1"
        and abbreviation.get("entries")
        == ["Co.", "Corp.", "Inc.", "Ltd.", "No.", "U.K.", "U.S.", "e.g.", "i.e.", "vs."]
        and canonical_digest(abbreviation.get("entries"))
        == abbreviation.get("entries_digest"),
        "R14_grammar_abbreviation_resource_invalid",
    )
    require(
        function_words.get("resource_id") == "R14_structural_function_words_v1"
        and canonical_digest(structural.get("function_words"))
        == function_words.get("entries_digest"),
        "R14_grammar_function_word_resource_invalid",
    )
    rules = list(value.get("rules") or ())
    require(
        tuple(str(row.get("rule_id") or "") for row in rules) == RULE_IDS,
        "R14_grammar_rule_population_or_order_invalid",
    )
    precedence = [int(row.get("precedence")) for row in rules]
    require(
        len(precedence) == len(set(precedence))
        and precedence == sorted(precedence),
        "R14_grammar_rule_precedence_invalid",
    )
    for row in rules:
        _expect_exact_keys(
            row,
            {"rule_id", "precedence", "premises", "conclusion", "state"},
            code=f"R14_grammar_rule_{row.get('rule_id')}",
        )
        expected = EXPECTED_RULE_SPECS[str(row.get("rule_id"))]
        observed = (
            row.get("precedence"),
            tuple(row.get("premises") or ()),
            row.get("conclusion"),
            row.get("state"),
        )
        require(
            observed == expected,
            f"R14_grammar_rule_semantics_invalid:{row.get('rule_id')}",
        )
    require(
        value.get("deterministic_procedure")
        == [
            "TOKENIZE",
            "SCOPE",
            "EVENT_CANDIDATES",
            "OBJECT_LIST",
            "SUBJECT_TIME",
            "NOMINAL",
            "PRICE",
            "TARGET",
        ],
        "R14_grammar_procedure_invalid",
    )
    outcome = dict(value.get("outcome_mapping") or {})
    require(
        outcome
        == {
            "no_target_candidate": "N",
            "candidate_all_required_proofs_PROVED_no_conflict": "C",
            "candidate_missing_AMBIGUOUS_or_UNSUPPORTED_proof": "P",
            "pre_registered_malformed_key_and_closed_code": "E",
            "uncaught_parser_or_compiler_exception": "TERMINAL_EXECUTION_FAILURE",
        },
        "R14_grammar_outcome_mapping_invalid",
    )
    matrix = dict(value.get("vocabulary_use_matrix") or {})
    require(
        set(matrix)
        == {
            "target_entity_product_measure_ontology",
            "target_predicate_ontology",
            "structural_function_resources",
            "company_verb_service_connector_lists",
            "unknown_nonce_head_link_owner",
        },
        "R14_grammar_vocabulary_matrix_population_invalid",
    )
    for name, row in matrix.items():
        require(
            set(row) == {"allowed", "forbidden"}
            and bool(row["allowed"])
            and bool(row["forbidden"]),
            f"R14_grammar_vocabulary_matrix_row_invalid:{name}",
        )
    require(
        matrix == EXPECTED_VOCABULARY_USE_MATRIX,
        "R14_grammar_vocabulary_matrix_semantics_invalid",
    )


def _validate_graph_type_registry(value: Mapping[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "mention_node_types",
        "event_role_types",
        "nominal_relation_types",
        "event_types",
        "predicate_event_type_terms",
        "cardinality_enums",
        "proof_rule_ids",
        "target_mention_type_bindings",
        "target_edge_bindings",
        "bridge_types",
        "semantic_identity_contract",
        "typed_bridge_edge_contract",
        "compiler_input_contract",
    }
    _expect_exact_keys(value, expected_keys, code="R14_graph_type_registry")
    require(
        value.get("schema_version")
        == "fin_ia_dell_03B_R14_graph_type_registry_v1_0",
        "R14_graph_type_registry_schema_invalid",
    )
    require(
        canonical_digest(value) == EXPECTED_GRAPH_REGISTRY_DIGEST,
        "R14_graph_type_registry_semantics_invalid",
    )
    mention_types = tuple(value.get("mention_node_types") or ())
    role_types = tuple(value.get("event_role_types") or ())
    relation_types = tuple(value.get("nominal_relation_types") or ())
    event_types = tuple(value.get("event_types") or ())
    cardinalities = tuple(value.get("cardinality_enums") or ())
    for name, rows in (
        ("mention", mention_types),
        ("role", role_types),
        ("relation", relation_types),
        ("event", event_types),
        ("cardinality", cardinalities),
    ):
        require(
            bool(rows) and tuple(sorted(set(rows))) == rows,
            f"R14_graph_type_registry_{name}_population_invalid",
        )
    require(
        tuple(value.get("proof_rule_ids") or ()) == RULE_IDS,
        "R14_graph_type_registry_rule_binding_invalid",
    )
    require(
        value.get("semantic_identity_contract")
        == {
            "schema_version": "fin_ia_dell_03B_R14_semantic_identity_v1_0",
            "allowed_prefixes": [
                "BUNDLE::",
                "ENTITY::",
                "EVENT_TYPE::",
                "MEASURE::",
                "NOMINAL_HEAD::",
                "OPERATOR::",
                "PRODUCT::",
                "TARGET::",
            ],
            "contains_raw_or_normalized_surface": False,
            "mention_identity_recomputed_before_projection": True,
            "bridge_shared_identity_prefixes": ["ENTITY::", "PRODUCT::"],
        },
        "R14_graph_type_registry_semantic_identity_contract_invalid",
    )
    require(
        value.get("typed_bridge_edge_contract")
        == {
            "collection": "target_bridge_edges",
            "maximum_events_per_edge": 2,
            "same_local_scope_and_sentence": True,
            "adjacent_events_only": True,
            "proof_state": "PROVED",
            "proof_rule_id": "G30-ROLE-LOCAL",
            "identity_intersection_recomputed": True,
        },
        "R14_graph_type_registry_typed_bridge_contract_invalid",
    )
    predicate_event_types = dict(value.get("predicate_event_type_terms") or {})
    require(
        set(predicate_event_types).issubset(set(event_types))
        and "unknown" not in predicate_event_types
        and all(
            bool(terms) and tuple(sorted(set(terms))) == tuple(terms)
            for terms in predicate_event_types.values()
        ),
        "R14_graph_type_registry_predicate_event_types_invalid",
    )
    mention_bindings = dict(value.get("target_mention_type_bindings") or {})
    require(bool(mention_bindings), "R14_graph_type_registry_mention_bindings_empty")
    for declared, concrete in mention_bindings.items():
        require(
            bool(require_identifier(declared, field="target_mention_type"))
            and bool(concrete)
            and set(concrete).issubset(set(mention_types)),
            f"R14_graph_type_registry_mention_binding_invalid:{declared}",
        )
    edge_bindings = dict(value.get("target_edge_bindings") or {})
    edge_families = {
        "event_role": set(role_types),
        "nominal_relation": set(relation_types),
        "event_role_or_bridge": set(role_types) | {"typed_target_bridge"},
        "event_type": set(event_types),
        "temporal": {"period"},
    }
    for declared, binding in edge_bindings.items():
        require(
            set(binding) == {"edge_family", "allowed_types"}
            and binding.get("edge_family") in edge_families
            and bool(binding.get("allowed_types"))
            and set(binding["allowed_types"]).issubset(
                edge_families[str(binding["edge_family"])]
            ),
            f"R14_graph_type_registry_edge_binding_invalid:{declared}",
        )
    compiler = dict(value.get("compiler_input_contract") or {})
    require(
        compiler
        == {
            "view": "TargetGraphViewR14",
            "contains_raw_text": False,
            "contains_token_surface": False,
            "allowed_inputs": [
                "typed_nodes",
                "typed_edges",
                "proofs",
                "digests",
                "target_topology_contract",
            ],
            "forbidden_inputs": [
                "raw_sentence",
                "regex_complete_rule",
                "R13_output",
                "preview_vector",
            ],
        },
        "R14_graph_type_registry_compiler_boundary_invalid",
    )


def validate_target_topology_contract(value: Mapping[str, Any]) -> None:
    validate_result_digest(value, code="R14_topology")
    _expect_exact_keys(
        value,
        {
            "schema_version",
            "contract_id",
            "grammar_ref",
            "grammar_result_digest",
            "ontology_authority",
            "outcome_precedence",
            "graph_type_registry",
            "targets",
            "result_digest",
        },
        code="R14_topology",
    )
    require(
        value.get("schema_version")
        == "fin_ia_dell_03B_R14_target_topology_contract_v1_0",
        "R14_topology_schema_invalid",
    )
    require(
        value.get("grammar_ref") == GRAMMAR_REF
        and value.get("grammar_result_digest")
        == "628f12fcf3df3be2dd922230ef152d5f2b67b30994a403df01425d5d13edf8a8",
        "R14_topology_grammar_binding_invalid",
    )
    require(
        value.get("ontology_authority")
        == "candidate_discovery_and_semantic_typing_only",
        "R14_topology_ontology_authority_invalid",
    )
    require(
        value.get("contract_id")
        == "FIN-0.1.3-S1-DELL-03B-R14-TARGET-TOPOLOGY-V1"
        and value.get("outcome_precedence")
        == EXPECTED_TOPOLOGY_OUTCOME_PRECEDENCE,
        "R14_topology_identity_or_outcome_precedence_invalid",
    )
    registry = dict(value.get("graph_type_registry") or {})
    _validate_graph_type_registry(registry)
    mention_bindings = dict(registry["target_mention_type_bindings"])
    edge_bindings = dict(registry["target_edge_bindings"])
    event_types = set(registry["event_types"])
    cardinalities = set(registry["cardinality_enums"])
    targets = list(value.get("targets") or ())
    actual_ids = [str(row.get("target_id") or "") for row in targets]
    require(
        len(actual_ids) == len(set(actual_ids)) == len(TARGET_IDS)
        and set(actual_ids) == set(TARGET_IDS),
        "R14_topology_target_population_invalid",
    )
    for target in targets:
        target_id = str(target["target_id"])
        expected_target_keys = {
            "target_id",
            "target_proposition",
            "candidate_ontology",
            "required_roles",
            "event_cardinality",
            "allowed_bridges",
            "forbidden_inference",
            "positive_family_fingerprints",
        }
        if target_id == "DELL-RSQ-03A-TARGET-ASP":
            expected_target_keys.add("required_price_proof_rules")
        _expect_exact_keys(
            target, expected_target_keys, code=f"R14_topology_target:{target_id}"
        )
        required = list(target.get("required_roles") or ())
        require(bool(required), f"R14_topology_required_roles_empty:{target_id}")
        role_ids = [str(row.get("role") or "") for row in required]
        require(
            len(role_ids) == len(set(role_ids))
            and all(role_ids),
            f"R14_topology_required_roles_invalid:{target_id}",
        )
        for role in required:
            role_keys = {
                "role",
                "mention_type",
                "edge",
                "event_local",
                "cardinality",
            }
            if "required_semantic_identity_ids" in role:
                role_keys.add("required_semantic_identity_ids")
            require(
                set(role) == role_keys
                and isinstance(role.get("event_local"), bool)
                and role.get("mention_type") in mention_bindings
                and role.get("edge") in edge_bindings
                and role.get("cardinality") in cardinalities,
                f"R14_topology_role_schema_invalid:{target_id}:{role.get('role')}",
            )
            required_identities = tuple(
                role.get("required_semantic_identity_ids") or ()
            )
            require(
                tuple(sorted(set(required_identities))) == required_identities
                and all(
                    any(identity.startswith(prefix) for prefix in registry["semantic_identity_contract"]["allowed_prefixes"])
                    for identity in required_identities
                ),
                f"R14_topology_role_semantic_identity_invalid:{target_id}:{role.get('role')}",
            )
        card = dict(target.get("event_cardinality") or {})
        require(
            set(card) == {"minimum", "maximum", "event_type"}
            and 1 <= int(card["minimum"]) <= int(card["maximum"]) <= 2
            and card.get("event_type") in event_types,
            f"R14_topology_event_cardinality_invalid:{target_id}",
        )
        ontology = dict(target.get("candidate_ontology") or {})
        require(
            set(ontology)
            == {"entity_terms", "product_terms", "predicate_terms", "measure_types"}
            and any(bool(ontology[key]) for key in ontology),
            f"R14_topology_candidate_ontology_invalid:{target_id}",
        )
        require(
            bool(target.get("forbidden_inference"))
            and bool(target.get("positive_family_fingerprints")),
            f"R14_topology_quality_boundary_invalid:{target_id}",
        )
        for bridge in target.get("allowed_bridges") or ():
            require(
                set(bridge)
                == {
                    "bridge_id",
                    "source_event_type",
                    "destination_event_type",
                    "shared_roles",
                    "direction",
                    "maximum_events",
                }
                and int(bridge["maximum_events"]) == 2
                and bool(bridge["shared_roles"])
                and bridge.get("bridge_id") in set(registry["bridge_types"])
                and bridge.get("source_event_type") in event_types
                and bridge.get("destination_event_type") in event_types,
                f"R14_topology_bridge_invalid:{target_id}",
            )
    by_id = {str(row["target_id"]): row for row in targets}
    require(
        by_id["DELL-RSQ-03A-TARGET-ASP"].get("event_cardinality", {}).get("maximum")
        == 1
        and by_id["DELL-RSQ-03A-TARGET-ASP"].get("required_price_proof_rules")
        == ["G50-PRICE-DIRECT", "G51-PRICE-NOMINAL", "G52-HARDWARE-BUNDLE"],
        "R14_topology_ASP_contract_invalid",
    )
    supplier_bridge = by_id["DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH"][
        "allowed_bridges"
    ][0]
    hbm_bridge = by_id["DELL-RSQ-03A-TARGET-HBM-SUPPLY"]["allowed_bridges"][0]
    require(
        supplier_bridge
        == {
            "bridge_id": "SUPPLIER_RELATIONSHIP_TO_DELIVERY",
            "source_event_type": "supplier_relationship",
            "destination_event_type": "delivery",
            "shared_roles": ["same_named_supplier", "same_Dell_entity_or_product"],
            "direction": "relationship_to_delivery",
            "maximum_events": 2,
        }
        and hbm_bridge
        == {
            "bridge_id": "HBM_STATE_TO_DELL",
            "source_event_type": "HBM_supply_state",
            "destination_event_type": "Dell_configuration_or_delivery",
            "shared_roles": ["same_HBM_product_or_supplier"],
            "direction": "upstream_state_to_Dell",
            "maximum_events": 2,
        },
        "R14_topology_declared_bridge_invalid",
    )
    for target_id, target in by_id.items():
        require(
            canonical_digest(target) == EXPECTED_TARGET_SEMANTIC_DIGESTS[target_id],
            f"R14_topology_target_semantics_invalid:{target_id}",
        )


def validate_lifecycle_transition_table(value: Mapping[str, Any]) -> None:
    validate_result_digest(value, code="R14_lifecycle")
    lifecycle_body = dict(value)
    lifecycle_body.pop("result_digest", None)
    require(
        value.get("schema_version")
        == "fin_ia_dell_03B_R14_lifecycle_transition_table_v1_0",
        "R14_lifecycle_schema_invalid",
    )
    states = list(value.get("states") or ())
    require(
        len(states) == len(set(states)) and value.get("initial_state") in states,
        "R14_lifecycle_states_invalid",
    )
    transitions = list(value.get("transitions") or ())
    keys = [(row.get("from"), row.get("event")) for row in transitions]
    require(
        len(keys) == len(set(keys)),
        "R14_lifecycle_transition_nonunique",
    )
    for row in transitions:
        require(
            set(row) == {"from", "event", "to", "attempt_consumed"}
            and row["from"] in states
            and row["to"] in states
            and isinstance(row["attempt_consumed"], bool),
            f"R14_lifecycle_transition_invalid:{row.get('from')}:{row.get('event')}",
        )
    route = {(row["from"], row["event"]): row["to"] for row in transitions}
    require(
        route.get(("PLAN_REVIEW_PENDING", "PLAN_REVIEW_PASS_AND_G_VALIDATED"))
        == "PLAN_FROZEN"
        and route.get(("PLAN_FROZEN", "FREEZE_IMPLEMENTATION_WITH_PARENT_G"))
        == "IMPLEMENTATION_FROZEN"
        and route.get(("PREFORMAL_REVIEW_PENDING", "PREFORMAL_REVIEW_FAIL"))
        == "PREFORMAL_FAIL_REVISION_REQUIRED"
        and route.get(
            ("PREFORMAL_FAIL_REVISION_REQUIRED", "FREEZE_SAME_R14_REVISED_IMPLEMENTATION")
        )
        == "IMPLEMENTATION_FROZEN"
        and route.get(("ATTEMPT_CONSUMED", "FORMAL_MATERIAL_FAIL"))
        == "R14_STOP_OWNER_DECISION_REQUIRED"
        and route.get(("POSTFORMAL_REVIEW_PENDING", "POSTFORMAL_MATERIAL_FAIL"))
        == "R14_STOP_OWNER_DECISION_REQUIRED",
        "R14_lifecycle_required_routes_invalid",
    )
    require(
        all(
            row["to"] != "R14_STOP_OWNER_DECISION_REQUIRED"
            for row in transitions
            if row["from"] in {
                "PLAN_REVIEW_PENDING",
                "PREFORMAL_REVIEW_PENDING",
                "PREFORMAL_FAIL_REVISION_REQUIRED",
            }
        ),
        "R14_lifecycle_pre_attempt_owner_stop_forbidden",
    )
    authority = dict(value.get("state_authority") or {})
    require(
        authority["PLAN_REVIEW_FAIL_REVISION_REQUIRED"]["owner_decision_required"]
        is False
        and authority["PREFORMAL_FAIL_REVISION_REQUIRED"]["owner_decision_required"]
        is False
        and authority["R14_STOP_OWNER_DECISION_REQUIRED"]["owner_decision_required"]
        is True,
        "R14_lifecycle_owner_decision_boundary_invalid",
    )
    require(
        canonical_digest(lifecycle_body) == EXPECTED_LIFECYCLE_SEMANTICS_DIGEST,
        "R14_lifecycle_semantics_invalid",
    )


def validate_requirement_manifest(
    value: Mapping[str, Any], *, root: Path | None = None
) -> None:
    validate_result_digest(value, code="R14_requirement")
    root = root or repository_root()
    _expect_exact_keys(
        value,
        {
            "schema_version",
            "requirement_manifest_id",
            "program_id",
            "stage",
            "product_version",
            "authority",
            "plan_frozen_governance",
            "r13_frozen_predecessor",
            "immutable_inputs",
            "contract_bindings",
            "finding_registry",
            "evidence_separation_contract",
            "positive_controls",
            "critical_operator_families",
            "r17_report_quality_carry_forward",
            "TokenBudgetBasis",
            "implementation_changed_path_allowlist",
            "forbidden_in_implementation_commit",
            "hard_stops",
            "result_digest",
        },
        code="R14_requirement",
    )
    frozen_semantics = {
        field: value.get(field) for field in REQUIREMENT_FROZEN_SEMANTIC_FIELDS
    }
    require(
        canonical_digest(frozen_semantics)
        == EXPECTED_REQUIREMENT_FROZEN_SEMANTICS_DIGEST,
        "R14_requirement_frozen_semantics_invalid",
    )
    require(
        value.get("schema_version")
        == "fin_ia_dell_03B_R14_requirement_manifest_v1_0",
        "R14_requirement_schema_invalid",
    )
    authority = dict(value.get("authority") or {})
    require(
        authority.get("R14_implementation_and_T0_T1_T2_after_PLAN_FROZEN") is True
        and authority.get(
            "model_provider_network_external_embedding_4B_reranker_calls"
        )
        == 0
        and all(
            authority.get(key) is False
            for key in (
                "policy",
                "formal_attempt",
                "03C_external_routes",
                "Evidence_Pack_Readiness",
                "S2_S3_Writer_report",
                "qualified_human",
                "product_publication_release",
            )
        ),
        "R14_requirement_authority_invalid",
    )
    frozen = dict(value.get("plan_frozen_governance") or {})
    require(
        frozen.get("governance_commit")
        == "50fc4a706f00f40d831ec9624d33889180e1baa0"
        and frozen.get("governance_parent")
        == "ade8ebde4e6bca04de290eec6f8e46b55daee65e"
        and frozen.get("post_commit_PLAN_FROZEN_validation") == "PASS",
        "R14_requirement_PLAN_FROZEN_identity_invalid",
    )
    inputs = dict(value.get("immutable_inputs") or {})
    require(
        inputs.get("source_logical_decision_count") == 1888 * 6
        and inputs.get("compiled_logical_decision_count") == 34199 * 6
        and inputs.get("total_logical_decision_count") == (1888 + 34199) * 6,
        "R14_requirement_logical_counts_invalid",
    )
    bindings = list(value.get("contract_bindings") or ())
    require(
        [row.get("ref") for row in bindings]
        == [GRAMMAR_REF, TOPOLOGY_REF, LIFECYCLE_REF],
        "R14_requirement_contract_binding_population_invalid",
    )
    for row in bindings:
        path = resolve_repo_relative_path(root, row["ref"], field="contract_ref")
        require(path.is_file(), f"R14_requirement_contract_missing:{row['ref']}")
        require(
            file_sha256(path) == require_sha256(row.get("sha256"), field="binding"),
            f"R14_requirement_contract_SHA_mismatch:{row['ref']}",
        )
        bound = read_json(path)
        require(
            validate_result_digest(bound, code="R14_bound_contract")
            == row.get("result_digest"),
            f"R14_requirement_contract_digest_mismatch:{row['ref']}",
        )
    findings = list(value.get("finding_registry") or ())
    require(
        [row.get("severity") for row in findings]
        == ["P1", "P2", "P2", "P1", "P1", "P1", "P1", "P1", "P1", "P1", "P2"]
        and len({row.get("finding_id") for row in findings}) == 11,
        "R14_requirement_finding_registry_invalid",
    )
    expected_evidence_separation = {
        "schema_version": "fin_ia_dell_03B_R14_I_B_A_evidence_separation_v1_0",
        "implementation_I_allowed_content": [
            "machine_requirements",
            "contracts",
            "implementation",
            "tests",
        ],
        "implementation_I_forbidden_content": [
            "preview_or_test_runtime_receipt",
            "author_claimed_closure",
            "independent_audit_receipt",
            "formal_policy_or_attempt_artifact",
        ],
        "proof_B_required_content": [
            "post_freeze_layered_test_receipts",
            "post_freeze_zero_call_full_corpus_preview",
            "property_and_mutation_receipts",
            "resource_and_durability_receipts",
        ],
        "audit_A_required_content": [
            "fresh_no_fork_read_only_verdict",
            "exact_I_and_B_identity",
            "frozen_problem_set_regression_and_nonce_holdout",
            "P0_P1_P2_counts",
        ],
        "failure_evidence_residency": (
            "append_only_Project_OS_or_A_FAIL_not_mutable_I"
        ),
        "single_batch_stop_rule": (
            "new_material_finding_outside_frozen_root_families_stops_for_owner_decision"
        ),
        "automatic_R15_authorized": False,
    }
    require(
        value.get("evidence_separation_contract")
        == expected_evidence_separation,
        "R14_requirement_evidence_separation_invalid",
    )
    carry = dict(value.get("r17_report_quality_carry_forward") or {})
    require(
        carry.get("verdict") == "FAIL_GATE_OPEN_NOT_ASSESSABLE"
        and carry.get("reader_citation_binding") == "0_of_18"
        and carry.get("WWC") == "0_of_6"
        and carry.get("qualified_human") == "0_of_16",
        "R14_requirement_R17_carry_invalid",
    )
    budget = list(value.get("TokenBudgetBasis") or ())
    budget_keys = {
        "node",
        "purpose",
        "input_scale",
        "required_outputs",
        "schema_burden",
        "materiality_quality_risk",
        "comparable_run_evidence",
        "reasoning_profile",
        "stop_truncation_behavior",
        "model_provider_calls",
    }
    require(len(budget) == 4, "R14_requirement_TokenBudgetBasis_count_invalid")
    for row in budget:
        require(
            set(row) == budget_keys
            and row["model_provider_calls"] == 0
            and all(bool(str(row[key]).strip()) for key in budget_keys - {"model_provider_calls"}),
            f"R14_requirement_TokenBudgetBasis_invalid:{row.get('node')}",
        )
    require(
        value.get("implementation_changed_path_allowlist")
        == [
            "configs/retrieval/*r14*requirement*.json",
            "configs/retrieval/*r14*grammar*.json",
            "configs/retrieval/*r14*topology*.json",
            "configs/retrieval/*r14*lifecycle*.json",
            "src/retrieval/*r14*.py",
            "scripts/data_retrieval/*r14*.py",
            "tests/*r14*.py",
        ],
        "R14_requirement_implementation_allowlist_invalid",
    )


def verify_frozen_input_files(
    requirement: Mapping[str, Any], *, root: Path | None = None
) -> dict[str, int]:
    root = root or repository_root()
    inputs = dict(requirement.get("immutable_inputs") or {})
    output: dict[str, int] = {}
    for key in ("source_records", "compiled_objects"):
        binding = dict(inputs.get(key) or {})
        path = resolve_repo_relative_path(
            root, binding.get("ref"), field=f"{key}_ref"
        )
        require(path.is_file(), f"R14_{key}_missing")
        require(
            file_sha256(path) == require_sha256(binding.get("sha256"), field=key),
            f"R14_{key}_SHA_mismatch",
        )
        with path.open("rb") as handle:
            count = sum(1 for line in handle if line.strip())
        require(count == int(binding.get("count") or -1), f"R14_{key}_count_mismatch")
        output[key] = count
    return output


def _git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=root, stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as exc:
        raise DellReportR14ContractError(
            f"R14_git_command_failed:{' '.join(args)}:{exc.returncode}"
        ) from exc


def validate_plan_frozen_git(
    requirement: Mapping[str, Any], *, root: Path | None = None
) -> dict[str, Any]:
    root = root or repository_root()
    frozen = dict(requirement.get("plan_frozen_governance") or {})
    candidate = require_identifier(frozen.get("candidate_commit"), field="candidate")
    governance = require_identifier(frozen.get("governance_commit"), field="governance")
    parent = _git(root, "rev-parse", f"{governance}^").decode().strip()
    tree = _git(root, "rev-parse", f"{governance}^{{tree}}").decode().strip()
    require(parent == candidate, "R14_PLAN_FROZEN_G_parent_mismatch")
    require(tree == frozen.get("governance_tree"), "R14_PLAN_FROZEN_G_tree_mismatch")
    audit_ref = require_identifier(
        frozen.get("plan_audit_receipt_ref"), field="plan_audit_receipt_ref"
    )
    audit_raw = _git(root, "show", f"{governance}:{audit_ref}")
    audit = json.loads(audit_raw)
    require(
        validate_result_digest(audit, code="R14_plan_audit_receipt")
        == frozen.get("plan_audit_receipt_result_digest"),
        "R14_PLAN_FROZEN_receipt_digest_mismatch",
    )
    actual_paths = [
        line[2:]
        for line in _git(
            root, "diff-tree", "--no-commit-id", "--name-status", "-r", governance
        )
        .decode()
        .splitlines()
    ]
    expected_paths = audit["g_governance_contract"]["GChangedPathManifest"]
    require(actual_paths == expected_paths, "R14_PLAN_FROZEN_G_pathset_mismatch")
    plan_ref = require_identifier(frozen.get("plan_path"), field="plan_ref")
    candidate_plan = _git(root, "show", f"{candidate}:{plan_ref}")
    governance_plan = _git(root, "show", f"{governance}:{plan_ref}")
    require(candidate_plan == governance_plan, "R14_PLAN_FROZEN_plan_bytes_changed")
    require(
        len(governance_plan) == int(frozen.get("plan_bytes") or -1)
        and sha256_bytes(governance_plan) == frozen.get("plan_sha256")
        and _git(root, "rev-parse", f"{governance}:{plan_ref}").decode().strip()
        == frozen.get("plan_blob"),
        "R14_PLAN_FROZEN_plan_identity_mismatch",
    )
    payload = canonical_json_bytes(audit["review_payload"])
    require(
        len(payload) == int(frozen.get("review_payload_bytes") or -1)
        and sha256_bytes(payload) == frozen.get("review_payload_sha256")
        and audit["review_payload"].get("verdict") == "PLAN_PASS"
        and audit["review_payload"].get("findings")
        == {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
        "R14_PLAN_FROZEN_review_payload_invalid",
    )
    predecessor = dict(requirement.get("r13_frozen_predecessor") or {})
    r13_ref = require_identifier(predecessor.get("fresh_audit_ref"), field="R13_audit_ref")
    r13_raw = _git(root, "show", f"{governance}:{r13_ref}")
    r13 = json.loads(r13_raw)
    require(
        sha256_bytes(r13_raw) == predecessor.get("fresh_audit_sha256")
        and validate_result_digest(r13, code="R14_R13_fresh_audit")
        == predecessor.get("fresh_audit_result_digest"),
        "R14_PLAN_FROZEN_R13_audit_invalid",
    )
    return {
        "status": "PLAN_FROZEN_PASS",
        "candidate": candidate,
        "governance": governance,
        "governance_tree": tree,
        "changed_path_count": len(actual_paths),
        "plan_sha256": sha256_bytes(governance_plan),
        "review_payload_sha256": sha256_bytes(payload),
    }


def load_and_validate_r14_contracts(
    *, root: Path | None = None, verify_inputs: bool = False, verify_git: bool = False
) -> R14ContractBundle:
    root = root or repository_root()
    requirement = read_json(root / REQUIREMENT_REF)
    grammar = read_json(root / GRAMMAR_REF)
    topology = read_json(root / TOPOLOGY_REF)
    lifecycle = read_json(root / LIFECYCLE_REF)
    validate_structural_proof_grammar(grammar)
    validate_target_topology_contract(topology)
    validate_lifecycle_transition_table(lifecycle)
    validate_requirement_manifest(requirement, root=root)
    if verify_inputs:
        verify_frozen_input_files(requirement, root=root)
    if verify_git:
        validate_plan_frozen_git(requirement, root=root)
    return R14ContractBundle(
        requirement=requirement,
        grammar=grammar,
        topology=topology,
        lifecycle=lifecycle,
    )


__all__ = [
    "GRAMMAR_REF",
    "LIFECYCLE_REF",
    "REQUIREMENT_REF",
    "RULE_IDS",
    "R14ContractBundle",
    "TARGET_IDS",
    "TOPOLOGY_REF",
    "load_and_validate_r14_contracts",
    "validate_lifecycle_transition_table",
    "validate_plan_frozen_git",
    "validate_requirement_manifest",
    "validate_structural_proof_grammar",
    "validate_target_topology_contract",
    "verify_frozen_input_files",
]
