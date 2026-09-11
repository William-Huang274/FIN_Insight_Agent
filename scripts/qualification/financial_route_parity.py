"""Zero-model equality of conversation SQL and research MCP over one host snapshot."""
import argparse
import asyncio
from datetime import date
import json
import os
from pathlib import Path
from types import SimpleNamespace

from mcp import Client
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.agent_runtime.dell_agent_server_data_composition import open_dell_approved_data_composition


def facts(value):
    found = set()
    def visit(x):
        if isinstance(x, dict):
            if x.get('numeric_fact_id') and 'value_decimal' in x:
                found.add(tuple(str(x.get(k)) for k in ['metric_id','period_start','period_end','value_decimal','unit']))
            for v in x.values(): visit(v)
        elif isinstance(x, list):
            for v in x: visit(v)
    visit(value)
    return sorted(found)


async def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    settings=json.loads((args.settings/'host-settings.json').read_text(encoding='utf-8'))
    mart=(args.fact_mart or Path(settings['conversation_fact_mart'])).resolve(strict=True)
    env={**json.loads(args.data_environment.read_text(encoding='utf-8')),'FIN_REPO_ROOT':str(Path.cwd()),'FINSIGHT_RESEARCH_FACT_MART_PATH':str(mart)}
    query=next(g.tool for g in conversation_tools(thread_id='route-parity',fact_mart=mart) if g.tool.name=='query_financial_data')
    receipts=[]
    with open_dell_approved_data_composition(run_invocation_id='qualification:208:financial-route-parity',environment=env) as data:
        async with Client(data.mcp_server,raise_exceptions=False) as client:
            bound=await client.call_tool('get_dell_research_method',{'branch_ids':['Q1_ISSUER_TRUTH'],'research_as_of':'2026-09-02T00:00:00Z','data_snapshot_id':data.foundation_binding.snapshot_id,'execution_attempt_id':'qualification:208:financial-route-parity'})
            if bound.is_error:raise RuntimeError('scope_binding_failed')
            for ticker in ['MSFT','HPE','DELL','NVDA','MU']:
                for year in [2024,2025]:
                    metrics=['operating_cash_flow','capital_expenditures','free_cash_flow']
                    _,ordinary=query.func(ticker=ticker,fiscal_years=[year],metric_ids=metrics,research_as_of=date(2026,9,2),granularity='fiscal_year',runtime=SimpleNamespace(tool_call_id=f'{ticker}:{year}'))
                    result=await client.call_tool('query_company_financial_facts',{'branch_id':'Q1_ISSUER_TRUTH','run_scope':bound.structured_content['run_scope'],'ticker':ticker,'metric_ids':metrics,'fiscal_years':[year],'research_as_of':'2026-09-02','granularity':'fiscal_year','selection_mode':'latest_on_or_before'})
                    if result.is_error:raise RuntimeError('research_query_failed')
                    a,b=facts(ordinary),facts(result.structured_content)
                    receipts.append({'ticker':ticker,'year':year,'conversation':a,'research':b,'equal':a==b,'nonempty':bool(a)})
                    (args.output/'result.json').write_text(json.dumps({'receipts':receipts,'model_calls':0,'runtime_mart_sha256':data.dependencies.planner_tool_capabilities['mart_sha256'],'historical_inventory_digest':data.inventory_snapshot_digest},indent=2),encoding='utf-8')
                    assert a==b, f'route_mismatch:{ticker}:{year}'
                    if ticker in {'MSFT','HPE'}:assert a, f'expected_registered_data_missing:{ticker}:{year}'
    print(json.dumps({'queries':len(receipts),'equal':all(r['equal'] for r in receipts),'nonempty':sum(r['nonempty'] for r in receipts),'model_calls':0}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--settings',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--data-environment',type=Path,required=True);p.add_argument('--fact-mart',type=Path)
    asyncio.run(main(p.parse_args()))
