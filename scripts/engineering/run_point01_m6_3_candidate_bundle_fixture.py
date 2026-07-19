from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.candidate_bundle import CandidateBundleCompiler, CandidateBundlePolicy, CandidateMetadata, CandidateMetadataSnapshot
from sec_agent.canonical_runtime.tool_planner import BoundedToolPlanner


POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_3_candidate_bundle_policy_v1_0.json"
REVIEW_PATH = ROOT / "configs/engineering_handoff/point01_m6_3_cross_owner_design_review_v1_0.json"
M6_2_RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_2_tool_planner_fixture.py"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_3_candidate_bundle_fixture_result_v1_0.json"

SPEC = importlib.util.spec_from_file_location("point01_m6_2_fixture_for_m6_3", M6_2_RUNNER_PATH)
assert SPEC and SPEC.loader
M6_2_RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M6_2_RUNNER)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy() -> CandidateBundlePolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return CandidateBundlePolicy.model_validate(
        {
            "policy_ref": raw["policy_ref"],
            "minimum_source_authority_rank_by_evidence_role": raw["minimum_source_authority_rank_by_evidence_role"],
            "required_candidate_kinds_by_evidence_role": raw["required_candidate_kinds_by_evidence_role"],
            "allowed_candidate_kinds": raw["allowed_candidate_kinds"],
            "allowed_bundle_statuses": raw["allowed_bundle_statuses"],
        }
    )


def issuer_request_and_plan(*, sector: str = "ai_semis"):
    snapshot, planner_policy = M6_2_RUNNER.registry_and_policy()
    request = M6_2_RUNNER._request(sector=sector)
    plan = BoundedToolPlanner(registry=snapshot, policy=planner_policy).plan(
        request=request,
        permissions=M6_2_RUNNER.permissions(snapshot),
    ).plan
    return request, plan


def metadata_snapshot(*, include_table: bool = True, route_id: str = "issuer_disclosure_metadata_route") -> CandidateMetadataSnapshot:
    candidates = [
        CandidateMetadata(candidate_id="candidate-filing-seed", document_id="issuer-10q", document_version="2026q1", source_snapshot_ref="fixture-source-snapshot-1", source_policy_ref="issuer_first", route_id=route_id, source_role="issuer_disclosure", source_authority_rank=5, entity_ref="AAA", period_ref="latest_fiscal_period", candidate_kind="top_k_seed", section_or_table_ref="MD&A", metadata_rank=1, content_ref="object://fixture/issuer-10q#mdna"),
        CandidateMetadata(candidate_id="candidate-filing-neighbor", document_id="issuer-10q", document_version="2026q1", source_snapshot_ref="fixture-source-snapshot-1", source_policy_ref="issuer_first", route_id=route_id, source_role="issuer_disclosure", source_authority_rank=5, entity_ref="AAA", period_ref="latest_fiscal_period", candidate_kind="neighbor_section", section_or_table_ref="ResultsOfOperations", metadata_rank=2, content_ref="object://fixture/issuer-10q#results"),
    ]
    if include_table:
        candidates.append(CandidateMetadata(candidate_id="candidate-filing-table", document_id="issuer-10q", document_version="2026q1", source_snapshot_ref="fixture-source-snapshot-1", source_policy_ref="issuer_first", route_id=route_id, source_role="issuer_disclosure", source_authority_rank=5, entity_ref="AAA", period_ref="latest_fiscal_period", candidate_kind="table_context", section_or_table_ref="SegmentRevenueTable", metadata_rank=3, content_ref="object://fixture/issuer-10q#segment-revenue"))
    return CandidateMetadataSnapshot.create(snapshot_id="candidate-metadata-fixture-v1", candidates=candidates)


