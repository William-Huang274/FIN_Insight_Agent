from __future__ import annotations

import argparse, hashlib, importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path: sys.path.insert(0, str(SRC_ROOT))
from sec_agent.canonical_runtime.evidence_gate import EvidenceGatePolicy, FixtureEvidenceGate, SemanticClassificationSuggestion

POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_6_evidence_gate_policy_v1_0.json"
REVIEW_PATH = ROOT / "configs/engineering_handoff/point01_m6_6_cross_owner_design_review_v1_0.json"
M6_5_PATH = ROOT / "scripts/engineering/run_point01_m6_5_parser_numeric_fixture.py"
M6_3_PATH = ROOT / "scripts/engineering/run_point01_m6_3_candidate_bundle_fixture.py"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_6_evidence_gate_fixture_result_v1_0.json"
PLAN_PATH = ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"
S5 = importlib.util.spec_from_file_location("m65_for_m66", M6_5_PATH); M5 = importlib.util.module_from_spec(S5); assert S5.loader; S5.loader.exec_module(M5)
S3 = importlib.util.spec_from_file_location("m63_for_m66", M6_3_PATH); M3 = importlib.util.module_from_spec(S3); assert S3.loader; S3.loader.exec_module(M3)

def _sha256(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def gate() -> FixtureEvidenceGate:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return FixtureEvidenceGate(policy=EvidenceGatePolicy(policy_ref=raw["policy_ref"], minimum_source_authority_rank_by_evidence_role=raw["minimum_source_authority_rank_by_evidence_role"]))
def numeric_inputs():
    bundle, observation = M5.inputs()
    parsed = M5.compiler().compile(bundle=bundle, observation=observation, metric_definition_ref="metric:segment_revenue:v1")
    request = M3.M6_2_RUNNER._request(sector="ai_semis").model_copy(update={"unit": "USD_millions"})
    return request, bundle, parsed
def relationship_inputs():
    request = M3.M6_2_RUNNER._request(sector="relationship", evidence_role="relationship_signal", source_policy_ref="relationship_graph_only", acceptance_role="bounded_context_only", forbidden_substitutions=("issuer_metric_substitute",), metric_scope=())
    registry, planner_policy = M3.M6_2_RUNNER.registry_and_policy()
    plan = M3.BoundedToolPlanner(registry=registry, policy=planner_policy).plan(request=request, permissions=M3.M6_2_RUNNER.permissions(registry)).plan
    snapshot = M3.CandidateMetadataSnapshot.create(snapshot_id="m66-relationship", candidates=(
        M3.CandidateMetadata(candidate_id="relation-seed", document_id="relationship", document_version="v1", source_snapshot_ref="fixture", source_policy_ref="relationship_graph_only", route_id="relationship_graph_metadata_route", source_role="relationship_graph", source_authority_rank=2, entity_ref="AAA", period_ref="latest_fiscal_period", candidate_kind="top_k_seed", section_or_table_ref="edge", metadata_rank=1, content_ref="object://fixture/edge"),
        M3.CandidateMetadata(candidate_id="relation-neighbor", document_id="relationship", document_version="v1", source_snapshot_ref="fixture", source_policy_ref="relationship_graph_only", route_id="relationship_graph_metadata_route", source_role="relationship_graph", source_authority_rank=2, entity_ref="AAA", period_ref="latest_fiscal_period", candidate_kind="neighbor_section", section_or_table_ref="neighbor", metadata_rank=2, content_ref="object://fixture/neighbor"),
    ))
    return request, M3.CandidateBundleCompiler(policy=M3.policy()).compile(request=request, plan=plan, snapshot=snapshot).bundle
def commercial_inputs():
    request = M3.M6_2_RUNNER._request(sector="commercial", evidence_role="commercial_tracker_metric", source_policy_ref="commercial_gap", acceptance_role="primary_or_bounded_context", forbidden_substitutions=("public_proxy_as_exact",), metric_scope=())
    registry, planner_policy = M3.M6_2_RUNNER.registry_and_policy(); plan=M3.BoundedToolPlanner(registry=registry,policy=planner_policy).plan(request=request,permissions=M3.M6_2_RUNNER.permissions(registry)).plan
    bundle=M3.CandidateBundleCompiler(policy=M3.policy()).compile(request=request,plan=plan,snapshot=M3.CandidateMetadataSnapshot.create(snapshot_id="m66-commercial",candidates=())).bundle
    return request,bundle
def build_result() -> dict[str, Any]:
    g=gate(); request,bundle,parsed=numeric_inputs(); suggestion=SemanticClassificationSuggestion(suggestion="numeric_fixture_consistent",rationale_ref="fixture-rule:v1")
    numeric=g.evaluate(request=request,bundle=bundle,parser_candidate=parsed.parser_candidate,fact=parsed.normalized_fact,trace=parsed.trace,suggestion=suggestion)
    hard=g.evaluate(request=request,bundle=bundle,parser_candidate=parsed.parser_candidate,fact=parsed.normalized_fact.model_copy(update={"unit":"percent"}),trace=parsed.trace,suggestion=suggestion)
    period=g.evaluate(request=request,bundle=bundle,parser_candidate=parsed.parser_candidate,fact=parsed.normalized_fact.model_copy(update={"period":"FY2025"}),trace=parsed.trace)
    scale=g.evaluate(request=request,bundle=bundle,parser_candidate=parsed.parser_candidate,fact=parsed.normalized_fact.model_copy(update={"scale_multiplier":0}),trace=parsed.trace)
    table = bundle.candidates[-1]
    entity_bundle=bundle.model_copy(update={"candidates":bundle.candidates[:-1]+(table.model_copy(update={"entity_ref":"OTHER"}),)})
    entity=g.evaluate(request=request,bundle=entity_bundle,parser_candidate=parsed.parser_candidate,fact=parsed.normalized_fact,trace=parsed.trace)
    authority_bundle=bundle.model_copy(update={"candidates":bundle.candidates[:-1]+(table.model_copy(update={"source_authority_rank":1}),)})
    authority=g.evaluate(request=request,bundle=authority_bundle,parser_candidate=parsed.parser_candidate,fact=parsed.normalized_fact,trace=parsed.trace)
    missing=g.evaluate(request=request,bundle=bundle,parser_candidate=parsed.parser_candidate,fact=parsed.normalized_fact,trace=None)
    rel_request,rel_bundle=relationship_inputs(); context=g.evaluate(request=rel_request,bundle=rel_bundle)
    relationship_fact=g.evaluate(request=rel_request,bundle=rel_bundle,parser_candidate=parsed.parser_candidate,fact=parsed.normalized_fact,trace=parsed.trace)
    com_request,com_bundle=commercial_inputs(); commercial=g.evaluate(request=com_request,bundle=com_bundle)
    conflict_candidate=bundle.candidates[-1].model_copy(update={"candidate_id":"conflicting-table","document_id":"other-filing"})
    conflict=g.evaluate(request=request,bundle=bundle.model_copy(update={"candidates": bundle.candidates+(conflict_candidate,)}),parser_candidate=parsed.parser_candidate,fact=parsed.normalized_fact,trace=parsed.trace)
    checks={
        "fixture_accepted_is_non_authoritative": numeric.decision.decision=="fixture_accepted_for_gate_simulation" and not numeric.decision.runtime_promotion_authorized and not numeric.decision.writer_citable and not numeric.decision.domain_judgment_eligible and not numeric.decision.persistence_authorized,
        "hard_rejection_cannot_be_overridden": hard.decision.decision=="rejected" and "unit_mismatch" in hard.decision.hard_failure_codes and hard.decision.classification_suggestion==suggestion,
        "entity_period_scale_authority_mismatches_rejected": entity.decision.decision=="rejected" and "entity_mismatch" in entity.decision.hard_failure_codes and "period_mismatch" in period.decision.hard_failure_codes and "scale_mismatch" in scale.decision.hard_failure_codes and "source_authority_below_minimum" in authority.decision.hard_failure_codes,
        "missing_trace_rejected": missing.decision.decision=="rejected" and "numeric_program_trace_required" in missing.decision.hard_failure_codes,
        "relationship_context_only_and_fact_rejected": context.decision.decision=="context_only" and relationship_fact.decision.decision=="rejected",
        "commercial_gap_not_proxy": commercial.decision.decision=="commercial_gap" and "commercial_gap_stop_rule" in commercial.decision.typed_gap_codes,
        "conflicts_are_typed_gap": conflict.decision.decision=="typed_gap" and conflict.decision.typed_gap_codes==("candidate_conflict_unresolved",),
        "lead_human_not_executed": numeric.decision.lead_human_status=="approval_required_not_executed",
        "execution_free": numeric.external_call_count==numeric.tool_invocation_count==numeric.store_write_count==0,
    }
    return {"result_version":"finsight_point01_m6_6_evidence_gate_fixture_result_v1_0","generated_at":datetime.now(timezone.utc).isoformat(),"scope":"Point01_M6_6_deterministic_fixture_evidence_gate","status":"pass" if all(checks.values()) else "fail_closed","checks":checks,"decisions":{"numeric":numeric.decision.model_dump(mode="json"),"hard_rejected":hard.decision.model_dump(mode="json"),"period":period.decision.model_dump(mode="json"),"scale":scale.decision.model_dump(mode="json"),"entity":entity.decision.model_dump(mode="json"),"authority":authority.decision.model_dump(mode="json"),"missing_trace":missing.decision.model_dump(mode="json"),"context":context.decision.model_dump(mode="json"),"commercial":commercial.decision.model_dump(mode="json"),"conflict":conflict.decision.model_dump(mode="json")},"authority_boundary":{"formal_evidence_promotion":False,"runtime_promotion_authorized":False,"writer_citable":False,"domain_judgment_eligible":False,"persistence_authorized":False,"lead_human_status":"approval_required_not_executed","model_call_count":0,"external_call_count":0,"tool_invocation_count":0,"store_write_count":0,"m6_7":"not_admitted"},"fixed_input_sha256":{"configs/engineering_handoff/point01_m6_6_evidence_gate_policy_v1_0.json":_sha256(POLICY_PATH),"configs/engineering_handoff/point01_m6_6_cross_owner_design_review_v1_0.json":_sha256(REVIEW_PATH),"scripts/engineering/run_point01_m6_6_evidence_gate_fixture.py":_sha256(Path(__file__)),"src/sec_agent/canonical_runtime/evidence_gate.py":_sha256(ROOT/'src/sec_agent/canonical_runtime/evidence_gate.py'),"docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md":_sha256(PLAN_PATH)},"boundary":"M6.6 emits only deterministic_fixture_only non-authoritative gate decisions. It neither promotes/persists formal evidence nor executes Lead/Human approval, model/tool/provider/network operations or M6.7 consumption."}
def main() -> int:
    p=argparse.ArgumentParser(description="Run M6.6 deterministic fixture evidence gate.");p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT);a=p.parse_args();o=a.output if a.output.is_absolute() else ROOT/a.output;r=build_result();o.parent.mkdir(parents=True,exist_ok=True);o.write_text(json.dumps(r,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps({"status":r["status"],"output":str(o),"checks":r["checks"]},ensure_ascii=False));return 0 if r["status"]=="pass" else 1
if __name__=="__main__": raise SystemExit(main())
