from __future__ import annotations

import ast
from copy import deepcopy
import math
from pathlib import Path

import pytest

from retrieval.dell_report_r14_common import (
    DellReportR14ContractError,
    canonical_json_bytes,
    read_json,
    with_result_digest,
)
from retrieval.dell_report_r14_contracts import (
    TARGET_IDS,
    load_and_validate_r14_contracts,
    validate_lifecycle_transition_table,
    validate_plan_frozen_git,
    validate_requirement_manifest,
    validate_structural_proof_grammar,
    validate_target_topology_contract,
    verify_frozen_input_files,
)


ROOT = Path(__file__).resolve().parents[1]


def _resign(value: dict) -> dict:
    return with_result_digest(value)


def test_r14_machine_contracts_bind_exact_G_inputs_and_zero_call_authority() -> None:
    bundle = load_and_validate_r14_contracts(root=ROOT)
    frozen = validate_plan_frozen_git(bundle.requirement, root=ROOT)
    inputs = verify_frozen_input_files(bundle.requirement, root=ROOT)

    assert frozen == {
        "status": "PLAN_FROZEN_PASS",
        "candidate": "ade8ebde4e6bca04de290eec6f8e46b55daee65e",
        "governance": "50fc4a706f00f40d831ec9624d33889180e1baa0",
        "governance_tree": "6b4392697409499acb77811ba3c988cca0879f96",
        "changed_path_count": 7,
        "plan_sha256": "5b39ac6ccd788bda5e1de12e40e5f60573e29bbd07a9030bb82234806a9009a2",
        "review_payload_sha256": "fe052ea196bcc36abc89850063dc5dbb7f8e1f73ec3c4894335f05dafdd4aeed",
    }
    assert inputs == {"source_records": 1888, "compiled_objects": 34199}
    assert tuple(sorted(bundle.target_by_id)) == TARGET_IDS
    assert all(
        row["model_provider_calls"] == 0
        for row in bundle.requirement["TokenBudgetBasis"]
    )
    assert bundle.requirement["r17_report_quality_carry_forward"][
        "reader_citation_binding"
    ] == "0_of_18"


def test_r14_grammar_rejects_resigned_rule_removal_and_implicit_truth_lexicon() -> None:
    bundle = load_and_validate_r14_contracts(root=ROOT)
    missing_rule = deepcopy(bundle.grammar)
    missing_rule["rules"] = missing_rule["rules"][:-1]
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_grammar_rule_population_or_order_invalid",
    ):
        validate_structural_proof_grammar(_resign(missing_rule))

    relabel = deepcopy(bundle.grammar)
    relabel["vocabulary_use_matrix"]["company_verb_service_connector_lists"][
        "forbidden"
    ] = []
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_grammar_vocabulary_matrix_row_invalid",
    ):
        validate_structural_proof_grammar(_resign(relabel))


def test_r14_grammar_rejects_resigned_nonempty_vocabulary_semantic_substitution() -> None:
    bundle = load_and_validate_r14_contracts(root=ROOT)
    mutated = deepcopy(bundle.grammar)
    mutated["vocabulary_use_matrix"]["target_predicate_ontology"][
        "forbidden"
    ] = ["author_supplied_placeholder"]

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_grammar_vocabulary_matrix_semantics_invalid",
    ):
        validate_structural_proof_grammar(_resign(mutated))


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("scope", "hard_boundary_surface"), []),
        (("scope", "soft_coordinators"), []),
        (("scope", "parenthetical_pairs"), []),
        (("scope", "quotation_pairs"), []),
        (("structural_resources", "auxiliaries"), []),
        (("structural_resources", "finite_or_participle_suffixes"), []),
        (("structural_resources", "subject_pronouns"), []),
        (("tokenizer", "word_internal_joiners"), []),
        (("normalization", "punctuation_class_map"), {}),
    ],
)
def test_r14_grammar_rejects_resigned_critical_resource_mutation(
    path: tuple[str, str], replacement: object
) -> None:
    bundle = load_and_validate_r14_contracts(root=ROOT)
    mutated = deepcopy(bundle.grammar)
    mutated[path[0]][path[1]] = replacement

    with pytest.raises(DellReportR14ContractError, match="R14_grammar_"):
        validate_structural_proof_grammar(_resign(mutated))


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("premises", ["author_claimed_premise"]),
        ("conclusion", "author_claimed_conclusion"),
        ("state", "AMBIGUOUS"),
    ],
)
def test_r14_grammar_rejects_resigned_rule_semantic_mutation(
    field: str, replacement: object
) -> None:
    bundle = load_and_validate_r14_contracts(root=ROOT)
    mutated = deepcopy(bundle.grammar)
    rule = next(row for row in mutated["rules"] if row["rule_id"] == "G20-EXPLICIT-EVENT")
    rule[field] = replacement

    with pytest.raises(DellReportR14ContractError, match="R14_grammar_rule_"):
        validate_structural_proof_grammar(_resign(mutated))


