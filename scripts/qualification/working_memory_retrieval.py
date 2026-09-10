"""Bounded public/synthetic working-paper retrieval and cache qualification."""
import argparse
import json
import os
from pathlib import Path
import time
from sec_agent.agent_runtime.working_memory import WorkingMemory
from sec_agent.agent_runtime.working_memory_search import WorkingPaperSearch


def run(output,live):
    output.mkdir(parents=True,exist_ok=False)
    basis={'node_purpose':'Qwen working-paper paraphrase retrieval and warm cache',
        'input_scale':'Four synthetic short working papers, one paraphrase query, repeated once',
        'required_outputs':['Locate cash-conversion note despite different wording','Return current versions','Warm request makes zero provider calls'],
        'schema_burden':'Provider vectors and document rankings only',
        'materiality_quality_risk':'Synthetic memory retrieval, not finance acceptance or a blind benchmark',
        'comparable_run_evidence':'13 local working-memory/search tests; native Qwen adapter qualified previously',
        'reasoning_profile':'embedding/rerank only','maximum_calls':3,
        'stop_truncation_behavior':'One attempt, no retry; retain failed call usage as unknown'}
    (output/'TokenBudgetBasis.json').write_text(json.dumps(basis,ensure_ascii=False,indent=2),encoding='utf-8')
    if not live:return
    m=WorkingMemory(output/'notes.sqlite',owner='qualification',workspace='public-synthetic',actor='cash-analyst')
    rows=[('现金兑现观察','经营现金流未同步跟上账面盈利，待核实客户回款和营运资本变动，暂不作因果归因。'),
        ('订单执行','订单积压有所增加，但交付能力及客户取消情况仍待查证。'),
        ('竞争结构','比较产品功能及客户转换成本，没有形成市场份额结论。'),
        ('云基础设施','数据中心建设计划尚未核实，不据此判断供应商的利润率。')]
    for title,body in rows:m.save(title,body)
    query='之前谁讨论过赚到的利润还没有变成手里的钱？'
    literal=m.search(query)
    started=time.perf_counter();first=WorkingPaperSearch(m).search(query);elapsed=time.perf_counter()-started
    warm=WorkingPaperSearch(m).search(query)
    with m.connection() as db:calls=[dict(r) for r in db.execute('SELECT operation,status,input_characters,usage,request_id FROM working_retrieval_calls')]
    result={'first':first,'warm':warm,'literal_count':len(literal['items']),'elapsed_seconds':elapsed,
        'top_result_matches_intended_note':bool(first['items'] and first['items'][0]['title']=='现金兑现观察'),
        'calls':calls,'warm_cache_no_provider_call':warm['remote_calls']==0}
    (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'first','warm','calls'}},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--live',action='store_true');a=p.parse_args();run(a.output,a.live)
