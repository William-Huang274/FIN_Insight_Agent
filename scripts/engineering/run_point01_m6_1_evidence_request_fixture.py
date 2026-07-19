from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.evidence_request import (
    EvidenceRequestCompileError,
    EvidenceRequestCompileOverrides,
    EvidenceRequestCompiler,
    EvidenceRequestPolicy,
)
from sec_agent.canonical_runtime.models import DecisionSurfaceCellVersion, DecisionSurfaceContractVersion, EvidenceSlotVersion
from sec_agent.canonical_runtime.planning_service import CompilerInputContract, DecisionCellSeed, DecisionSurfacePlanningService, EvidenceSlotSeed, PackSelectionDecision


POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_1_evidence_request_policy_v1_0.json"
REVIEW_PATH = ROOT / "configs/engineering_handoff/point01_m6_1_cross_owner_design_review_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_1_evidence_request_fixture_result_v1_0.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy() -> EvidenceRequestPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return EvidenceRequestPolicy.model_validate({key: value for key, value in raw.items() if key in {"policy_ref", "role_rules"}})


def _scope(sector: str) -> dict[str, Any]:
    now = datetime(2026, 7, 13, tzinfo=timezone.utc).isoformat()
    return {
        "tenant_id": "tenant-m6-1-fixture",
        "project_id": "project-m6-1-fixture",
        "case_id": f"case-m6-1-{sector}",
        "created_at": now,
        "recorded_at": now,
        "actor_snapshot_ref": "actor-m6-1-fixture",
        "permission_snapshot_ref": "permission-m6-1-fixture",
        "correlation_id": f"correlation-m6-1-{sector}",
    }


def planning_models(
    *,
    sector: str,
    evidence_role: str = "issuer_metric",
    source_policy_ref: str = "issuer_first",
    acceptance_role: str = "primary",
    forbidden_substitutions: tuple[str, ...] = ("relationship_graph_only",),
    metric_scope: tuple[str, ...] = ("revenue_growth",),
) -> tuple[DecisionSurfaceContractVersion, DecisionSurfaceCellVersion, EvidenceSlotVersion]:
    scope = _scope(sector)
    input_contract = CompilerInputContract(
        tenant_id=scope["tenant_id"],
        project_id=scope["project_id"],
        case_id=scope["case_id"],
        query=f"{sector} decision surface request fixture",
        as_of=datetime(2026, 7, 13, tzinfo=timezone.utc),
        universe=("AAA",),
        language="en",
        compiler_policy_ref="point01-m2-fixture-policy",
        pack_selection=PackSelectionDecision(universal_pack_refs=("universal-core:v1",), sector_pack_refs=(f"sector-{sector}:v1",)),
        required_cells=(
            DecisionCellSeed(
                cell_key=f"{sector}_cell",
                decision_question=f"{sector} material decision question",
                origin_type="m6_1_fixture",
                owner_role="fundamental_analyst",
                materiality="high",
                stop_rule="accepted primary route or typed gap",
                evidence_slots=(
                    EvidenceSlotSeed(
                        evidence_role=evidence_role,
                        entity_scope=("AAA",),
                        period_scope="latest_fiscal_period",
                        metric_scope=metric_scope,
                        source_policy_ref=source_policy_ref,
                        forbidden_substitutions=forbidden_substitutions,
                        acceptance_role=acceptance_role,
                    ),
                ),
            ),
        ),
    )
    bundle = DecisionSurfacePlanningService(None).compile_deterministic_fixture(input_contract, audit_scope=scope)  # type: ignore[arg-type]
    return (
        DecisionSurfaceContractVersion.model_validate(bundle["contract"]),
        DecisionSurfaceCellVersion.model_validate(bundle["cells"][0]),
        EvidenceSlotVersion.model_validate(bundle["slots"][0]),
    )


def _expect_error(callback: Any) -> str:
    try:
        callback()
    except EvidenceRequestCompileError as error:
        return str(error)
    raise AssertionError("expected_evidence_request_compile_error")