def test_r14_topology_rejects_resigned_target_role_or_bridge_drift() -> None:
    bundle = load_and_validate_r14_contracts(root=ROOT)
    missing_target = deepcopy(bundle.topology)
    missing_target["targets"] = missing_target["targets"][:-1]
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_topology_target_population_invalid",
    ):
        validate_target_topology_contract(_resign(missing_target))

    bridge_drift = deepcopy(bundle.topology)
    supplier = next(
        row
        for row in bridge_drift["targets"]
        if row["target_id"] == "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH"
    )
    supplier["allowed_bridges"][0]["direction"] = "delivery_to_relationship"
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_topology_declared_bridge_invalid",
    ):
        validate_target_topology_contract(_resign(bridge_drift))


@pytest.mark.parametrize(
    ("surface", "replacement"),
    [
        ("mention_type", "author_defined_type"),
        ("edge", "author_defined_edge"),
        ("cardinality", "author_defined_cardinality"),
    ],
)
def test_r14_topology_rejects_resigned_role_semantic_mutation(
    surface: str, replacement: str
) -> None:
    bundle = load_and_validate_r14_contracts(root=ROOT)
    mutated = deepcopy(bundle.topology)
    asp = next(
        row
        for row in mutated["targets"]
        if row["target_id"] == "DELL-RSQ-03A-TARGET-ASP"
    )
    asp["required_roles"][0][surface] = replacement

    with pytest.raises(DellReportR14ContractError, match="R14_topology_"):
        validate_target_topology_contract(_resign(mutated))


@pytest.mark.parametrize(
    ("surface", "replacement"),
    [
        ("outcome_precedence", ["C_ALWAYS"]),
        ("event_type", "author_defined_event"),
        ("forbidden_inference", ["author_claimed_boundary"]),
        ("positive_family_fingerprints", ["author_claimed_positive"]),
    ],
)
def test_r14_topology_rejects_resigned_contract_semantic_mutation(
    surface: str, replacement: object
) -> None:
    bundle = load_and_validate_r14_contracts(root=ROOT)
    mutated = deepcopy(bundle.topology)
    asp = next(
        row
        for row in mutated["targets"]
        if row["target_id"] == "DELL-RSQ-03A-TARGET-ASP"
    )
    if surface == "outcome_precedence":
        mutated[surface] = replacement
    elif surface == "event_type":
        asp["event_cardinality"][surface] = replacement
    else:
        asp[surface] = replacement

    with pytest.raises(DellReportR14ContractError, match="R14_topology_"):
        validate_target_topology_contract(_resign(mutated))


