from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .dell_report_r14_common import (
    canonical_digest,
    canonical_json_bytes,
    domain_rows_digest,
    require,
    require_identifier,
    require_sha256,
    validate_result_digest,
    with_result_digest,
)
from .dell_report_r14_contracts import R14ContractBundle
from .dell_report_structural_graph_r14 import (
    build_event_argument_graph_r14,
    build_price_attachment_graph_r14,
)
from .dell_report_target_compiler_r14 import (
    build_target_graph_view_r14,
    compile_target_decisions_r14,
)


PROPERTY_MANIFEST_SCHEMA = "fin_ia_dell_03B_R14_author_property_manifest_v1_0"
PROPERTY_RECEIPT_SCHEMA = "fin_ia_dell_03B_R14_author_property_receipt_v1_0"
PROPERTY_OPERATOR_VERSION = "R14_author_property_operator_v1"
_HEX40 = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class _PropertyCaseR14:
    case_id: str
    control_id: str
    text: str
    target_id: str
    expected_outcome: str
    expected_metrics: Mapping[str, int]
    positive_control: bool


_AUTHOR_CASES = (
    _PropertyCaseR14(
        "R14-PROP-SUPPLIER-01",
        "supplier_Dell_and_NVIDIA_partnered",
        "Dell partnered with Nvidia.",
        "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        "C",
        {"target_bridge_count": 0},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-SUPPLIER-02",
        "supplier_NVIDIA_and_Dell_partnering_to_deliver",
        "Dell partnered with Nvidia to deliver PowerEdge.",
        "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        "C",
        {"event_count": 1},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-SUPPLIER-03",
        "supplier_Dell_server_with_NVIDIA_component_shipping",
        "Dell shipped PowerEdge with Nvidia GPU in 2026.",
        "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        "C",
        {"event_count": 1},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-SUPPLIER-04",
        "supplier_Dell_partner_ecosystem_including_NVIDIA",
        "Dell partner ecosystem included Nvidia in 2026.",
        "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        "C",
        {"event_count": 1},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-ASP-01",
        "ASP_Dell_offered_PowerEdge_at_currency_price",
        "Dell offered PowerEdge at USD 100.",
        "DELL-RSQ-03A-TARGET-ASP",
        "C",
        {"proved_price_path_count": 1},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-ASP-02",
        "ASP_explicit_price_of_Dell_configuration_is_currency_amount",
        "Dell said the price of PowerEdge configuration was USD 100.",
        "DELL-RSQ-03A-TARGET-ASP",
        "C",
        {"proved_price_path_count": 1},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-ASP-03",
        "ASP_product_priced_at_currency_amount",
        "Dell PowerEdge was priced at USD 100.",
        "DELL-RSQ-03A-TARGET-ASP",
        "C",
        {"proved_price_path_count": 1},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-ASP-04",
        "ASP_all_hardware_bounded_bundle_total",
        (
            "Dell offered a hardware bundle of PowerEdge R760 and PowerEdge "
            "XE9680 for a total of USD 30000."
        ),
        "DELL-RSQ-03A-TARGET-ASP",
        "C",
        {"proved_price_path_count": 1},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-CAPACITY-01",
        "capacity_upstream_capacity_allocated_to_Dell_with_period",
        "Micron allocated HBM capacity to Dell in 2026.",
        "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
        "C",
        {"inference_barrier_count": 0},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-YIELD-01",
        "yield_issuer_reported_utilization_measure_with_period",
        "Micron reported HBM utilization at 95% in 2026.",
        "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
        "C",
        {"inference_barrier_count": 0},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-HBM-01",
        "HBM_upstream_supply_to_Dell_with_period",
        "Micron supplied HBM to Dell in 2026.",
        "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
        "C",
        {"inference_barrier_count": 1},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-UNITS-01",
        "units_Dell_shipped_number_of_servers_with_period",
        "Dell shipped 20 PowerEdge systems in 2026.",
        "DELL-RSQ-03A-TARGET-UNITS",
        "C",
        {"inference_barrier_count": 0},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-EVENT-LIST-01",
        "event_object_list_without_new_predicate",
        (
            "Dell shipped 10 PowerEdge systems and 20 PowerEdge appliances "
            "in 2026."
        ),
        "DELL-RSQ-03A-TARGET-UNITS",
        "P",
        {"event_count": 1, "object_list_proof_count": 1},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-SUBJECT-SHARE-01",
        "shared_subject_actor_only_between_coordinated_events",
        "Dell offered support and shipped 20 PowerEdge systems in 2026.",
        "DELL-RSQ-03A-TARGET-UNITS",
        "C",
        {"event_count": 2, "subject_share_edge_count": 1, "inherited_non_actor_count": 0},
        True,
    ),
    _PropertyCaseR14(
        "R14-PROP-NEG-CAPACITY-SUPPLY",
        "generic_supply_not_capacity_release",
        "Micron supplied HBM to Dell in 2026.",
        "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
        "P",
        {"target_bridge_count": 0, "inference_barrier_count": 1},
        False,
    ),
    _PropertyCaseR14(
        "R14-PROP-NEG-ASP-ATTRIBUTION-PREFIX",
        "third_party_claim_cannot_create_issuer_ASP",
        "An analyst claimed: Dell offered PowerEdge at USD 100.",
        "DELL-RSQ-03A-TARGET-ASP",
        "P",
        {"reported_speech_event_count": 1},
        False,
    ),
    _PropertyCaseR14(
        "R14-PROP-NEG-ASP-ATTRIBUTION-SUFFIX",
        "according_to_third_party_cannot_create_issuer_ASP",
        "Dell offered PowerEdge at USD 100, according to an analyst.",
        "DELL-RSQ-03A-TARGET-ASP",
        "P",
        {"reported_speech_event_count": 2},
        False,
    ),
    _PropertyCaseR14(
        "R14-PROP-NEG-SUPPLIER-INCLUDE",
        "non_relationship_include_cannot_create_supplier_relationship",
        "Dell included Nvidia in a lawsuit in 2026.",
        "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        "P",
        {"inference_barrier_count": 1},
        False,
    ),
    _PropertyCaseR14(
        "R14-PROP-NEG-YIELD-TARGET",
        "target_or_goal_measure_is_not_observed_yield",
        "Micron reported a target HBM utilization of 95% in 2026.",
        "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
        "P",
        {"inference_barrier_count": 1},
        False,
    ),
    _PropertyCaseR14(
        "R14-PROP-NEG-HBM-DOCUMENT",
        "HBM_brochure_is_not_Dell_supply_state",
        "Micron supplied an HBM brochure to Dell in 2026.",
        "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
        "P",
        {"inference_barrier_count": 2},
        False,
    ),
    _PropertyCaseR14(
        "R14-PROP-NEG-UNITS-PROJECT",
        "customer_project_node_count_is_not_Dell_company_units",
        "Dell shipped a customer project with 20 PowerEdge nodes in 2026.",
        "DELL-RSQ-03A-TARGET-UNITS",
        "P",
        {"inference_barrier_count": 1},
        False,
    ),
    _PropertyCaseR14(
        "R14-PROP-NEG-HBM-DISTANT",
        "irrelevant_event_insertion_cannot_create_bridge_complete",
        (
            "Micron supplied HBM in 2026 and Acme reported utilization in 2026 "
            "and Dell shipped HBM PowerEdge in 2026."
        ),
        "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
        "P",
        {"target_bridge_count": 0},
        False,
    ),
    _PropertyCaseR14(
        "R14-PROP-NEG-PRICE-SERVICE",
        "competing_service_head_cannot_create_price_complete",
        "Dell's service agreement offered PowerEdge for USD 100.",
        "DELL-RSQ-03A-TARGET-ASP",
        "P",
        {"proved_price_path_count": 0},
        False,
    ),
)


