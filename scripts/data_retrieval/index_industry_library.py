"""Explicit paid document-router preparation; never invoked by normal reads."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from retrieval.library_hybrid import document_cards,prepare
from retrieval.qwen_api import QwenRetrieval
from sec_agent.research_foundation.research_library import ResearchLibrary
from scripts.deployment.research_workbench import configured_key


def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    library=ResearchLibrary(a.library);cards=document_cards(library);characters=sum(len(c['text']) for c in cards)
    basis={'purpose':'Index document navigation cards for current AI industry library; full original passages stay in SQL FTS5',
        'input_scale':{'documents':len(cards),'characters':characters},'required_output':'1024-dimensional text-embedding-v4 vectors',
        'quality_risk':'Coarse recall only; raw source reading and units/period checks remain required',
        'reasoning_profile':'non-generative embedding','limits':{'max_characters':10000000,'batch_size':10,'per_request_attempts':1},
        'stop_behavior':'Fail and retain unknown usage; do not automatically retry. Reuse exact-text cached vectors.',
        'pricing_basis':'Aliyun official Knowledge Studio billing: CNY0.0005 per 1000 tokens, verified 2026-09-20; estimate only, actual billing may differ',
        'library_sha256':library.manifest['sha256']}
    (a.output/'TokenBudgetBasis.json').write_text(json.dumps(basis,ensure_ascii=False,indent=2),encoding='utf-8')
    if not a.execute:print(json.dumps(basis));return
    if characters>basis['limits']['max_characters']:raise ValueError('index_scope_exceeds_budget_basis')
    class Audited(QwenRetrieval):
        def embed(self,texts,**kwargs):
            result=super().embed(texts,**kwargs)
            with (a.output/'usage.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'request_id':result.request_id,'model':result.model,'usage':result.usage})+'\n')
            return result
    api=Audited(configured_key('QWEN_API_KEY'))
    try:
        result=prepare(library,str(a.cache),api)
        (a.output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    finally:api.close()

if __name__=='__main__':main()
