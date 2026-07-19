from __future__ import annotations
import importlib.util,json,subprocess,sys
from pathlib import Path
import pytest
from pydantic import ValidationError
from sec_agent.canonical_runtime.evidence_gate import EvidenceGateError, EvidencePromotionDecision, SemanticClassificationSuggestion, reject_formal_evidence_consumer
ROOT=Path(__file__).resolve().parents[2]; PATH=ROOT/'scripts/engineering/run_point01_m6_6_evidence_gate_fixture.py'; S=importlib.util.spec_from_file_location('m66',PATH); R=importlib.util.module_from_spec(S); assert S.loader; S.loader.exec_module(R)
pytestmark=pytest.mark.fast_contract
def test_numeric_fixture_decision_is_replayable_and_non_authoritative():
 req,bundle,p=R.numeric_inputs();g=R.gate();a=g.evaluate(request=req,bundle=bundle,parser_candidate=p.parser_candidate,fact=p.normalized_fact,trace=p.trace);b=g.evaluate(request=req,bundle=bundle,parser_candidate=p.parser_candidate,fact=p.normalized_fact,trace=p.trace);assert a.decision.decision=="fixture_accepted_for_gate_simulation" and a.decision.decision_digest==b.decision.decision_digest and a.decision.runtime_promotion_authorized is False
def test_hard_mismatch_relationship_commercial_trace_and_semantic_override_fail_closed():
 req,b,p=R.numeric_inputs();g=R.gate();s=SemanticClassificationSuggestion(suggestion='try',rationale_ref='fixture')
 assert 'unit_mismatch' in g.evaluate(request=req,bundle=b,parser_candidate=p.parser_candidate,fact=p.normalized_fact.model_copy(update={'unit':'percent'}),trace=p.trace,suggestion=s).decision.hard_failure_codes
 assert 'numeric_program_trace_required' in g.evaluate(request=req,bundle=b,parser_candidate=p.parser_candidate,fact=p.normalized_fact,trace=None).decision.hard_failure_codes
 table=b.candidates[-1]
 assert 'entity_mismatch' in g.evaluate(request=req,bundle=b.model_copy(update={'candidates':b.candidates[:-1]+(table.model_copy(update={'entity_ref':'OTHER'}),)}),parser_candidate=p.parser_candidate,fact=p.normalized_fact,trace=p.trace).decision.hard_failure_codes
 assert 'period_mismatch' in g.evaluate(request=req,bundle=b,parser_candidate=p.parser_candidate,fact=p.normalized_fact.model_copy(update={'period':'FY2025'}),trace=p.trace).decision.hard_failure_codes
 assert 'scale_mismatch' in g.evaluate(request=req,bundle=b,parser_candidate=p.parser_candidate,fact=p.normalized_fact.model_copy(update={'scale_multiplier':0}),trace=p.trace).decision.hard_failure_codes
 assert 'source_authority_below_minimum' in g.evaluate(request=req,bundle=b.model_copy(update={'candidates':b.candidates[:-1]+(table.model_copy(update={'source_authority_rank':1}),)}),parser_candidate=p.parser_candidate,fact=p.normalized_fact,trace=p.trace).decision.hard_failure_codes
 rr,rb=R.relationship_inputs();assert g.evaluate(request=rr,bundle=rb,parser_candidate=p.parser_candidate,fact=p.normalized_fact,trace=p.trace).decision.decision=='rejected'
 cr,cb=R.commercial_inputs();assert g.evaluate(request=cr,bundle=cb).decision.decision=='commercial_gap'
 with pytest.raises(EvidenceGateError,match='semantic_suggestion_must_not_claim_override_authority'):g.evaluate(request=req,bundle=b,parser_candidate=p.parser_candidate,fact=p.normalized_fact,trace=p.trace,suggestion=s.model_copy(update={'override_authority':True}))
def test_conflict_digest_mismatch_consumers_and_accepted_schema_fail_closed():
 req,b,p=R.numeric_inputs();g=R.gate();conf=b.candidates[-1].model_copy(update={'candidate_id':'other-table','document_id':'other'});d=g.evaluate(request=req,bundle=b.model_copy(update={'candidates':b.candidates+(conf,)}),parser_candidate=p.parser_candidate,fact=p.normalized_fact,trace=p.trace).decision;assert d.decision=='typed_gap'
 assert g.evaluate(request=req,bundle=b.model_copy(update={'request_digest':'wrong'}),parser_candidate=p.parser_candidate,fact=p.normalized_fact,trace=p.trace).decision.decision=='rejected'
 for consumer in ('writer','domain_judgment'):
  with pytest.raises(EvidenceGateError,match='not_consumable'):reject_formal_evidence_consumer(decision=d,consumer=consumer)
 with pytest.raises(ValidationError): EvidencePromotionDecision(decision_id='x',decision_digest='x',decision='accepted',evidence_request_id='r',evidence_request_digest='r',candidate_bundle_id='b',candidate_bundle_digest='b')
def test_m6_6_fixture_and_review_are_scoped(tmp_path):
 review=json.loads((ROOT/'configs/engineering_handoff/point01_m6_6_cross_owner_design_review_v1_0.json').read_text(encoding='utf-8'));assert review['user_confirmation']['decision']=='approve_m6_6_deterministic_evidence_gate_contract_only' and review['independent_human_or_multi_person_signoff'] is False
 o=tmp_path/'r.json';p=subprocess.run([sys.executable,str(PATH),'--output',str(o)],cwd=ROOT,text=True,capture_output=True);assert p.returncode==0,p.stderr;r=json.loads(o.read_text(encoding='utf-8'));assert r['status']=='pass' and r['authority_boundary']['formal_evidence_promotion'] is False