_PROPERTY_METRIC_KEYS = {
    "event_count",
    "target_bridge_count",
    "proved_price_path_count",
    "object_list_proof_count",
    "subject_share_edge_count",
    "inherited_non_actor_count",
    "inference_barrier_count",
    "reported_speech_event_count",
}


def _canonical_property_rows(author_seed: str) -> list[dict[str, Any]]:
    seed = require_identifier(author_seed, field="property_author_seed")
    rows: list[dict[str, Any]] = []
    for case in _AUTHOR_CASES:
        body = {
            "case_id": case.case_id,
            "control_id": case.control_id,
            "input_text": case.text,
            "input_digest": canonical_digest(case.text),
            "target_id": case.target_id,
            "expected_outcome": case.expected_outcome,
            "expected_metrics": dict(sorted(case.expected_metrics.items())),
            "positive_control": case.positive_control,
            "operator_version": PROPERTY_OPERATOR_VERSION,
            "seed": seed,
        }
        rows.append({**body, "row_digest": canonical_digest(body)})
    rows.sort(key=lambda row: row["case_id"])
    return rows


def build_author_property_manifest_r14(
    *, requirement_manifest: Mapping[str, Any], author_seed: str
) -> dict[str, Any]:
    expected_positive = tuple(requirement_manifest.get("positive_controls") or ())
    actual_positive = tuple(
        row.control_id for row in _AUTHOR_CASES if row.positive_control
    )
    require(
        set(actual_positive) == set(expected_positive)
        and len(actual_positive) == len(expected_positive),
        "R14_property_positive_control_population_invalid",
    )
    seed = require_identifier(author_seed, field="property_author_seed")
    rows = _canonical_property_rows(seed)
    body = {
        "schema_version": PROPERTY_MANIFEST_SCHEMA,
        "requirement_manifest_result_digest": requirement_manifest.get("result_digest"),
        "author_seed": seed,
        "operator_version": PROPERTY_OPERATOR_VERSION,
        "case_rows": rows,
        "case_count": len(rows),
        "positive_control_count": sum(row["positive_control"] for row in rows),
        "case_root": domain_rows_digest(
            b"FIN_IA_R14_AUTHOR_PROPERTY_MANIFEST_V1\0",
            (canonical_json_bytes(row) for row in rows),
        ),
        "frozen_before_execution": True,
    }
    output = with_result_digest(body)
    validate_author_property_manifest_r14(
        output, requirement_manifest=requirement_manifest
    )
    return output


