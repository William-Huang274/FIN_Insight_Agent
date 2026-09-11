"""Zero-model checks of actual public snapshot, product API and Agent reader."""
import argparse
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil

from fastapi import FastAPI
from fastapi.testclient import TestClient
from apps.workbench.backend.api.v1.data_library import build_data_library_router
from sec_agent.research_foundation.data_ports import StructuredLocalKnowledgeReader
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest, navigate_source_nodes


def main():
    p=argparse.ArgumentParser();p.add_argument('--nodes',type=Path,required=True);p.add_argument('--mart',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--hybrid-cache');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    root=a.output/'attachments';(root/'public-library').mkdir(parents=True)
    shutil.copyfile(a.nodes,root/'public-library/retrieval_nodes.jsonl')
    data=a.nodes.read_bytes();rows=[json.loads(x) for x in data.decode().splitlines() if x.strip()];digest=sha256(data).hexdigest()
    reader=StructuredLocalKnowledgeReader(nodes_path=a.nodes,expected_sha256=digest,expected_node_count=len(rows),research_as_of=date(2026,9,2),allowed_branch_ids=['Q1'])
    app=FastAPI();app.include_router(build_data_library_router(root,a.mart),prefix='/api/v1')
    client=TestClient(app); receipts=[]
    os.environ['FINSIGHT_SOURCE_HYBRID']='0'  # paid vector preparation is separately accounted
    responses={}
    for ticker in ['DELL','HPE','MSFT','MU','NVDA']:
        url=f'/api/v1/data-library/sources?ticker={ticker}&kind=10-K&limit=100'
        result=client.get(url);assert result.status_code==200,result.text
        docs=result.json()['items'];assert len(docs)>=3,(ticker,len(docs))
        if ticker=='MSFT':assert any(d['period_end']=='2024-06-30' for d in docs)
        for doc in docs:
            found=navigate_source_nodes(list(reader._node_index.values()),SourceDocumentRequest(operation='search',document_id=doc['document_id'],query='operating cash flows',limit=5),snapshot=digest)
            assert found.items,(ticker,doc['title'])
            hit=found.items[0]
            full=navigate_source_nodes(list(reader._node_index.values()),SourceDocumentRequest(operation='read',document_id=doc['document_id'],node_id=hit['node_id']),snapshot=digest)
            assert full.items and full.items[0]['writer_citable'] and not full.items[0]['truncated']
        financial=client.get('/api/v1/data-library/financials',params={'ticker':ticker,'fiscal_year':2025,'metric':'operating_cash_flow','period':'FY'});assert financial.status_code==200,financial.text
        assert financial.json()['total']>0,ticker
        receipts.append({'ticker':ticker,'annual_documents':len(docs),'annual_passages_read':len(docs),'financial_rows':financial.json()['total']})
    # Frozen real API responses for browser presentation checks, not a live deployment claim.
    for path in ['/api/v1/data-library/sources','/api/v1/data-library/sources?ticker=MSFT&year=2024','/api/v1/data-library/financials','/api/v1/data-library/financials?ticker=MSFT&fiscal_year=2025&query=现金流']:
        response=client.get(path);assert response.status_code==200,response.text
        responses[path]=response.json()
    doc=responses['/api/v1/data-library/sources?ticker=MSFT&year=2024']['items'][0]
    path='/api/v1/data-library/sources/'+doc['document_id'];responses[path]=client.get(path).json()
    (a.output/'browser-responses.json').write_text(json.dumps(responses,ensure_ascii=False),encoding='utf-8')
    hybrid=[]
    if a.hybrid_cache:
        from retrieval.source_hybrid import prepare_source_index, rank_sources
        from retrieval.qwen_api import QwenRetrieval
        from scripts.deployment.dell_report_workbench import configured_key
        api=QwenRetrieval(configured_key('QWEN_API_KEY'))
        try:
            repeated=prepare_source_index(rows,digest,a.hybrid_cache,api)
            assert repeated['calls']==0,'Expected already prepared snapshot; do not re-embed'
            for ticker in ['DELL','HPE','MSFT','MU','NVDA']:
                doc=client.get('/api/v1/data-library/sources',params={'ticker':ticker,'kind':'10-K'}).json()['items'][0]
                scoped=[r for r in rows if r['parent_document_id']==doc['document_id'] and r['node_kind']!='section']
                query='经营活动现金流 operating cash flows'
                lexical=navigate_source_nodes(scoped,SourceDocumentRequest(operation='search',query=query,limit=20),snapshot=digest)
                lookup={r['node_id']:r for r in scoped}
                literal=[lookup[r['node_id']] for r in lexical.items]
                ranked,receipt=rank_sources(scoped,query,digest,literal,path=a.hybrid_cache,api=api)
                assert ranked and all(r['ticker']==ticker for r in ranked)
                _,replay=rank_sources(scoped,query,digest,literal,path=a.hybrid_cache,api=api)
                assert replay['calls']==0
                hybrid.append({'ticker':ticker,'document_id':doc['document_id'],'receipt':receipt,'repeat_calls':replay['calls'],
                    'top5':[{'node_id':r['node_id'],'section':r.get('section_path'),'preview':r['content'][:250]} for r in ranked[:5]]})
                (a.output/'hybrid.json').write_text(json.dumps(hybrid,ensure_ascii=False,indent=2),encoding='utf-8')
        finally:api.close()
    (a.output/'result.json').write_text(json.dumps({'companies':receipts,'source_nodes':len(rows),'snapshot':digest,'model_calls':0,'retrieval_api_calls':sum(r['receipt']['calls'] for r in hybrid),'deployment':False},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipts))


if __name__=='__main__':main()
