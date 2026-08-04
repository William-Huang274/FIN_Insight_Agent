from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from sec_agent.runtime_resource_registry import (
    RuntimeResource,
    RuntimeResourceRegistryError,
    load_runtime_resource_registry,
    read_registered_runtime_json,
)


CONTRACT_REF = "fin_0_1_2.S4.natural_case_entry_and_exact_binding:v1"
AUTHORITY_SCHEMA = "fin_ia_0_1_2_s4_t01_natural_case_entry_authority_v1_0"
AUTHORITY_RESOURCE_ID = "fin_0_1_2.s4.t01.natural_case_entry_authority"
REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_2_s4_t01_runtime_resource_registry_v1_0.json"
)
EXPECTED_CASE_IDENTITIES = {
    "DELL": ("DELL", "Dell Technologies Inc.", "DELL"),
    "MU": ("MU", "Micron Technology, Inc.", "MU"),
    "NVDA": ("NVDA", "NVIDIA Corporation", "NVDA"),
}
EXPECTED_PROGRAM_CELL_IDS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)
_INTERNAL_OBJECTIVE_PATTERN = re.compile(
    r"(?:fixture|preflight|test case|internal task|execute the fin|s[0-5][-_ ]t\d+)",
    flags=re.IGNORECASE,
)