def build_result() -> dict[str, Any]:
    compiler = EvidenceRequestCompiler(_policy())
    positive: dict[str, dict[str, Any]] = {}
    for sector in ("ai_semis", "saas", "healthcare", "banks"):
        contract, cell, slot = planning_models(sector=sector)
        result = compiler.compile(
            contract=contract,
            cell=cell,
            slot=slot,
            overrides=EvidenceRequestCompileOverrides(product_intent=(f"{sector}_product",)),
        )
        replay = compiler.compile(
            contract=contract,
            cell=cell,
            slot=slot,
            overrides=EvidenceRequestCompileOverrides(product_intent=(f"{sector}_product",)),
        )
        positive[sector] = {
            "request_id": result.request.request_id,
            "request_digest": result.request.request_digest,
            "accepted_evidence_role": result.request.accepted_evidence_role,
            "numeric_binding_requirements": result.request.numeric_binding_requirements,
            "replay_digest_match": result.request.request_digest == replay.request.request_digest,
        }

    relationship_contract, relationship_cell, relationship_slot = planning_models(
        sector="relationship",
        evidence_role="relationship_signal",
        source_policy_ref="relationship_graph_only",
        acceptance_role="bounded_context_only",
        forbidden_substitutions=("issuer_metric_substitute",),
        metric_scope=(),
    )
    relationship = compiler.compile(contract=relationship_contract, cell=relationship_cell, slot=relationship_slot)

    contract, cell, slot = planning_models(sector="negative")
    bad_parent_slot = slot.model_copy(update={"cell_version_id": "other-cell:v1"})
    missing_forbidden_slot = slot.model_copy(update={"forbidden_substitutions": ()})
    invalid_source_slot = slot.model_copy(update={"source_policy_ref": "news_first"})
    negative = {
        "bad_parent": _expect_error(lambda: compiler.compile(contract=contract, cell=cell, slot=bad_parent_slot)),
        "missing_forbidden": _expect_error(lambda: compiler.compile(contract=contract, cell=cell, slot=missing_forbidden_slot)),
        "invalid_source": _expect_error(lambda: compiler.compile(contract=contract, cell=cell, slot=invalid_source_slot)),
        "wrong_requester": _expect_error(
            lambda: compiler.compile(
                contract=contract,
                cell=cell,
                slot=slot,
                overrides=EvidenceRequestCompileOverrides(requester_role="memo_writer"),
            )
        ),
    }
    checks = {
        "four_sector_positive_corpus": len(positive) == 4 and all(row["accepted_evidence_role"] == "numeric_fact" for row in positive.values()),
        "exact_version_replay": all(bool(row["replay_digest_match"]) for row in positive.values()),
        "numeric_and_metadata_contract": all(len(row["numeric_binding_requirements"]) == 4 for row in positive.values()),
        "relationship_context_only": relationship.request.accepted_evidence_role == "context" and not relationship.request.numeric_binding_requirements,
        "lineage_and_policy_negatives": negative == {
            "bad_parent": "slot_parent_cell_version_mismatch",
            "missing_forbidden": "required_forbidden_substitution_missing:relationship_graph_only",
            "invalid_source": "source_policy_not_allowed:news_first",
            "wrong_requester": "requester_role_must_match_cell_owner",
        },
        "no_execution": relationship.model_call_count == 0 and relationship.external_call_count == 0 and relationship.store_write_count == 0,
    }
    return {
        "result_version": "finsight_point01_m6_1_evidence_request_fixture_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Point01_M6_1_deterministic_cell_slot_to_evidence_request",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "checks": checks,
        "positive": positive,
        "relationship_context_request": relationship.request.model_dump(mode="json"),
        "negative": negative,
        "authority_boundary": {
            "legacy_task_run": "authoritative",
            "decision_surface_input": "read_only_exact_version",
            "evidence_request_persistence": "not_admitted",
            "tool_registry_execution": "not_admitted",
            "provider_execution": False,
            "external_tool_execution": False,
            "model_call_count": 0,
            "external_call_count": 0,
            "store_write_count": 0,
            "evidence_promotion": "M6_6_not_implemented",
            "writer_full_chain": "not_admitted"
        },
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m6_1_evidence_request_policy_v1_0.json": _sha256(POLICY_PATH),
            "configs/engineering_handoff/point01_m6_1_cross_owner_design_review_v1_0.json": _sha256(REVIEW_PATH),
            "scripts/engineering/run_point01_m6_1_evidence_request_fixture.py": _sha256(Path(__file__).resolve()),
            "src/sec_agent/canonical_runtime/evidence_request.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/evidence_request.py"),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md")
        },
        "boundary": "M6.1 compiles deterministic request contracts only. It does not persist EvidenceRequest, retrieve candidates, select or execute tools, call a provider, parse/promote evidence, write a report, mutate a business Case or change legacy authority."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M6.1 EvidenceRequest compiler fixture.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output), "checks": result["checks"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
