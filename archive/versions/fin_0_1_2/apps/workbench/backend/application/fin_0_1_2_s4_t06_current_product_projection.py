from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.runtime_resource_registry import read_registered_runtime_json


CURRENT_PRODUCT_PROJECTION_REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_2_s4_t06_current_product_projection_"
    "runtime_resource_registry_v1_0.json"
)
CURRENT_PRODUCT_PROJECTION_RESOURCE_ID = (
    "fin_0_1_2.s4.t06.current_product_projection_manifest"
)
CURRENT_PRODUCT_PROJECTION_SCHEMA = (
    "fin_ia_0_1_2_s4_t06_current_product_projection_manifest_v1_0"
)
CURRENT_PRODUCT_API_SCHEMA = (
    "fin_ia_0_1_2_s4_t06_current_product_projection_api_v1_0"
)
CURRENT_PRODUCT_SURFACES = (
    "case",
    "run",
    "evidence",
    "numeric",
    "graph",
    "gaps",
    "workpaper",
    "report",
    "trace",
    "quality",
)
CURRENT_PRODUCT_CASE_KEYS = ("DELL", "MU", "NVDA")
CURRENT_PRODUCT_READ_PERMISSION = "current_product:read"

_FORBIDDEN_PRODUCT_KEYS = frozenset(
    {
        "authorization",
        "capture_objects",
        "credential",
        "cookie",
        "object_key",
        "provider_output",
        "raw_provider_response",
        "request_headers",
        "response_headers",
    }
)
_SAFE_NEGATIVE_BOUNDARY_KEYS = frozenset(
    {"raw_capture_product_exposure", "raw_content_exposed"}
)


