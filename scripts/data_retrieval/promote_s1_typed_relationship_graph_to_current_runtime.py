from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.current_runtime_binding import (  # noqa: E402
    build_current_s1_runtime_binding_receipt,
    canonical_digest,
    validate_current_s1_runtime_binding_receipt,
)
from sec_agent.runtime_resource_registry import (  # noqa: E402
    load_runtime_resource_registry,
)


PREDECESSOR_POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_7.json"
)
HYBRID_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_6.json"
)
ONTOLOGY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_financial_intent_ontology_v1_4.json"
)
POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_8.json"
)
RECEIPT_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_9.json"
)
REGISTRY_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json"
)


def _path(ref: str) -> Path:
    return ROOT / ref


def _read_json(ref: str) -> dict[str, Any]:
    value = json.loads(_path(ref).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{ref}")
    return value


def _render_json(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_json(ref: str, value: Mapping[str, Any]) -> None:
    path = _path(ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_render_json(value))
    temporary.replace(path)


def _with_resource(
    registry: dict[str, Any],
    *,
    resource_id: str,
    ref: str,
    payload: Mapping[str, Any],
) -> None:
    if canonical_digest(_read_json(ref)) != canonical_digest(dict(payload)):
        raise ValueError(f"runtime_registry_payload_file_drift:{resource_id}")
    rendered = _path(ref).read_bytes()
    matching = [
        row
        for row in registry.get("resources") or ()
        if row.get("resource_id") == resource_id
    ]
    if len(matching) != 1:
        raise ValueError(f"runtime_registry_resource_missing:{resource_id}")
    matching[0]["repo_relative_path"] = ref
    matching[0]["sha256"] = hashlib.sha256(rendered).hexdigest()
    matching[0]["bytes"] = len(rendered)


def _refresh_registry_aggregate(registry: dict[str, Any]) -> None:
    rows = registry.get("resources") or []
    if [str(row.get("resource_id") or "") for row in rows] != sorted(
        str(row.get("resource_id") or "") for row in rows
    ):
        raise ValueError("runtime_registry_resource_order_invalid")
    registry["resource_count"] = len(rows)
    registry["resource_bytes"] = sum(int(row["bytes"]) for row in rows)
    registry["resource_canonical_digest"] = canonical_digest(rows)


def _build_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    policy = deepcopy(dict(predecessor))
    policy["policy_id"] = "FIN-0.1.3-S1-CURRENT-PRODUCT-RUNTIME-BINDING-V1.8"
    policy["assets"]["hybrid_runtime_policy"]["ref"] = HYBRID_REF
    routes = {
        str(row["declared_route"]): row
        for row in policy["runtime_route_capabilities"]
    }
    graph = routes["typed_relationship_graph"]
    graph["capability_state"] = "available"
    graph["executor_id"] = "source_bound_registered_entity_explicit_mention_v1"
    return policy


def main() -> int:
    policy = _build_policy(_read_json(PREDECESSOR_POLICY_REF))
    _write_json(POLICY_REF, policy)

    registry = deepcopy(_read_json(REGISTRY_REF))
    registry["registry_id"] = (
        "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R33"
    )
    _with_resource(
        registry,
        resource_id="application.config.current_financial_intent_ontology",
        ref=ONTOLOGY_REF,
        payload=_read_json(ONTOLOGY_REF),
    )
    _with_resource(
        registry,
        resource_id="application.config.current_hybrid_candidate_runtime_policy",
        ref=HYBRID_REF,
        payload=_read_json(HYBRID_REF),
    )
    _with_resource(
        registry,
        resource_id="application.config.current_s1_runtime_binding_policy",
        ref=POLICY_REF,
        payload=policy,
    )
    _refresh_registry_aggregate(registry)

    receipt = build_current_s1_runtime_binding_receipt(
        ROOT,
        policy,
        payload_overrides={"runtime_registry": registry},
    )
    _write_json(RECEIPT_REF, receipt)
    _with_resource(
        registry,
        resource_id="application.result.current_s1_runtime_binding_receipt",
        ref=RECEIPT_REF,
        payload=receipt,
    )
    _refresh_registry_aggregate(registry)
    _write_json(REGISTRY_REF, registry)

    load_runtime_resource_registry(ROOT)
    validate_current_s1_runtime_binding_receipt(
        receipt,
        policy,
        repository_root=ROOT,
    )
    print(
        json.dumps(
            {
                "status": (
                    "grouped_recall_and_typed_relationship_graph_"
                    "promoted_to_current_runtime"
                ),
                "registry_id": registry["registry_id"],
                "policy_id": policy["policy_id"],
                "binding_digest": receipt["result_digest"],
                "typed_relationship_graph_capability": graph_capability(
                    receipt
                ),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def graph_capability(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return next(
        dict(row)
        for row in receipt["route_execution_truth"]["routes"]
        if row["declared_route"] == "typed_relationship_graph"
    )


if __name__ == "__main__":
    raise SystemExit(main())