def validate_author_property_manifest_r14(
    value: Mapping[str, Any], *, requirement_manifest: Mapping[str, Any]
) -> None:
    validate_result_digest(value, code="R14_property_manifest")
    require(
        set(value)
        == {
            "schema_version",
            "requirement_manifest_result_digest",
            "author_seed",
            "operator_version",
            "case_rows",
            "case_count",
            "positive_control_count",
            "case_root",
            "frozen_before_execution",
            "result_digest",
        },
        "R14_property_manifest_keyset_invalid",
    )
    seed = require_identifier(value.get("author_seed"), field="property_author_seed")
    require(
        value.get("schema_version") == PROPERTY_MANIFEST_SCHEMA
        and value.get("operator_version") == PROPERTY_OPERATOR_VERSION
        and value.get("frozen_before_execution") is True
        and value.get("requirement_manifest_result_digest")
        == requirement_manifest.get("result_digest"),
        "R14_property_manifest_identity_invalid",
    )
    rows = list(value.get("case_rows") or ())
    expected_rows = _canonical_property_rows(seed)
    require(
        rows == expected_rows
        and value.get("case_count") == len(rows)
        and value.get("positive_control_count")
        == sum(bool(row.get("positive_control")) for row in rows),
        "R14_property_manifest_denominator_invalid",
    )
    positive_ids = tuple(
        row["control_id"] for row in rows if row["positive_control"]
    )
    require(
        set(positive_ids) == set(requirement_manifest.get("positive_controls") or ())
        and len(positive_ids)
        == len(tuple(requirement_manifest.get("positive_controls") or ())),
        "R14_property_manifest_positive_controls_invalid",
    )
    require(
        value.get("case_root")
        == domain_rows_digest(
            b"FIN_IA_R14_AUTHOR_PROPERTY_MANIFEST_V1\0",
            (canonical_json_bytes(row) for row in rows),
        ),
        "R14_property_manifest_root_invalid",
    )


