from __future__ import annotations
import importlib.util, json
from pathlib import Path
import subprocess,sys
import pytest
from sec_agent.canonical_runtime.parser_numeric import ParserNumericError
ROOT=Path(__file__).resolve().parents[2]; PATH=ROOT/'scripts/engineering/run_point01_m6_5_parser_numeric_fixture.py'; S=importlib.util.spec_from_file_location('m65',PATH); R=importlib.util.module_from_spec(S); assert S.loader; S.loader.exec_module(R)
pytestmark=pytest.mark.fast_contract
def test_exact_unpromoted_trace_is_replayable():
 b,o=R.inputs(); a=R.compiler().compile(bundle=b,observation=o,metric_definition_ref='metric:segment_revenue:v1'); c=R.compiler().compile(bundle=b,observation=o,metric_definition_ref='metric:segment_revenue:v1'); assert a.trace.trace_digest==c.trace.trace_digest and a.normalized_fact.normalized_value=='1234.50' and a.normalized_fact.promotion_status=='unpromoted'
def test_unit_scale_period_coordinate_negatives_fail_closed():
 b,o=R.inputs(); c=R.compiler()
 for change,error in [({'unit':'EUR'},'numeric_unit_not_allowed'),({'scale_multiplier':1000},'numeric_scale_not_allowed'),({'period':'FY2025'},'numeric_period_does_not_match_candidate'),({'source_coordinate':'Other:r1'},'numeric_coordinate_does_not_match_table_context')]:
  with pytest.raises(ParserNumericError,match=error): c.compile(bundle=b,observation=o.model_copy(update=change),metric_definition_ref='metric:v1')
def test_m6_5_fixture_runner_is_execution_free(tmp_path):
 o=tmp_path/'r.json';p=subprocess.run([sys.executable,str(PATH),'--output',str(o)],cwd=ROOT,text=True,capture_output=True);assert p.returncode==0,p.stderr;r=json.loads(o.read_text(encoding='utf-8'));assert r['status']=='pass' and r['authority_boundary']['live_parser_or_ocr'] is False