def build_result() -> dict[str, Any]:
    compiler = CandidateBundleCompiler(policy=policy())
    request, plan = issuer_request_and_plan()
    snapshot = metadata_snapshot()
    first = compiler.compile(request=request, plan=plan, snapshot=snapshot)
    second = compiler.compile(request=request, plan=plan, snapshot=snapshot)
    missing_table = compiler.compile(request=request, plan=plan, snapshot=metadata_snapshot(include_table=False))
    empty_snapshot = CandidateMetadataSnapshot.create(snapshot_id="empty-metadata-fixture-v1", candidates=())
    exhausted = compiler.compile(request=request, plan=plan, snapshot=empty_snapshot)
    relationship_request = M6_2_RUNNER._request(sector="relationship", evidence_role="relationship_signal", source_policy_ref="relationship_graph_only", acceptance_role="bounded_context_only", forbidden_substitutions=("issuer_metric_substitute",), metric_scope=())
    registry, planner_policy = M6_2_RUNNER.registry_and_policy()
    relationship_plan = BoundedToolPlanner(registry=registry, policy=planner_policy).plan(request=relationship_request, permissions=M6_2_RUNNER.permissions(registry)).plan
    relationship_snapshot = CandidateMetadataSnapshot.create(
        snapshot_id="relationship-metadata-fixture-v1",
        candidates=(
            CandidateMetadata(candidate_id="relationship-seed", document_id="relationship-edge", document_version="v1", source_snapshot_ref="relationship-snapshot-v1", source_policy_ref="relationship_graph_only", route_id="relationship_graph_metadata_route", source_role="relationship_graph", source_authority_rank=2, entity_ref="AAA", period_ref="latest_fiscal_period", candidate_kind="top_k_seed", section_or_table_ref="edge", metadata_rank=1, content_ref="object://fixture/relationship#edge"),
            CandidateMetadata(candidate_id="relationship-neighbor", document_id="relationship-edge", document_version="v1", source_snapshot_ref="relationship-snapshot-v1", source_policy_ref="relationship_graph_only", route_id="relationship_graph_metadata_route", source_role="relationship_graph", source_authority_rank=2, entity_ref="AAA", period_ref="latest_fiscal_period", candidate_kind="neighbor_section", section_or_table_ref="neighbor-edge", metadata_rank=2, content_ref="object://fixture/relationship#neighbor"),
        ),
    )
    relationship = compiler.compile(request=relationship_request, plan=relationship_plan, snapshot=relationship_snapshot)
    commercial_request = M6_2_RUNNER._request(sector="commercial", evidence_role="commercial_tracker_metric", source_policy_ref="commercial_gap", acceptance_role="primary_or_bounded_context", forbidden_substitutions=("public_proxy_as_exact",), metric_scope=())
    commercial_plan = BoundedToolPlanner(registry=registry, policy=planner_policy).plan(request=commercial_request, permissions=M6_2_RUNNER.permissions(registry)).plan
    commercial = compiler.compile(request=commercial_request, plan=commercial_plan, snapshot=empty_snapshot)
    checks = {
        "issuer_topk_neighbor_table_metadata_bundle": first.bundle.status == "metadata_fixture_compiled" and first.bundle.top_k_candidate_ids == ("candidate-filing-seed",) and first.bundle.neighbor_candidate_ids == ("candidate-filing-neighbor",) and first.bundle.table_context_candidate_ids == ("candidate-filing-table",),
        "replay_digest_match": first.bundle.bundle_digest == second.bundle.bundle_digest,
        "missing_table_is_typed_exhaustion": missing_table.bundle.status == "retrieval_exhausted" and missing_table.bundle.typed_gap_codes == ("required_context_kind_missing:table_context",),
        "empty_metadata_is_typed_exhaustion": exhausted.bundle.status == "retrieval_exhausted" and exhausted.bundle.exhaustion_status == "metadata_candidate_absent",
        "relationship_context_bundle_has_no_table_requirement": relationship.bundle.status == "metadata_fixture_compiled" and relationship.bundle.table_context_candidate_ids == (),
        "commercial_stop_is_not_retrieval": commercial.bundle.status == "not_attempted_typed_stop" and commercial.bundle.typed_gap_codes == ("commercial_gap_stop_rule",),
        "execution_free": first.retrieval_call_count == 0 and first.external_call_count == 0 and first.store_write_count == 0 and plan.steps[0].invocation_status == "not_executed",
    }
    return {
        "result_version": "finsight_point01_m6_3_candidate_bundle_fixture_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Point01_M6_3_deterministic_metadata_candidate_bundle",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "checks": checks,
        "bundles": {"issuer": first.bundle.model_dump(mode="json"), "missing_table": missing_table.bundle.model_dump(mode="json"), "empty": exhausted.bundle.model_dump(mode="json"), "relationship": relationship.bundle.model_dump(mode="json"), "commercial": commercial.bundle.model_dump(mode="json")},
        "authority_boundary": {"candidate_bundle_persistence": "not_admitted", "tool_invocation_count": 0, "rag_sql_graph_retrieval": False, "provider_execution": False, "external_tool_execution": False, "model_call_count": 0, "retrieval_call_count": 0, "external_call_count": 0, "store_write_count": 0, "parser_numeric_promotion": "M6_5_M6_6_not_implemented", "writer_full_chain": "not_admitted"},
        "fixed_input_sha256": {"configs/engineering_handoff/point01_m6_3_candidate_bundle_policy_v1_0.json": _sha256(POLICY_PATH), "configs/engineering_handoff/point01_m6_3_cross_owner_design_review_v1_0.json": _sha256(REVIEW_PATH), "scripts/engineering/run_point01_m6_3_candidate_bundle_fixture.py": _sha256(Path(__file__).resolve()), "src/sec_agent/canonical_runtime/candidate_bundle.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/candidate_bundle.py"), "src/sec_agent/canonical_runtime/tool_planner.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/tool_planner.py"), "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md")},
        "boundary": "M6.3 compiles an ephemeral CandidateBundle from supplied fixture-only metadata. It does not invoke a tool, perform RAG/SQL/graph retrieval, read document content, parse/normalize a number, promote evidence, persist a bundle, write a report, mutate a business Case or change legacy authority."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M6.3 deterministic CandidateBundle fixture.")
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
