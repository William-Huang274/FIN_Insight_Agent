from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.evidence_policy import (  # noqa: E402
    EvidenceRoleRule,
    EvidenceSlotPolicyCompiler,
    SectorEvidenceOntology,
    SlotCompilationInput,
)
from sec_agent.canonical_runtime.planning_service import EvidenceSlotSeed  # noqa: E402


ONTOLOGY_PATH = ROOT / "configs/engineering_handoff/point01_m2_6_evidence_slot_policy_ontology_v1_0.json"
PLAN_PATH = ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m2_6_evidence_slot_policy_fixture_result_v1_0.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compiler() -> EvidenceSlotPolicyCompiler:
    raw = json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))
    rules = {name: EvidenceRoleRule.model_validate(value) for name, value in raw["evidence_role_rules"].items()}
    return EvidenceSlotPolicyCompiler({sector: SectorEvidenceOntology(sector=sector, evidence_role_rules=rules) for sector in raw["sectors"]})


def _slot(slot_key: str, role: str, source: str, acceptance: str, forbidden: tuple[str, ...]) -> SlotCompilationInput:
    return SlotCompilationInput(
        cell_key="cell-1",
        slot_key=slot_key,
        slot=EvidenceSlotSeed(
            evidence_role=role,
            entity_scope=("AAA",),
            period_scope="latest_fiscal_period",
            metric_scope=("metric",),
            source_policy_ref=source,
            forbidden_substitutions=forbidden,
            acceptance_role=acceptance,
        ),
    )


def build_result() -> dict[str, Any]:
    compiler = _compiler()
    sectors = ("ai_semis", "saas", "healthcare", "banks")
    positives = {
        sector: compiler.compile(
            sector=sector,
            slots=(_slot("issuer-slot", "issuer_metric", "issuer_first", "primary", ("relationship_graph_only",)),),
            available_parser_source_policy_refs=("issuer_first",),
        )
        for sector in sectors
    }
    parser_gap = compiler.compile(
        sector="ai_semis",
        slots=(_slot("parser-slot", "issuer_metric", "filing_first", "primary", ("relationship_graph_only",)),),
        available_parser_source_policy_refs=("issuer_first",),
    )
    relationship_overreach = compiler.compile(
        sector="saas",
        slots=(_slot("relationship-slot", "relationship_signal", "relationship_graph_only", "primary", ("issuer_metric_substitute",)),),
        available_parser_source_policy_refs=(),
    )
    commercial_gap = compiler.compile(
        sector="healthcare",
        slots=(_slot("commercial-slot", "commercial_tracker_metric", "commercial_gap", "primary_or_bounded_context", ("public_proxy_as_exact",)),),
        available_parser_source_policy_refs=(),
    )
    checks = {
        "four_sector_ready_slots": all(result.status == "pass" for result in positives.values()),
        "parser_gap_typed": parser_gap.status == "pass_with_typed_gaps" and any(gap.gap_type == "parser_gap" for gap in parser_gap.gaps),
        "relationship_overreach_rejected": relationship_overreach.status == "fail" and "relationship_scope_overreach:relationship-slot" in relationship_overreach.errors,
        "commercial_gap_typed": commercial_gap.status == "pass_with_typed_gaps" and any(gap.gap_type == "commercial_data_gap" for gap in commercial_gap.gaps),
        "model_free": all(result.model_call_count == 0 and result.external_call_count == 0 for result in (*positives.values(), parser_gap, relationship_overreach, commercial_gap)),
    }
    return {
        "result_version": "finsight_point01_m2_6_evidence_slot_policy_fixture_result_v1_0",
        "scope": "Point01_M2_6_evidence_slot_stop_source_policy",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "checks": checks,
        "positive_sectors": {sector: result.model_dump(mode="json") for sector, result in positives.items()},
        "parser_gap": parser_gap.model_dump(mode="json"),
        "relationship_overreach": relationship_overreach.model_dump(mode="json"),
        "commercial_gap": commercial_gap.model_dump(mode="json"),
        "authority_boundary": {"legacy_task_run": "authoritative", "canonical_lane": "shadow_only", "model_call_count": 0, "external_call_count": 0},
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m2_6_evidence_slot_policy_ontology_v1_0.json": _sha256(ONTOLOGY_PATH),
            "scripts/engineering/run_point01_m2_6_evidence_slot_policy_fixture.py": _sha256(Path(__file__).resolve()),
            "src/sec_agent/canonical_runtime/evidence_policy.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/evidence_policy.py"),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(PLAN_PATH),
        },
        "boundary": "Policy compilation returns ready slots or typed gaps only. It does not retrieve evidence, promote a relationship signal, call a model, write legacy state or change authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M2.6 evidence-slot policy fixture.")
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