class CurrentProductProjectionError(RuntimeError):
    def __init__(self, error_code: str, status_code: int = 409, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


@dataclass(frozen=True)
class CurrentProductPrincipal:
    mode: str
    permissions: frozenset[str]


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CurrentProductProjectionError(code)


def _walk_forbidden(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            _require(
                normalized not in _FORBIDDEN_PRODUCT_KEYS
                and (
                    not normalized.startswith("raw_")
                    or normalized in _SAFE_NEGATIVE_BOUNDARY_KEYS
                )
                and "private_reasoning" not in normalized,
                "current_product_projection_forbidden_raw_surface",
            )
            _walk_forbidden(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _walk_forbidden(item)
    elif isinstance(value, str):
        _require(
            ".codex_runtime" not in value.replace("\\", "/").lower()
            and "restricted-provider-captures" not in value.lower(),
            "current_product_projection_forbidden_runtime_reference",
        )


def validate_current_product_projection_manifest(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    body = {key: item for key, item in value.items() if key != "manifest_digest"}
    _require(
        value.get("schema_version") == CURRENT_PRODUCT_PROJECTION_SCHEMA
        and value.get("projection_mode") == "current"
        and value.get("manifest_digest") == canonical_digest(body),
        "current_product_projection_manifest_identity_or_digest_invalid",
    )
    cases = value.get("cases")
    _require(
        isinstance(cases, list)
        and [row.get("case_key") for row in cases if isinstance(row, Mapping)]
        == list(CURRENT_PRODUCT_CASE_KEYS),
        "current_product_projection_case_set_invalid",
    )
    for case in cases:
        _require(
            isinstance(case, Mapping),
            "current_product_projection_case_invalid",
        )
        case_key = str(case.get("case_key") or "")
        case_body = {
            key: item for key, item in case.items() if key != "case_projection_digest"
        }
        _require(
            case.get("case_projection_digest") == canonical_digest(case_body),
            "current_product_projection_case_digest_invalid",
        )
        views = case.get("views")
        _require(
            isinstance(views, Mapping)
            and tuple(views.keys()) == CURRENT_PRODUCT_SURFACES,
            "current_product_projection_surface_set_invalid",
        )
        for surface, view in views.items():
            _require(
                isinstance(view, Mapping)
                and view.get("surface") == surface
                and view.get("case_key") == case_key,
                "current_product_projection_view_identity_invalid",
            )
            view_body = {
                key: item for key, item in view.items() if key != "view_digest"
            }
            _require(
                view.get("view_digest") == canonical_digest(view_body),
                "current_product_projection_view_digest_invalid",
            )
        evidence_rows = views["evidence"].get("data", {}).get("rows")
        numeric_rows = views["numeric"].get("data", {}).get("rows")
        gap_rows = views["gaps"].get("data", {}).get("rows")
        graph = views["graph"].get("data", {})
        _require(
            isinstance(evidence_rows, list)
            and len(evidence_rows) == 15
            and all(row.get("entity_ref") == case_key for row in evidence_rows)
            and isinstance(numeric_rows, list)
            and len(numeric_rows) == 3
            and all(row.get("entity_ref") == case_key for row in numeric_rows)
            and isinstance(gap_rows, list)
            and len(gap_rows) == 3,
            "current_product_projection_business_row_shape_invalid",
        )
        _require(
            graph
            == {
                "status": "typed_empty_no_approved_current_graph_evidence",
                "nodes": [],
                "edges": [],
                "reason": "approved_current_evidence_pack_contains_no_graph_evidence",
            },
            "current_product_projection_graph_must_remain_typed_empty",
        )
    counts = value.get("observed_counts") or {}
    _require(
        counts.get("cases") == 3
        and counts.get("evidence_rows") == 45
        and counts.get("numeric_rows") == 9
        and counts.get("typed_gaps") == 9
        and counts.get("approved_graph_edges") == 0
        and counts.get("business_artifacts") == 27
        and counts.get("owner_acceptances") == 3,
        "current_product_projection_aggregate_counts_invalid",
    )
    boundaries = value.get("hard_boundaries") or {}
    _require(
        boundaries.get("fixture_fallback") is False
        and boundaries.get("raw_capture_product_exposure") is False
        and boundaries.get("mutable_business_truth_write") is False
        and boundaries.get("invented_graph_edges") is False
        and boundaries.get("model_provider_network_source_calls") == 0,
        "current_product_projection_hard_boundary_invalid",
    )
    _walk_forbidden(value)
    return deepcopy(dict(value))


class CurrentProductProjectionService:
    """Read-only, digest-bound projection over accepted FIN 0.1.2 cases."""

    def __init__(self, manifest: Mapping[str, Any]):
        self._manifest = validate_current_product_projection_manifest(manifest)
        self._cases = {
            str(row["case_key"]): row for row in self._manifest["cases"]
        }

    @classmethod
    def from_repository(
        cls, repository_root: str | Path
    ) -> "CurrentProductProjectionService":
        manifest = read_registered_runtime_json(
            repository_root,
            CURRENT_PRODUCT_PROJECTION_RESOURCE_ID,
            registry_ref=CURRENT_PRODUCT_PROJECTION_REGISTRY_REF,
        )
        return cls(manifest)

    @property
    def manifest_digest(self) -> str:
        return str(self._manifest["manifest_digest"])

    def list_cases(self, principal: CurrentProductPrincipal) -> dict[str, Any]:
        self._require_read(principal)
        items = []
        for case_key in CURRENT_PRODUCT_CASE_KEYS:
            case = self._cases[case_key]
            view = case["views"]["case"]
            items.append(
                {
                    "case_key": case_key,
                    "case_projection_digest": case["case_projection_digest"],
                    "view_digest": view["view_digest"],
                    **deepcopy(view["data"]),
                }
            )
        return {
            "schema_version": CURRENT_PRODUCT_API_SCHEMA,
            "projection_mode": "current",
            "manifest_digest": self.manifest_digest,
            "items": items,
            "next_cursor": None,
        }

    def get_case(
        self, case_key: str, principal: CurrentProductPrincipal
    ) -> dict[str, Any]:
        return self.get_surface(case_key, "case", principal)

    def get_surface(
        self,
        case_key: str,
        surface: str,
        principal: CurrentProductPrincipal,
    ) -> dict[str, Any]:
        self._require_read(principal)
        normalized_case = str(case_key).upper()
        if normalized_case not in self._cases:
            raise CurrentProductProjectionError(
                "current_product_case_not_found", 404, case_key=case_key
            )
        if surface not in CURRENT_PRODUCT_SURFACES:
            raise CurrentProductProjectionError(
                "current_product_surface_not_found", 404, surface=surface
            )
        case = self._cases[normalized_case]
        view = case["views"][surface]
        return {
            "schema_version": CURRENT_PRODUCT_API_SCHEMA,
            "projection_mode": "current",
            "manifest_digest": self.manifest_digest,
            "case_key": normalized_case,
            "case_projection_digest": case["case_projection_digest"],
            "surface": surface,
            "view_digest": view["view_digest"],
            "data": deepcopy(view["data"]),
        }

    @staticmethod
    def _require_read(principal: CurrentProductPrincipal) -> None:
        if principal.mode != "current":
            raise CurrentProductProjectionError(
                "current_product_mode_required", 403
            )
        if CURRENT_PRODUCT_READ_PERMISSION not in principal.permissions:
            raise CurrentProductProjectionError(
                "current_product_read_permission_required", 403
            )