def _observe_case(
    row: Mapping[str, Any], *, bundle: R14ContractBundle
) -> dict[str, Any]:
    graph = build_event_argument_graph_r14(text=str(row["input_text"]), bundle=bundle)
    price = build_price_attachment_graph_r14(graph=graph, bundle=bundle)
    view = build_target_graph_view_r14(event_graph=graph, price_graph=price)
    decisions = compile_target_decisions_r14(
        view=view, topology_contract=bundle.topology
    )
    decision = next(
        value for value in decisions if value.target_id == row["target_id"]
    )
    metrics = {
        "event_count": len(graph.events),
        "target_bridge_count": len(graph.target_bridge_edges),
        "proved_price_path_count": sum(
            proof.state == "PROVED" for proof in price.proofs
        ),
        "object_list_proof_count": sum(
            proof.rule_id == "G22-OBJECT-LIST" and proof.state == "PROVED"
            for proof in graph.proofs
        ),
        "subject_share_edge_count": len(graph.subject_share_edges),
        "inherited_non_actor_count": sum(
            edge.proof_rule_id == "G23-SUBJECT-INHERIT" and edge.role != "actor"
            for edge in graph.role_edges
        ),
        "inference_barrier_count": sum(
            len(event.inference_barrier_ids) for event in graph.events
        ),
        "reported_speech_event_count": sum(
            event.speech_mode == "reported_speech" for event in graph.events
        ),
    }
    expected_metrics = dict(row["expected_metrics"])
    passed = decision.outcome == row["expected_outcome"] and all(
        metrics[key] == expected for key, expected in expected_metrics.items()
    )
    body = {
        "case_id": row["case_id"],
        "manifest_row_digest": row["row_digest"],
        "actual_outcome": decision.outcome,
        "actual_metrics": metrics,
        "classification_pass": decision.outcome == row["expected_outcome"],
        "topology_pass": all(
            metrics[key] == expected for key, expected in expected_metrics.items()
        ),
        "passed": passed,
        "minimal_counterexample_digest": None if passed else graph.graph_digest,
    }
    return {**body, "row_digest": canonical_digest(body)}


def build_author_property_receipt_r14(
    *,
    manifest: Mapping[str, Any],
    requirement_manifest: Mapping[str, Any],
    bundle: R14ContractBundle,
    implementation_commit: str,
    implementation_tree: str,
) -> dict[str, Any]:
    validate_author_property_manifest_r14(
        manifest, requirement_manifest=requirement_manifest
    )
    require(
        bool(_HEX40.fullmatch(implementation_commit))
        and bool(_HEX40.fullmatch(implementation_tree)),
        "R14_property_git_identity_invalid",
    )
    rows = [_observe_case(row, bundle=bundle) for row in manifest["case_rows"]]
    passed = sum(bool(row["passed"]) for row in rows)
    counterexamples = [
        row["minimal_counterexample_digest"]
        for row in rows
        if row["minimal_counterexample_digest"] is not None
    ]
    body = {
        "schema_version": PROPERTY_RECEIPT_SCHEMA,
        "property_manifest_result_digest": manifest["result_digest"],
        "property_manifest_case_root": manifest["case_root"],
        "implementation_commit": implementation_commit,
        "implementation_tree": implementation_tree,
        "result_rows": rows,
        "case_count": len(rows),
        "passed_count": passed,
        "failed_count": len(rows) - passed,
        "positive_control_count": manifest["positive_control_count"],
        "minimal_counterexample_digests": counterexamples,
        "result_root": domain_rows_digest(
            b"FIN_IA_R14_AUTHOR_PROPERTY_RESULTS_V1\0",
            (canonical_json_bytes(row) for row in rows),
        ),
        "status": "PASS" if passed == len(rows) else "FAIL",
    }
    output = with_result_digest(body)
    validate_author_property_receipt_r14(output, manifest=manifest)
    return output


