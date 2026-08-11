from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.fin_0_1_2_s4_natural_case_entry import (
    CONTRACT_REF,
    EXPECTED_PROGRAM_CELL_IDS,
    Fin012S4T01EntryError,
    compile_fin_0_1_2_s4_t01_case_entry,
    load_current_fin_0_1_2_s4_t01_case_entry,
    load_fin_0_1_2_s4_t01_authority_and_resources,
)
from sec_agent.runtime_resource_registry import load_runtime_resource_registry


AUTHORITY = ROOT / (
    "configs/runtime/fin_ia_0_1_2_s4_t01_"
    "natural_case_entry_authority_v1_0.json"
)
REGISTRY = ROOT / (
    "configs/runtime/fin_ia_0_1_2_s4_t01_"
    "runtime_resource_registry_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _refresh_authority_digest(payload: dict) -> dict:
    refreshed = deepcopy(payload)
    refreshed["budgets"] = sorted(
        refreshed["budgets"], key=lambda row: row["budget_ref"]
    )
    for case in refreshed["cases"]:
        case["program_cells"] = sorted(
            case["program_cells"], key=lambda row: row["program_cell_id"]
        )
    refreshed["cases"] = sorted(
        refreshed["cases"], key=lambda row: row["case_key"]
    )
    projection = {
        key: value for key, value in refreshed.items() if key != "authority_digest"
    }
    refreshed["authority_digest"] = _canonical_digest(projection)
    return refreshed


def _compile(payload: dict, case_key: str = "DELL", *, occupied=()):
    _, resources = load_fin_0_1_2_s4_t01_authority_and_resources()
    return compile_fin_0_1_2_s4_t01_case_entry(
        authority=payload,
        resources_by_id=resources,
        case_key=case_key,
        occupied_identity_ids=occupied,
    )


def test_runtime_registry_and_current_consumer_read_all_three_case_bindings() -> None:
    registry = load_runtime_resource_registry(ROOT, REGISTRY.relative_to(ROOT).as_posix())
    assert registry.registry_id == (
        "FIN-0.1.2-S4-T01-NATURAL-CASE-ENTRY-RUNTIME-RESOURCE-REGISTRY-R1"
    )
    assert len(registry.resources) == 7
    outputs = {
        case_key: load_current_fin_0_1_2_s4_t01_case_entry(case_key)
        for case_key in ("DELL", "MU", "NVDA")
    }
    assert len({row.receipt.entry_digest for row in outputs.values()}) == 3
    assert len(
        {row.identity_projection.work_unit_id for row in outputs.values()}
    ) == 3
    for case_key, compiled in outputs.items():
        assert compiled.request.contract_ref == CONTRACT_REF
        assert compiled.request.case_key == case_key
        assert tuple(
            sorted(row["program_cell_id"] for row in compiled.request.program_cells)
        ) == tuple(sorted(EXPECTED_PROGRAM_CELL_IDS))
        assert compiled.identity_projection.execution_claimed is False
        assert compiled.identity_projection.reusable is False
        assert compiled.receipt.T02_authorized is False
        assert set(compiled.receipt.observed_counts.values()) == {0}


def test_receipt_contains_only_snapshot_metadata_and_never_evidence_content() -> None:
    for case_key in ("DELL", "MU", "NVDA"):
        compiled = load_current_fin_0_1_2_s4_t01_case_entry(case_key)
        output = compiled.as_dict()
        serialized = json.dumps(output, ensure_ascii=False, sort_keys=True)
        assert compiled.snapshot_binding.content_read_or_returned is False
        assert compiled.snapshot_binding.qualification_status == (
            "entry_bound_not_current_Evidence_T02_qualification_required"
        )
        assert compiled.receipt.evidence_content_included is False
        for forbidden in (
            '"evidence_rows"',
            '"numeric_rows"',
            '"claims"',
            '"judgments"',
            '"assistant_output"',
        ):
            assert forbidden not in serialized


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("objective", "s4_t01_authority_digest_mismatch"),
        ("as_of", "s4_t01_authority_digest_mismatch"),
        ("ticker", "s4_t01_case_identity_invalid"),
        ("cell", "s4_t01_program_cell_set_invalid"),
        (
            "source_snapshot",
            "s4_t01_unknown_runtime_resource:unknown.snapshot",
        ),
        ("budget", "s4_t01_external_budget_not_zero"),
        ("identity", "s4_t01_authority_digest_mismatch"),
        (
            "runtime_head",
            "s4_t01_runtime_resource_binding_drift:"
            "fin_0_1_2.s4.t01.current_runtime_binding",
        ),
    ],
)
def test_objective_as_of_case_cell_snapshot_budget_identity_and_head_mutations_fail_closed(
    mutation: str, expected_code: str
) -> None:
    payload = _load(AUTHORITY)
    case = payload["cases"][0]
    refresh = False
    if mutation == "objective":
        case["objective"] += "（被篡改）"
    elif mutation == "as_of":
        case["as_of"] = "2026-07-27T00:00:00Z"
    elif mutation == "ticker":
        case["ticker"] = "MU"
        refresh = True
    elif mutation == "cell":
        case["program_cells"][0]["program_cell_id"] = "unknown_cell"
        refresh = True
    elif mutation == "source_snapshot":
        case["source_snapshot"]["resource_id"] = "unknown.snapshot"
        refresh = True
    elif mutation == "budget":
        payload["budgets"][0]["model_calls"] = 1
        refresh = True
    elif mutation == "identity":
        case["identity_seed"] += "-changed"
    elif mutation == "runtime_head":
        payload["runtime_binding"]["binding_resource"]["sha256"] = "f" * 64
        refresh = True
    if refresh:
        payload = _refresh_authority_digest(payload)
    with pytest.raises(Fin012S4T01EntryError) as exc:
        _compile(payload)
    assert exc.value.code == expected_code