def test_r14_topology_graph_registry_closes_every_declared_role_and_event_type() -> None:
    bundle = load_and_validate_r14_contracts(root=ROOT)
    registry = bundle.topology["graph_type_registry"]
    mention_bindings = registry["target_mention_type_bindings"]
    edge_bindings = registry["target_edge_bindings"]
    event_types = set(registry["event_types"])
    cardinalities = set(registry["cardinality_enums"])

    for target in bundle.topology["targets"]:
        assert target["event_cardinality"]["event_type"] in event_types
        for role in target["required_roles"]:
            assert role["mention_type"] in mention_bindings
            assert role["edge"] in edge_bindings
            assert role["cardinality"] in cardinalities
        for bridge in target["allowed_bridges"]:
            assert bridge["source_event_type"] in event_types
            assert bridge["destination_event_type"] in event_types


def test_r14_lifecycle_has_one_preformal_fail_route_and_no_owner_stop() -> None:
    bundle = load_and_validate_r14_contracts(root=ROOT)
    bad = deepcopy(bundle.lifecycle)
    bad["transitions"].append(
        {
            "from": "PREFORMAL_REVIEW_PENDING",
            "event": "PREFORMAL_MATERIAL_FAIL",
            "to": "R14_STOP_OWNER_DECISION_REQUIRED",
            "attempt_consumed": False,
        }
    )
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_lifecycle_pre_attempt_owner_stop_forbidden",
    ):
        validate_lifecycle_transition_table(_resign(bad))

    duplicate = deepcopy(bundle.lifecycle)
    duplicate["transitions"].append(deepcopy(duplicate["transitions"][0]))
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_lifecycle_transition_nonunique",
    ):
        validate_lifecycle_transition_table(_resign(duplicate))


def test_r14_lifecycle_rejects_resigned_attempt_bypass_transition() -> None:
    bundle = load_and_validate_r14_contracts(root=ROOT)
    bypass = deepcopy(bundle.lifecycle)
    bypass["transitions"].append(
        {
            "from": "POLICY_BOUND",
            "event": "BYPASS_TO_POSTFORMAL",
            "to": "POSTFORMAL_PASS",
            "attempt_consumed": False,
        }
    )

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_lifecycle_semantics_invalid",
    ):
        validate_lifecycle_transition_table(_resign(bypass))


@pytest.mark.parametrize(
    ("field", "mutator"),
    [
        (
            "critical_operator_families",
            lambda value: value["critical_operator_families"].__setitem__(
                "event", []
            ),
        ),
        ("hard_stops", lambda value: value.__setitem__("hard_stops", [])),
        (
            "positive_controls",
            lambda value: value.__setitem__("positive_controls", ["placeholder"]),
        ),
        (
            "finding_registry",
            lambda value: value["finding_registry"][0].__setitem__(
                "invariant", "author supplied replacement"
            ),
        ),
    ],
)
def test_r14_requirement_rejects_resigned_governance_semantic_substitution(
    field: str, mutator: object
) -> None:
    del field
    bundle = load_and_validate_r14_contracts(root=ROOT)
    mutated = deepcopy(bundle.requirement)
    mutator(mutated)

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_requirement_frozen_semantics_invalid",
    ):
        validate_requirement_manifest(_resign(mutated), root=ROOT)


def test_r14_contract_validator_does_not_import_R13_or_output_surfaces() -> None:
    path = ROOT / "src/retrieval/dell_report_r14_contracts.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    source = path.read_text(encoding="utf-8")

    assert not any("r13" in name.lower() for name in imports)
    assert "dell_report_predicate_frames_r13" not in source
    assert "dell_report_internal_chain_ceiling_r13" not in source
    assert "private_result" not in source
    assert "candidate_ceiling" not in source


def test_r14_canonical_json_rejects_non_finite_values(tmp_path: Path) -> None:
    with pytest.raises((DellReportR14ContractError, ValueError)):
        canonical_json_bytes({"value": math.nan})

    path = tmp_path / "non_finite.json"
    path.write_text('{"value":NaN}', encoding="utf-8")
    with pytest.raises(DellReportR14ContractError, match="R14_JSON_read_failed"):
        read_json(path)