class Fin012S4T01EntryError(ValueError):
    """Typed failure at the FIN 0.1.2 S4-T01 entry boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _strict_keys(value: Any, expected: set[str], code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise Fin012S4T01EntryError(code)
    return value


def _nonblank(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Fin012S4T01EntryError(code)
    return value.strip()


def _sha256(value: Any, code: str) -> str:
    text = _nonblank(value, code).lower()
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise Fin012S4T01EntryError(code)
    return text


def _parse_as_of(value: Any) -> str:
    text = _nonblank(value, "s4_t01_as_of_missing")
    if not text.endswith("Z"):
        raise Fin012S4T01EntryError("s4_t01_as_of_not_utc")
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Fin012S4T01EntryError("s4_t01_as_of_invalid") from exc
    return text


def _normalize_program_cells(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise Fin012S4T01EntryError("s4_t01_program_cells_invalid")
    rows: list[dict[str, str]] = []
    for raw in value:
        row = _strict_keys(
            raw,
            {"program_cell_id", "objective"},
            "s4_t01_program_cell_shape_invalid",
        )
        objective = _nonblank(row["objective"], "s4_t01_cell_objective_missing")
        if len(objective) < 24 or _INTERNAL_OBJECTIVE_PATTERN.search(objective):
            raise Fin012S4T01EntryError("s4_t01_cell_objective_not_natural")
        rows.append(
            {
                "program_cell_id": _nonblank(
                    row["program_cell_id"],
                    "s4_t01_program_cell_id_missing",
                ),
                "objective": objective,
            }
        )
    rows.sort(key=lambda row: row["program_cell_id"])
    ids = tuple(row["program_cell_id"] for row in rows)
    if ids != tuple(sorted(EXPECTED_PROGRAM_CELL_IDS)):
        raise Fin012S4T01EntryError("s4_t01_program_cell_set_invalid")
    return rows


def _normalize_budget(raw: Any) -> dict[str, Any]:
    row = _strict_keys(
        raw,
        {
            "budget_ref",
            "model_calls",
            "provider_calls",
            "execution_network_calls",
            "source_network_calls",
            "external_tool_calls",
            "token_budget",
            "cost_usd",
            "wall_clock_seconds",
            "future_execution_budget_ref",
        },
        "s4_t01_budget_shape_invalid",
    )
    zero_fields = (
        "model_calls",
        "provider_calls",
        "execution_network_calls",
        "source_network_calls",
        "external_tool_calls",
        "token_budget",
    )
    if any(type(row[key]) is not int or row[key] != 0 for key in zero_fields):
        raise Fin012S4T01EntryError("s4_t01_external_budget_not_zero")
    if type(row["cost_usd"]) not in (int, float) or float(row["cost_usd"]) != 0.0:
        raise Fin012S4T01EntryError("s4_t01_cost_budget_not_zero")
    if (
        type(row["wall_clock_seconds"]) is not int
        or not 1 <= row["wall_clock_seconds"] <= 60
    ):
        raise Fin012S4T01EntryError("s4_t01_wall_clock_budget_invalid")
    future_ref = _nonblank(
        row["future_execution_budget_ref"],
        "s4_t01_future_execution_budget_ref_missing",
    )
    if "pending" not in future_ref.lower():
        raise Fin012S4T01EntryError(
            "s4_t01_future_execution_budget_prematurely_authorized"
        )
    return {
        "budget_ref": _nonblank(row["budget_ref"], "s4_t01_budget_ref_missing"),
        **{key: int(row[key]) for key in zero_fields},
        "cost_usd": 0.0,
        "wall_clock_seconds": int(row["wall_clock_seconds"]),
        "future_execution_budget_ref": future_ref,
    }


def _normalize_resource_binding(raw: Any, *, code: str) -> dict[str, Any]:
    row = _strict_keys(
        raw,
        {"resource_id", "repo_relative_path", "sha256", "bytes"},
        f"{code}_shape_invalid",
    )
    size = row["bytes"]
    if type(size) is not int or size <= 0:
        raise Fin012S4T01EntryError(f"{code}_bytes_invalid")
    return {
        "resource_id": _nonblank(row["resource_id"], f"{code}_id_missing"),
        "repo_relative_path": _nonblank(
            row["repo_relative_path"], f"{code}_path_missing"
        ),
        "sha256": _sha256(row["sha256"], f"{code}_sha256_invalid"),
        "bytes": size,
    }


def _normalize_case(raw: Any) -> dict[str, Any]:
    row = _strict_keys(
        raw,
        {
            "case_key",
            "ticker",
            "company",
            "canonical_entity_ref",
            "objective",
            "as_of",
            "freshness_policy_ref",
            "program_cells",
            "budget_ref",
            "source_snapshot",
            "index_snapshot",
            "identity_seed",
        },
        "s4_t01_case_shape_invalid",
    )
    case_key = _nonblank(row["case_key"], "s4_t01_case_key_missing")
    expected = EXPECTED_CASE_IDENTITIES.get(case_key)
    observed = (
        row.get("ticker"),
        row.get("company"),
        row.get("canonical_entity_ref"),
    )
    if expected is None or observed != expected:
        raise Fin012S4T01EntryError("s4_t01_case_identity_invalid")
    objective = _nonblank(row["objective"], "s4_t01_objective_missing")
    if len(objective) < 40 or _INTERNAL_OBJECTIVE_PATTERN.search(objective):
        raise Fin012S4T01EntryError("s4_t01_objective_not_natural")
    identity_seed = _nonblank(row["identity_seed"], "s4_t01_identity_seed_missing")
    if len(identity_seed) < 24:
        raise Fin012S4T01EntryError("s4_t01_identity_seed_too_short")
    return {
        "case_key": case_key,
        "ticker": expected[0],
        "company": expected[1],
        "canonical_entity_ref": expected[2],
        "objective": objective,
        "as_of": _parse_as_of(row["as_of"]),
        "freshness_policy_ref": _nonblank(
            row["freshness_policy_ref"],
            "s4_t01_freshness_policy_ref_missing",
        ),
        "program_cells": _normalize_program_cells(row["program_cells"]),
        "budget_ref": _nonblank(row["budget_ref"], "s4_t01_case_budget_ref_missing"),
        "source_snapshot": _normalize_resource_binding(
            row["source_snapshot"], code="s4_t01_source_snapshot"
        ),
        "index_snapshot": _normalize_resource_binding(
            row["index_snapshot"], code="s4_t01_index_snapshot"
        ),
        "identity_seed": identity_seed,
    }


def _normalize_authority(payload: Mapping[str, Any]) -> dict[str, Any]:
    root = _strict_keys(
        payload,
        {
            "schema_version",
            "contract_ref",
            "status",
            "runtime_binding",
            "budgets",
            "cases",
            "nonpromotion_boundary",
            "authority_digest",
        },
        "s4_t01_authority_shape_invalid",
    )
    if root["schema_version"] != AUTHORITY_SCHEMA or root["contract_ref"] != CONTRACT_REF:
        raise Fin012S4T01EntryError("s4_t01_authority_identity_invalid")
    if root["status"] != "tracked_zero_call_entry_authority_not_execution_admission":
        raise Fin012S4T01EntryError("s4_t01_authority_status_invalid")
    runtime = _strict_keys(
        root["runtime_binding"],
        {"binding_ref", "binding_resource", "source_resource"},
        "s4_t01_runtime_binding_shape_invalid",
    )
    normalized_runtime = {
        "binding_ref": _nonblank(
            runtime["binding_ref"], "s4_t01_runtime_binding_ref_missing"
        ),
        "binding_resource": _normalize_resource_binding(
            runtime["binding_resource"], code="s4_t01_runtime_binding_resource"
        ),
        "source_resource": _normalize_resource_binding(
            runtime["source_resource"], code="s4_t01_runtime_source_resource"
        ),
    }
    if normalized_runtime["binding_ref"] != (
        "fin_0_1_2.common_runtime.judgment_atom_family_binding:v1.3"
    ):
        raise Fin012S4T01EntryError("s4_t01_runtime_contract_ref_invalid")
    if not isinstance(root["budgets"], list) or not root["budgets"]:
        raise Fin012S4T01EntryError("s4_t01_budgets_invalid")
    budgets = sorted(
        (_normalize_budget(row) for row in root["budgets"]),
        key=lambda row: row["budget_ref"],
    )
    if len({row["budget_ref"] for row in budgets}) != len(budgets):
        raise Fin012S4T01EntryError("s4_t01_budget_ref_duplicate")
    if not isinstance(root["cases"], list):
        raise Fin012S4T01EntryError("s4_t01_cases_invalid")
    cases = sorted((_normalize_case(row) for row in root["cases"]), key=lambda row: row["case_key"])
    if [row["case_key"] for row in cases] != sorted(EXPECTED_CASE_IDENTITIES):
        raise Fin012S4T01EntryError("s4_t01_case_set_invalid")
    budget_refs = {row["budget_ref"] for row in budgets}
    if any(row["budget_ref"] not in budget_refs for row in cases):
        raise Fin012S4T01EntryError("s4_t01_case_budget_unbound")
    boundary = _strict_keys(
        root["nonpromotion_boundary"],
        {
            "snapshot_content_read_or_returned",
            "snapshot_is_current_evidence",
            "evidence_qualification_owner",
            "execution_admission_created",
            "T02_started",
            "business_artifact_created",
        },
        "s4_t01_nonpromotion_boundary_shape_invalid",
    )
    expected_boundary = {
        "snapshot_content_read_or_returned": False,
        "snapshot_is_current_evidence": False,
        "evidence_qualification_owner": "S4-T02",
        "execution_admission_created": False,
        "T02_started": False,
        "business_artifact_created": False,
    }
    if dict(boundary) != expected_boundary:
        raise Fin012S4T01EntryError("s4_t01_nonpromotion_boundary_invalid")
    normalized = {
        "schema_version": AUTHORITY_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "status": root["status"],
        "runtime_binding": normalized_runtime,
        "budgets": budgets,
        "cases": cases,
        "nonpromotion_boundary": expected_boundary,
    }
    if root["authority_digest"] != _digest(normalized):
        raise Fin012S4T01EntryError("s4_t01_authority_digest_mismatch")
    normalized["authority_digest"] = str(root["authority_digest"])
    return normalized


def _resource_projection(row: RuntimeResource | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(row, RuntimeResource):
        return {
            "resource_id": row.resource_id,
            "repo_relative_path": row.repo_relative_path,
            "sha256": row.sha256,
            "bytes": row.bytes,
        }
    return {
        "resource_id": row["resource_id"],
        "repo_relative_path": row["repo_relative_path"],
        "sha256": row["sha256"],
        "bytes": row["bytes"],
    }


def _assert_resource_binding(
    expected: Mapping[str, Any], resources_by_id: Mapping[str, Any]
) -> dict[str, Any]:
    resource_id = str(expected["resource_id"])
    try:
        observed = _resource_projection(resources_by_id[resource_id])
    except KeyError as exc:
        raise Fin012S4T01EntryError(
            f"s4_t01_unknown_runtime_resource:{resource_id}"
        ) from exc
    if observed != dict(expected):
        raise Fin012S4T01EntryError(
            f"s4_t01_runtime_resource_binding_drift:{resource_id}"
        )
    return observed


@dataclass(frozen=True)
class NaturalCaseEntryRequest:
    contract_ref: str
    case_key: str
    objective: str
    as_of: str
    freshness_policy_ref: str
    ticker: str
    company: str
    canonical_entity_ref: str
    program_cells: tuple[Mapping[str, str], ...]
    budget_ref: str
    request_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "case_key": self.case_key,
            "objective": self.objective,
            "as_of": self.as_of,
            "freshness_policy_ref": self.freshness_policy_ref,
            "ticker": self.ticker,
            "company": self.company,
            "canonical_entity_ref": self.canonical_entity_ref,
            "program_cells": [dict(row) for row in self.program_cells],
            "budget_ref": self.budget_ref,
            "request_digest": self.request_digest,
        }


@dataclass(frozen=True)
class CurrentCaseRuntimeBinding:
    contract_ref: str
    runtime_contract_ref: str
    runtime_binding_resource: Mapping[str, Any]
    runtime_source_resource: Mapping[str, Any]
    case_key: str
    binding_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "runtime_contract_ref": self.runtime_contract_ref,
            "runtime_binding_resource": dict(self.runtime_binding_resource),
            "runtime_source_resource": dict(self.runtime_source_resource),
            "case_key": self.case_key,
            "binding_digest": self.binding_digest,
        }


@dataclass(frozen=True)
class SourceIndexSnapshotBinding:
    contract_ref: str
    case_key: str
    source_snapshot: Mapping[str, Any]
    index_snapshot: Mapping[str, Any]
    qualification_status: str
    content_read_or_returned: bool
    binding_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "case_key": self.case_key,
            "source_snapshot": dict(self.source_snapshot),
            "index_snapshot": dict(self.index_snapshot),
            "qualification_status": self.qualification_status,
            "content_read_or_returned": self.content_read_or_returned,
            "binding_digest": self.binding_digest,
        }


@dataclass(frozen=True)
class ExactExecutionIdentityProjection:
    contract_ref: str
    case_key: str
    work_unit_id: str
    attempt_id: str
    research_run_id: str
    identity_seed_digest: str
    execution_claimed: bool
    reusable: bool
    projection_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "case_key": self.case_key,
            "work_unit_id": self.work_unit_id,
            "attempt_id": self.attempt_id,
            "research_run_id": self.research_run_id,
            "identity_seed_digest": self.identity_seed_digest,
            "execution_claimed": self.execution_claimed,
            "reusable": self.reusable,
            "projection_digest": self.projection_digest,
        }


@dataclass(frozen=True)
class S4T01EntryReceipt:
    contract_ref: str
    authority_digest: str
    case_key: str
    request_digest: str
    runtime_binding_digest: str
    snapshot_binding_digest: str
    identity_projection_digest: str
    entry_digest: str
    evidence_content_included: bool
    observed_counts: Mapping[str, int]
    T02_authorized: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "authority_digest": self.authority_digest,
            "case_key": self.case_key,
            "request_digest": self.request_digest,
            "runtime_binding_digest": self.runtime_binding_digest,
            "snapshot_binding_digest": self.snapshot_binding_digest,
            "identity_projection_digest": self.identity_projection_digest,
            "entry_digest": self.entry_digest,
            "evidence_content_included": self.evidence_content_included,
            "observed_counts": dict(self.observed_counts),
            "T02_authorized": self.T02_authorized,
        }


@dataclass(frozen=True)
class S4T01CompiledEntry:
    request: NaturalCaseEntryRequest
    runtime_binding: CurrentCaseRuntimeBinding
    snapshot_binding: SourceIndexSnapshotBinding
    identity_projection: ExactExecutionIdentityProjection
    receipt: S4T01EntryReceipt

    def as_dict(self) -> dict[str, Any]:
        return {
            "NaturalCaseEntryRequest": self.request.as_dict(),
            "CurrentCaseRuntimeBinding": self.runtime_binding.as_dict(),
            "SourceIndexSnapshotBinding": self.snapshot_binding.as_dict(),
            "ExactExecutionIdentityProjection": self.identity_projection.as_dict(),
            "S4T01EntryReceipt": self.receipt.as_dict(),
        }


def compile_fin_0_1_2_s4_t01_case_entry(
    *,
    authority: Mapping[str, Any],
    resources_by_id: Mapping[str, RuntimeResource | Mapping[str, Any]],
    case_key: str,
    occupied_identity_ids: Iterable[str] = (),
) -> S4T01CompiledEntry:
    normalized = _normalize_authority(authority)
    runtime = normalized["runtime_binding"]
    runtime_binding_resource = _assert_resource_binding(
        runtime["binding_resource"], resources_by_id
    )
    runtime_source_resource = _assert_resource_binding(
        runtime["source_resource"], resources_by_id
    )
    try:
        case = next(row for row in normalized["cases"] if row["case_key"] == case_key)
    except StopIteration as exc:
        raise Fin012S4T01EntryError("s4_t01_case_unknown") from exc
    source_snapshot = _assert_resource_binding(case["source_snapshot"], resources_by_id)
    index_snapshot = _assert_resource_binding(case["index_snapshot"], resources_by_id)
    budget = next(
        row for row in normalized["budgets"] if row["budget_ref"] == case["budget_ref"]
    )
    request_projection = {
        "contract_ref": CONTRACT_REF,
        "case_key": case["case_key"],
        "objective": case["objective"],
        "as_of": case["as_of"],
        "freshness_policy_ref": case["freshness_policy_ref"],
        "ticker": case["ticker"],
        "company": case["company"],
        "canonical_entity_ref": case["canonical_entity_ref"],
        "program_cells": case["program_cells"],
        "budget_ref": budget["budget_ref"],
    }
    request_digest = _digest(request_projection)
    request = NaturalCaseEntryRequest(
        contract_ref=CONTRACT_REF,
        case_key=case["case_key"],
        objective=case["objective"],
        as_of=case["as_of"],
        freshness_policy_ref=case["freshness_policy_ref"],
        ticker=case["ticker"],
        company=case["company"],
        canonical_entity_ref=case["canonical_entity_ref"],
        program_cells=tuple(dict(row) for row in case["program_cells"]),
        budget_ref=budget["budget_ref"],
        request_digest=request_digest,
    )
    runtime_projection = {
        "contract_ref": CONTRACT_REF,
        "runtime_contract_ref": runtime["binding_ref"],
        "runtime_binding_resource": runtime_binding_resource,
        "runtime_source_resource": runtime_source_resource,
        "case_key": case["case_key"],
    }
    runtime_binding = CurrentCaseRuntimeBinding(
        **runtime_projection,
        binding_digest=_digest(runtime_projection),
    )
    snapshot_projection = {
        "contract_ref": CONTRACT_REF,
        "case_key": case["case_key"],
        "source_snapshot": source_snapshot,
        "index_snapshot": index_snapshot,
        "qualification_status": "entry_bound_not_current_Evidence_T02_qualification_required",
        "content_read_or_returned": False,
    }
    snapshot_binding = SourceIndexSnapshotBinding(
        **snapshot_projection,
        binding_digest=_digest(snapshot_projection),
    )
    identity_seed_digest = _digest(
        {
            "contract_ref": CONTRACT_REF,
            "case_key": case["case_key"],
            "identity_seed": case["identity_seed"],
            "request_digest": request_digest,
            "runtime_binding_digest": runtime_binding.binding_digest,
            "snapshot_binding_digest": snapshot_binding.binding_digest,
        }
    )
    identity_ids = {
        "work_unit_id": f"wu_fin012_s4_t01_{identity_seed_digest[:24]}",
        "attempt_id": f"attempt_fin012_s4_t01_{identity_seed_digest[8:32]}",
        "research_run_id": f"research_run_fin012_s4_t01_{identity_seed_digest[16:40]}",
    }
    occupied = {str(value) for value in occupied_identity_ids}
    if occupied.intersection(identity_ids.values()):
        raise Fin012S4T01EntryError("s4_t01_execution_identity_reuse")
    identity_projection_base = {
        "contract_ref": CONTRACT_REF,
        "case_key": case["case_key"],
        **identity_ids,
        "identity_seed_digest": identity_seed_digest,
        "execution_claimed": False,
        "reusable": False,
    }
    identity_projection = ExactExecutionIdentityProjection(
        **identity_projection_base,
        projection_digest=_digest(identity_projection_base),
    )
    receipt_base = {
        "contract_ref": CONTRACT_REF,
        "authority_digest": normalized["authority_digest"],
        "case_key": case["case_key"],
        "request_digest": request_digest,
        "runtime_binding_digest": runtime_binding.binding_digest,
        "snapshot_binding_digest": snapshot_binding.binding_digest,
        "identity_projection_digest": identity_projection.projection_digest,
        "evidence_content_included": False,
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "execution_network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "execution_admissions": 0,
            "business_runs": 0,
            "business_artifacts": 0,
        },
        "T02_authorized": False,
    }
    receipt = S4T01EntryReceipt(
        **receipt_base,
        entry_digest=_digest(receipt_base),
    )
    return S4T01CompiledEntry(
        request=request,
        runtime_binding=runtime_binding,
        snapshot_binding=snapshot_binding,
        identity_projection=identity_projection,
        receipt=receipt,
    )


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / REGISTRY_REF).is_file():
            return parent
    raise Fin012S4T01EntryError("s4_t01_repository_root_not_found")


@lru_cache(maxsize=1)
def load_fin_0_1_2_s4_t01_authority_and_resources() -> tuple[
    dict[str, Any], Mapping[str, RuntimeResource]
]:
    root = _repository_root()
    try:
        registry = load_runtime_resource_registry(root, REGISTRY_REF)
        authority = read_registered_runtime_json(
            root,
            AUTHORITY_RESOURCE_ID,
            registry_ref=REGISTRY_REF,
        )
    except RuntimeResourceRegistryError as exc:
        raise Fin012S4T01EntryError("s4_t01_runtime_resource_authority_invalid") from exc
    return authority, registry.by_id()


def load_current_fin_0_1_2_s4_t01_case_entry(
    case_key: str,
    *,
    occupied_identity_ids: Iterable[str] = (),
) -> S4T01CompiledEntry:
    """Current Runtime consumer readback for the zero-call S4-T01 binding."""

    authority, resources = load_fin_0_1_2_s4_t01_authority_and_resources()
    return compile_fin_0_1_2_s4_t01_case_entry(
        authority=authority,
        resources_by_id=resources,
        case_key=case_key,
        occupied_identity_ids=occupied_identity_ids,
    )