def test_cross_case_contamination_and_internal_fixture_objective_fail_semantically() -> None:
    payload = _load(AUTHORITY)
    dell = payload["cases"][0]
    dell["ticker"] = "MU"
    dell["company"] = "Micron Technology, Inc."
    dell["canonical_entity_ref"] = "MU"
    payload = _refresh_authority_digest(payload)
    with pytest.raises(Fin012S4T01EntryError) as exc:
        _compile(payload)
    assert exc.value.code == "s4_t01_case_identity_invalid"

    payload = _load(AUTHORITY)
    payload["cases"][0]["objective"] = (
        "Execute the FIN S4-T01 internal fixture preflight for the DELL test case."
    )
    payload = _refresh_authority_digest(payload)
    with pytest.raises(Fin012S4T01EntryError) as exc:
        _compile(payload)
    assert exc.value.code == "s4_t01_objective_not_natural"


def test_duplicate_execution_identity_is_rejected_before_claim_or_run() -> None:
    payload = _load(AUTHORITY)
    first = _compile(payload, "MU")
    occupied = {
        first.identity_projection.work_unit_id,
        first.identity_projection.attempt_id,
        first.identity_projection.research_run_id,
    }
    with pytest.raises(Fin012S4T01EntryError) as exc:
        _compile(payload, "MU", occupied=occupied)
    assert exc.value.code == "s4_t01_execution_identity_reuse"


def test_case_and_cell_permutation_preserves_all_compiled_digests() -> None:
    payload = _load(AUTHORITY)
    original = {
        key: _compile(payload, key).as_dict() for key in ("DELL", "MU", "NVDA")
    }
    permuted = deepcopy(payload)
    permuted["cases"].reverse()
    for case in permuted["cases"]:
        case["program_cells"].reverse()
    observed = {
        key: _compile(permuted, key).as_dict()
        for key in ("DELL", "MU", "NVDA")
    }
    assert observed == original


def test_snapshot_and_runtime_binding_are_exact_content_addressed_refs() -> None:
    authority, resources = load_fin_0_1_2_s4_t01_authority_and_resources()
    for case in authority["cases"]:
        compiled = compile_fin_0_1_2_s4_t01_case_entry(
            authority=authority,
            resources_by_id=resources,
            case_key=case["case_key"],
        )
        for binding in (
            compiled.runtime_binding.runtime_binding_resource,
            compiled.runtime_binding.runtime_source_resource,
            compiled.snapshot_binding.source_snapshot,
            compiled.snapshot_binding.index_snapshot,
        ):
            path = ROOT / binding["repo_relative_path"]
            assert path.stat().st_size == binding["bytes"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"]


def test_unknown_case_fails_without_side_effects() -> None:
    payload = _load(AUTHORITY)
    with pytest.raises(Fin012S4T01EntryError) as exc:
        _compile(payload, "AMD")
    assert exc.value.code == "s4_t01_case_unknown"
