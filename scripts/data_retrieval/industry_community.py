"""Recent repository feedback and alternate official model-directory endpoint."""
import argparse,json
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import quote
from scripts.data_retrieval.build_industry_foundation import Collector,dumps


def collect(worker,c):
    e=c['entity_id']
    if c.get('github_org'):
        try:
            raw,_=worker.get(f"https://api.github.com/orgs/{c['github_org']}/repos?sort=updated&per_page=100")
            recent=[r for r in json.loads(raw) if worker.since<=r.get('pushed_at','')[:10]<=worker.as_of and not r.get('archived')]
            recent.sort(key=lambda r:r.get('stargazers_count',0),reverse=True)
            records=[]
            for repo in recent[:1]:
                url=f"https://api.github.com/repos/{repo['full_name']}/issues?state=all&sort=updated&direction=desc&since={worker.since}T00:00:00Z&per_page=30"
                raw,_=worker.get(url)
                for item in json.loads(raw):
                    if 'pull_request' in item or not worker.since<=item.get('updated_at','')[:10]<=worker.as_of:continue
                    records.append({k:item.get(k) for k in ['number','title','body','state','created_at','updated_at','closed_at','html_url','comments','author_association']})
                if records:
                    worker.source(e,url,c['name']+' · 近期仓库用户反馈','community_feedback',dumps(records),metadata={'repository':repo['full_name'],'updated_window':[worker.since,worker.as_of],'authoritative_company_position':False,'sampling':'30 most recently updated issues in highest-star recently active configured-org repository; not a representative user survey','comments_body_not_collected':True})
            worker.gap(e,'recent_repository_feedback','available' if records else 'empty_window',{'issues':len(records),'feedback_is_not_verified_fact':True,'representative_sentiment':False})
        except Exception as exc:worker.gap(e,'recent_repository_feedback','tool_failure',{'error':type(exc).__name__,'public_information_gap':False})
    if c.get('hf_org'):
        url=f"https://www.huggingface.co/api/models?author={quote(c['hf_org'])}&sort=lastModified&direction=-1&limit=30&full=true"
        try:
            raw,_=worker.get(url);models=[m for m in json.loads(raw) if worker.since<=m.get('lastModified','')[:10]<=worker.as_of]
            sid=worker.source(e,url,c['name']+' · Hugging Face近期模型','model_catalogue',dumps(models),metadata={'downloads_are_not_market_share':True,'endpoint_fallback':'official www host; TLS verification remains enabled'})
            saved=0
            for m in models[:2]:
                try:
                    u='https://www.huggingface.co/'+m['id']+'/raw/main/README.md';body,_=worker.get(u)
                    worker.source(e,u,m['id']+' model card','model_card',body.decode('utf-8',errors='replace'),metadata={'model_updated_at':m['lastModified'],'model_card_publication_unknown':True,'model_claim_not_independent_benchmark':True});saved+=1
                except Exception as exc:worker.gap(e,'hf_card:'+m['id'],'tool_failure',{'error':type(exc).__name__})
            worker.gap(e,'recent_hf_models','available' if models and saved else 'partial' if models else 'empty_window',{'models':len(models),'cards_read':saved,'source_id':sid})
        except Exception as exc:worker.gap(e,'recent_hf_models','tool_failure',{'error':type(exc).__name__,'url':url,'TLS_verification_not_disabled':True})
    print(dumps({'company':c['slug'],'community_extension':'done'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);a=p.parse_args()
    plan=json.loads(a.db.with_suffix('.plan.json').read_text(encoding='utf-8'));w=Collector(a.db,plan)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(collect,w,c) for c in plan['companies'] if c.get('github_org') or c.get('hf_org')]
        for f in as_completed(futures):f.result()
