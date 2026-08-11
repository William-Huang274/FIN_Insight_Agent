from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]; SRC_ROOT=ROOT/'src'
if str(SRC_ROOT) not in sys.path: sys.path.insert(0,str(SRC_ROOT))
from sec_agent.canonical_runtime.parser_numeric import ParserNumericFixtureCompiler, ParserNumericPolicy, NumericFixtureObservation
POLICY_PATH=ROOT/'configs/engineering_handoff/point01_m6_5_parser_numeric_policy_v1_0.json'; REVIEW_PATH=ROOT/'configs/engineering_handoff/point01_m6_5_cross_owner_design_review_v1_0.json'; M6_3=ROOT/'scripts/engineering/run_point01_m6_3_candidate_bundle_fixture.py'; DEFAULT_OUTPUT=ROOT/'data/manifests/point01_m6_5_parser_numeric_fixture_result_v1_0.json'
SPEC=importlib.util.spec_from_file_location('m63',M6_3); M=importlib.util.module_from_spec(SPEC); assert SPEC.loader; SPEC.loader.exec_module(M)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def compiler():
 r=json.loads(POLICY_PATH.read_text(encoding='utf-8')); return ParserNumericFixtureCompiler(policy=ParserNumericPolicy(policy_ref=r['policy_ref'],allowed_units=tuple(r['allowed_units']),allowed_scales=tuple(r['allowed_scales'])))
def inputs():
 req,plan=M.issuer_request_and_plan(); bundle=M.CandidateBundleCompiler(policy=M.policy()).compile(request=req,plan=plan,snapshot=M.metadata_snapshot()).bundle
 obs=NumericFixtureObservation(candidate_id='candidate-filing-table',raw_value='1,234.50',row_label='Segment revenue',unit='USD_millions',period='latest_fiscal_period',source_coordinate='SegmentRevenueTable:r12c4',scale_multiplier=1000000); return bundle,obs
def build_result():
 bundle,obs=inputs(); first=compiler().compile(bundle=bundle,observation=obs,metric_definition_ref='metric:segment_revenue:v1'); second=compiler().compile(bundle=bundle,observation=obs,metric_definition_ref='metric:segment_revenue:v1')
 checks={'exact_table_row_unit_period_trace':first.normalized_fact.normalized_value=='1234.50' and first.normalized_fact.promotion_status=='unpromoted' and first.trace.program_steps==('decimal_parse','unit_preserved','scale_preserved'),'replay_digest_match':first.trace.trace_digest==second.trace.trace_digest,'execution_free':first.external_call_count==first.store_write_count==0}
 return {'result_version':'finsight_point01_m6_5_parser_numeric_fixture_result_v1_0','generated_at':datetime.now(timezone.utc).isoformat(),'scope':'Point01_M6_5_deterministic_fixture_parser_numeric_trace','status':'pass' if all(checks.values()) else 'fail_closed','checks':checks,'artifacts':{'parser_candidate':first.parser_candidate.model_dump(mode='json'),'normalized_fact':first.normalized_fact.model_dump(mode='json'),'trace':first.trace.model_dump(mode='json')},'authority_boundary':{'document_content_read':'fixture_only','live_parser_or_ocr':False,'numeric_fact_persistence':'not_admitted','evidence_promotion':'M6_6_not_implemented','model_call_count':0,'external_call_count':0,'store_write_count':0,'writer_full_chain':'not_admitted'},'fixed_input_sha256':{'configs/engineering_handoff/point01_m6_5_parser_numeric_policy_v1_0.json':sha(POLICY_PATH),'configs/engineering_handoff/point01_m6_5_cross_owner_design_review_v1_0.json':sha(REVIEW_PATH),'scripts/engineering/run_point01_m6_5_parser_numeric_fixture.py':sha(Path(__file__)),'src/sec_agent/canonical_runtime/parser_numeric.py':sha(ROOT/'src/sec_agent/canonical_runtime/parser_numeric.py')},'boundary':'M6.5 parses a supplied fixture observation against a CandidateBundle table-context ref only. It does not read documents, call parser/OCR/network/provider, persist facts, promote evidence, write output or mutate authority.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);a=p.parse_args();o=a.output if a.output.is_absolute() else ROOT/a.output; r=build_result();o.parent.mkdir(parents=True,exist_ok=True);o.write_text(json.dumps(r,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'status':r['status'],'output':str(o),'checks':r['checks']},ensure_ascii=False));return 0 if r['status']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