def validate_author_property_receipt_r14(
    value: Mapping[str, Any], *, manifest: Mapping[str, Any]
) -> None:
    validate_result_digest(value, code="R14_property_receipt")
    require(
        set(value)
        == {
            "schema_version",
            "property_manifest_result_digest",
            "property_manifest_case_root",
            "implementation_commit",
            "implementation_tree",
            "result_rows",
            "case_count",
            "passed_count",
            "failed_count",
            "positive_control_count",
            "minimal_counterexample_digests",
            "result_root",
            "status",
            "result_digest",
        },
        "R14_property_receipt_keyset_invalid",
    )
    rows = list(value.get("result_rows") or ())
    manifest_rows = list(manifest.get("case_rows") or ())
    require(
        value.get("schema_version") == PROPERTY_RECEIPT_SCHEMA
        and value.get("property_manifest_result_digest") == manifest.get("result_digest")
        and value.get("property_manifest_case_root") == manifest.get("case_root")
        and [row.get("case_id") for row in rows]
        == [row.get("case_id") for row in manifest_rows],
        "R14_property_receipt_binding_invalid",
    )
    require(
        bool(_HEX40.fullmatch(str(value.get("implementation_commit") or "")))
        and bool(_HEX40.fullmatch(str(value.get("implementation_tree") or ""))),
        "R14_property_receipt_git_identity_invalid",
    )
    for row, manifest_row in zip(rows, manifest_rows):
        require(
            isinstance(row, dict)
            and set(row)
            == {
                "case_id",
                "manifest_row_digest",
                "actual_outcome",
                "actual_metrics",
                "classification_pass",
                "topology_pass",
                "passed",
                "minimal_counterexample_digest",
                "row_digest",
            },
            "R14_property_receipt_row_schema_invalid",
        )
        body = dict(row)
        digest = body.pop("row_digest", None)
        require(digest == canonical_digest(body), "R14_property_receipt_row_digest_invalid")
        metrics = row.get("actual_metrics")
        expected_metrics = dict(manifest_row["expected_metrics"])
        require(
            row.get("manifest_row_digest") == manifest_row.get("row_digest")
            and isinstance(metrics, dict)
            and set(metrics) == _PROPERTY_METRIC_KEYS
            and all(type(item) is int and item >= 0 for item in metrics.values()),
            "R14_property_receipt_row_binding_invalid",
        )
        classification_pass = row.get("actual_outcome") == manifest_row.get(
            "expected_outcome"
        )
        topology_pass = all(
            metrics[key] == expected for key, expected in expected_metrics.items()
        )
        passed_row = classification_pass and topology_pass
        require(
            type(row.get("classification_pass")) is bool
            and type(row.get("topology_pass")) is bool
            and type(row.get("passed")) is bool
            and row["classification_pass"] == classification_pass
            and row["topology_pass"] == topology_pass
            and row["passed"] == passed_row,
            "R14_property_receipt_row_semantics_invalid",
        )
        if passed_row:
            require(
                row.get("minimal_counterexample_digest") is None,
                "R14_property_receipt_spurious_counterexample",
            )
        else:
            require_sha256(
                row.get("minimal_counterexample_digest"),
                field="property_minimal_counterexample_digest",
            )
    passed = sum(bool(row.get("passed")) for row in rows)
    failed = len(rows) - passed
    require(
        value.get("case_count") == len(rows)
        and value.get("passed_count") == passed
        and value.get("failed_count") == failed
        and value.get("status") == ("PASS" if failed == 0 and rows else "FAIL")
        and value.get("positive_control_count")
        == manifest.get("positive_control_count")
        and value.get("minimal_counterexample_digests")
        == [
            row["minimal_counterexample_digest"]
            for row in rows
            if row.get("minimal_counterexample_digest") is not None
        ],
        "R14_property_receipt_counts_or_status_invalid",
    )
    require(
        value.get("result_root")
        == domain_rows_digest(
            b"FIN_IA_R14_AUTHOR_PROPERTY_RESULTS_V1\0",
            (canonical_json_bytes(row) for row in rows),
        ),
        "R14_property_receipt_root_invalid",
    )


__all__ = [
    "PROPERTY_MANIFEST_SCHEMA",
    "PROPERTY_OPERATOR_VERSION",
    "PROPERTY_RECEIPT_SCHEMA",
    "build_author_property_manifest_r14",
    "build_author_property_receipt_r14",
    "validate_author_property_manifest_r14",
    "validate_author_property_receipt_r14",
]
