from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.financial_intent_v3 import (  # noqa: E402
    concept_aliases,
    validate_financial_intent_ontology,
)


PREDECESSOR = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_3.json"
)
PROGRAM = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_2.json"
)
OUTPUT = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_4.json"
)


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_mapping_required:{path.name}")
    return value


def _render(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _metric_concepts() -> dict[str, dict[str, Any]]:
    return {
        "average_selling_price": {
            "aliases": [
                "average selling price",
                "ASP",
                "average server selling price",
            ]
        },
        "shipments": {
            "aliases": [
                "shipments",
                "shipment",
                "units shipped",
                "unit shipments",
                "server shipments",
            ]
        },
        "orders": {
            "aliases": ["orders", "order volume", "bookings"]
        },
        "backlog": {
            "aliases": ["backlog", "order backlog", "remaining backlog"]
        },
        "customer_count": {
            "aliases": [
                "customer count",
                "number of customers",
                "named customers",
            ]
        },
        "capacity": {
            "aliases": [
                "capacity",
                "production capacity",
                "manufacturing capacity",
            ]
        },
        "inventory": {
            "aliases": ["inventory", "inventories", "inventory balance"]
        },
        "yield": {
            "aliases": [
                "yield",
                "production yield",
                "manufacturing yield",
                "product yields",
            ]
        },
    }


def _product_concepts() -> dict[str, dict[str, Any]]:
    return {
        "ai_server_price_configuration": {
            "aliases": [
                "AI server observable price range",
                "AI server configuration tiers",
                "GPU HBM networking and storage configuration mix",
            ],
            "supporting_terms": [
                "list price",
                "starting price",
                "configured price",
                "price range",
                "configuration tier",
                "GPU count",
                "accelerator count",
                "memory configuration",
                "networking configuration",
                "storage configuration",
                "rack-scale configuration",
            ],
            "proxy_terms": ["price", "configuration"],
            "excluded_terms": ["share price", "stock price"],
            "recall_surface_groups": {
                "observable_price": [
                    "starting at",
                    "list price",
                    "priced at",
                    "price range",
                    "configured price",
                    "request a quote",
                ],
                "configuration_intensity": [
                    "GPU count",
                    "accelerator count",
                    "HBM",
                    "networking",
                    "storage",
                    "rack-scale",
                    "configuration",
                ],
            },
        },
        "ai_server_unit_volume_market_share": {
            "aliases": [
                "AI server units shipped",
                "industry AI server shipment volume",
                "Dell shipment share proxy",
            ],
            "supporting_terms": [
                "units shipped",
                "unit volume",
                "server shipments",
                "AI server shipments",
                "shipment volume",
                "market share",
                "vendor share",
                "shipment share",
                "racks shipped",
                "systems shipped",
            ],
            "proxy_terms": ["shipments", "market share"],
            "excluded_terms": ["revenue share without unit disclosure"],
            "recall_surface_groups": {
                "shipment_volume": [
                    "units shipped",
                    "unit shipments",
                    "shipment volume",
                    "server shipments",
                    "racks shipped",
                    "systems shipped",
                ],
                "vendor_share": [
                    "market share",
                    "vendor share",
                    "shipment share",
                    "ranked vendor",
                ],
            },
        },
        "ai_server_pvm_configuration_inputs": {
            "aliases": [
                "reported AI server revenue and mix",
                "industry AI server shipment and ASP",
                "configuration intensity inputs",
            ],
            "supporting_terms": [
                "AI server revenue",
                "average selling price",
                "ASP",
                "price and mix",
                "configuration mix",
                "unit volume",
                "shipments",
                "content per system",
                "GPU per server",
            ],
            "proxy_terms": ["mix", "shipments"],
            "excluded_terms": ["generic mix without price or volume"],
            "recall_surface_groups": {
                "price_mix": [
                    "average selling price",
                    "ASP",
                    "price and mix",
                    "configuration mix",
                    "content per system",
                ],
                "revenue_volume": [
                    "AI server revenue",
                    "unit volume",
                    "units shipped",
                    "server shipments",
                ],
            },
        },
        "ai_order_conversion_durability": {
            "aliases": [
                "AI order conversion",
                "backlog durability",
                "customer concentration",
                "pull-forward risk",
            ],
            "supporting_terms": [
                "backlog conversion",
                "convert backlog",
                "order conversion",
                "cancellations",
                "customer concentration",
                "large customer",
                "pull-forward",
                "demand digestion",
                "lead times",
            ],
            "proxy_terms": ["backlog", "orders"],
            "excluded_terms": [],
            "recall_surface_groups": {
                "conversion": [
                    "backlog conversion",
                    "convert backlog",
                    "order conversion",
                    "ship from backlog",
                ],
                "durability_risk": [
                    "cancellation",
                    "customer concentration",
                    "pull-forward",
                    "demand digestion",
                    "lead time",
                ],
            },
        },
        "named_ai_counterparty_relationship": {
            "aliases": [
                "named Dell customer or deployment relationship",
                "Dell supplier dependency or allocation disclosure",
                "supplier names Dell",
                "Dell names supplier",
                "delivery or allocation relationship",
                "Dell supplier attribution or relationship",
            ],
            "supporting_terms": [
                "Dell Technologies",
                "customer",
                "supplier",
                "partner",
                "deployment",
                "powered by",
                "selected",
                "available from",
                "delivery",
                "allocation",
            ],
            "proxy_terms": ["partner", "supplier", "customer"],
            "excluded_terms": ["unnamed customer", "unnamed supplier"],
            "recall_surface_groups": {
                "direct_named_relationship": [
                    "Dell Technologies",
                    "Dell",
                    "powered by",
                    "selected",
                    "supplier",
                    "customer",
                    "partner",
                    "available from",
                ],
                "delivery_allocation": [
                    "delivery",
                    "allocation",
                    "supply agreement",
                    "purchase commitment",
                ],
            },
        },
        "ai_infrastructure_budget_durability": {
            "aliases": ["customer budget durability"],
            "supporting_terms": [
                "AI infrastructure budget",
                "capital spending",
                "capital expenditures",
                "deployment schedule",
                "budget commitment",
                "spending durability",
            ],
            "proxy_terms": ["capex", "capital spending"],
            "excluded_terms": [],
            "recall_surface_groups": {
                "budget_and_schedule": [
                    "AI infrastructure budget",
                    "capital spending",
                    "capital expenditures",
                    "deployment schedule",
                    "budget commitment",
                ]
            },
        },
        "ai_server_fulfillment_execution": {
            "aliases": [
                "AI server delivery cadence",
                "component constraint",
                "inventory and fulfillment execution",
            ],
            "supporting_terms": [
                "delivery cadence",
                "backlog conversion",
                "lead times",
                "component constraints",
                "component availability",
                "inventory",
                "fulfillment",
                "shipments",
            ],
            "proxy_terms": ["inventory", "shipments"],
            "excluded_terms": [],
            "recall_surface_groups": {
                "delivery_fulfillment": [
                    "delivery cadence",
                    "fulfillment",
                    "lead times",
                    "backlog conversion",
                    "shipments",
                ],
                "component_inventory": [
                    "component constraint",
                    "component availability",
                    "inventory build",
                    "inventory levels",
                ],
            },
        },
        "ai_server_oem_unit_economics": {
            "aliases": [
                "AI server OEM gross profit and margin",
                "AI server incremental margin inputs",
            ],
            "supporting_terms": [
                "gross profit",
                "gross margin",
                "operating margin",
                "incremental margin",
                "configuration mix",
                "pricing",
                "component cost",
            ],
            "proxy_terms": ["margin", "gross profit"],
            "excluded_terms": ["companywide margin without AI server attribution"],
            "recall_surface_groups": {
                "unit_economics": [
                    "gross profit",
                    "gross margin",
                    "incremental margin",
                    "configuration mix",
                    "component cost",
                    "pricing",
                ]
            },
        },
        "ai_component_value_pool": {
            "aliases": [
                "supplier component value proxy",
                "GPU HBM packaging and OEM value pool inputs",
                "supplier economics",
            ],
            "supporting_terms": [
                "GPU content",
                "HBM content",
                "advanced packaging",
                "networking content",
                "storage content",
                "bill of materials",
                "component cost",
                "supplier gross margin",
                "value capture",
            ],
            "proxy_terms": ["component cost", "gross margin"],
            "excluded_terms": [],
            "recall_surface_groups": {
                "component_content": [
                    "GPU content",
                    "HBM content",
                    "advanced packaging",
                    "networking content",
                    "storage content",
                    "bill of materials",
                ],
                "supplier_economics": [
                    "component cost",
                    "supplier gross margin",
                    "value capture",
                    "average selling price",
                ],
            },
        },
        "ai_issuer_counter_signals": {
            "aliases": [
                "AI demand digestion signals",
                "AI margin dilution signals",
                "AI working-capital pressure",
            ],
            "supporting_terms": [
                "demand digestion",
                "order slowdown",
                "backlog cancellation",
                "pricing pressure",
                "gross margin dilution",
                "inventory build",
                "receivables build",
                "working capital use",
                "cash conversion pressure",
            ],
            "proxy_terms": ["inventory", "working capital"],
            "excluded_terms": [],
            "recall_surface_groups": {
                "demand_margin": [
                    "demand digestion",
                    "order slowdown",
                    "backlog cancellation",
                    "pricing pressure",
                    "gross margin dilution",
                ],
                "working_capital": [
                    "inventory build",
                    "receivables build",
                    "working capital use",
                    "cash conversion pressure",
                ],
            },
        },
        "ai_ecosystem_counter_signals": {
            "aliases": [
                "GPU HBM packaging constraint",
                "customer capex slowdown",
                "architecture transition",
                "supply release or easing evidence",
            ],
            "supporting_terms": [
                "supply constraint",
                "capacity constraint",
                "short supply",
                "sold out",
                "supply easing",
                "availability improving",
                "production ramp",
                "architecture transition",
                "capex slowdown",
                "capital spending cuts",
            ],
            "proxy_terms": ["capacity", "capex"],
            "excluded_terms": [],
            "recall_surface_groups": {
                "constraint_or_easing": [
                    "supply constraint",
                    "capacity constraint",
                    "short supply",
                    "sold out",
                    "supply easing",
                    "availability improving",
                    "production ramp",
                ],
                "demand_or_transition": [
                    "capex slowdown",
                    "capital spending cuts",
                    "architecture transition",
                    "product transition",
                ],
            },
        },
    }


def build() -> dict[str, Any]:
    ontology = deepcopy(_read(PREDECESSOR))
    ontology.update(
        {
            "schema_version": "fin_ia_financial_intent_ontology_v1_3",
            "contract_revision": (
                "fin_ia_0_1_3_s1_financial_intent_ontology_v1_4"
            ),
            "status": (
                "provider_neutral_financial_core_with_grouped_dell_"
                "disclosure_surface_expansion"
            ),
            "recorded_at": "2026-08-24",
            "parent_ontology_ref": PREDECESSOR.relative_to(ROOT).as_posix(),
            "parent_change_summary": (
                "Map the reviewed DELL proposition program to explicit financial "
                "concepts and add bounded grouped disclosure surfaces for candidate "
                "recall. Groups are provider-neutral, label-free and grant neither "
                "Evidence nor NumericFact authority."
            ),
        }
    )
    ontology["metric_concepts"].update(_metric_concepts())
    ontology["product_concepts"].update(_product_concepts())

    product = ontology["product_concepts"]
    product["gpu_supply_capacity_transition"]["aliases"].append(
        "GPU supply release"
    )
    product["gpu_supply_capacity_transition"]["recall_surface_groups"] = {
        "supply_demand_state": [
            "supply constraint",
            "capacity constraint",
            "sold out",
            "short supply",
            "demand is extraordinary",
            "component availability",
        ],
        "production_transition": [
            "Blackwell",
            "production ramp",
            "ramping at full speed",
            "ramp production",
            "production transition",
        ],
    }
    product["hbm_data_center"]["aliases"].append("HBM availability")
    product["hbm_data_center"]["recall_surface_groups"] = {
        "hbm_supply_demand": [
            "HBM availability",
            "HBM supply",
            "HBM demand",
            "HBM shortage",
            "HBM sold out",
        ]
    }
    product["advanced_packaging_cowos"]["aliases"].append(
        "advanced packaging capacity"
    )
    product["advanced_packaging_cowos"]["recall_surface_groups"] = {
        "packaging_capacity": [
            "advanced packaging capacity",
            "CoWoS capacity",
            "packaging capacity",
            "short supply",
            "capacity expansion",
        ]
    }
    product["ai_infrastructure_deployment_usage"]["aliases"].append(
        "customer AI infrastructure deployment"
    )
    product["ai_infrastructure_deployment_usage"][
        "recall_surface_groups"
    ] = {
        "deployment_usage": [
            "AI infrastructure deployment",
            "deployed AI infrastructure",
            "production deployment",
            "customer deployment",
            "usage growth",
        ]
    }
    ontology["authority"].update(
        {
            "grouped_recall_surfaces_are_candidate_only": True,
            "grouped_recall_has_no_result_or_label_access": True,
            "dell_program_aliases_do_not_create_case_specific_code_branches": True,
        }
    )
    validate_financial_intent_ontology(ontology)

    program = _read(PROGRAM)
    unmapped: list[str] = []
    for request in program.get("evidence_requests") or ():
        for family, key in (
            ("metric_concepts", "metric_intents"),
            ("product_concepts", "product_intents"),
        ):
            for intent in request.get(key) or ():
                concept_id, _ = concept_aliases(
                    str(intent),
                    family=family,
                    ontology=ontology,
                )
                if concept_id.startswith("unmapped::"):
                    unmapped.append(f"{request['request_id']}::{intent}")
    if unmapped:
        raise ValueError(f"dell_program_intents_unmapped:{unmapped}")
    return ontology


def main() -> int:
    ontology = build()
    OUTPUT.write_text(_render(ontology), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": "dell_financial_intent_ontology_materialized",
                "output": OUTPUT.relative_to(ROOT).as_posix(),
                "metric_concept_count": len(ontology["metric_concepts"]),
                "product_concept_count": len(ontology["product_concepts"]),
                "all_dell_program_intents_mapped": True,
                "candidate_is_not_evidence": True,
                "numeric_authority": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
