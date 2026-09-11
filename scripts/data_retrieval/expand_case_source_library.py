"""Bounded SEC capture + existing structured parser/node projection; no model calls.

Inputs are operator-selected source-bound mart policy and frozen base nodes.
Writes a new attempt directory, never changes the historical corpus in place.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import urljoin, urlsplit

import requests
from dotenv import load_dotenv
from ingestion.structured_document_adapter import StructuredSourceDescriptor, build_structured_document_tree
from financial_facts.sec_snapshot import sec_user_agent_from_environment
from scripts.qualification.run_dell_structured_rag_slice_qualification import build_retrieval_nodes


def selected_filings(binding, cutoff):
    recent = json.loads(Path(binding['submissions_ref']).read_text(encoding='utf-8'))['filings']['recent']
    result = []
    for form, limit in [('10-K', 3), ('10-Q', 1), ('8-K', 2)]:
        indices = [i for i, f in enumerate(recent['form']) if f == form
                   and recent['filingDate'][i] <= cutoff
                   and (form != '8-K' or '2.02' in recent.get('items', [''] * len(recent['form']))[i])]
        for i in sorted(indices, key=lambda i: recent['filingDate'][i], reverse=True)[:limit]:
            accession = recent['accessionNumber'][i]
            result.append({'ticker': binding['ticker'], 'company': binding['legal_name'],
                'issuer_id': binding['cik'], 'form': form, 'accession': accession,
                'publication_date': recent['filingDate'][i], 'period_end': recent['reportDate'][i],
                'url': f"https://www.sec.gov/Archives/edgar/data/{int(binding['cik'])}/{accession.replace('-', '')}/{recent['primaryDocument'][i]}"})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--base-nodes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--as-of', default='2026-09-02')
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--reuse', type=Path)
    args = parser.parse_args()
    if args.capture:
        import sec2md  # qualify the parser before any network capture
    args.output.mkdir(parents=True, exist_ok=False)
    policy = json.loads(args.policy.read_text(encoding='utf-8'))
    selected = [r for b in policy['source_bindings'] for r in selected_filings(b, args.as_of)]
    (args.output/'plan.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding='utf-8')
    if not args.capture:
        print(json.dumps({'planned': len(selected), 'path': str(args.output/'plan.json')})); return
    load_dotenv(override=False)
    client = requests.Session()
    client.headers['User-Agent'] = sec_user_agent_from_environment(os.environ)
    corpus = {k: [] for k in ('documents','sections','blocks','chunks')}
    receipts = []
    queue = list(selected)
    for item in queue:
        digest = hashlib.sha256(item['url'].encode()).hexdigest()
        receipt = {**item, 'status': 'pending'}
        try:
            cached = args.reuse / (digest+'.html') if args.reuse else None
            if cached and cached.is_file():
                body = cached.read_bytes()
                receipt['cache_reused'] = True
            else:
                time.sleep(.55)
                response = client.get(item['url'], timeout=35, allow_redirects=False)
                response.raise_for_status()
                body = response.content
                if len(body) > 20 * 1024 * 1024 or 'html' not in response.headers.get('Content-Type','').lower():
                    raise ValueError('unexpected_filing_body')
            (args.output/(digest+'.html')).write_bytes(body)
            body_digest = hashlib.sha256(body).hexdigest()
            source = StructuredSourceDescriptor.from_mapping({**item, 'route_id': 'PUBLIC:'+digest[:24],
                'title': f"{item['ticker']} {item['form']} · {item['period_end']}", 'publisher': 'SEC EDGAR',
                'fiscal_period': item['period_end'], 'source_role': item['form'], 'document_kind': 'html',
                'stable_url': item['url'], 'branches': ['public_company_research']}, raw_body_sha256=body_digest)
            profile = {'10-K':'sec2md_10k','10-Q':'sec2md_10q'}.get(item['form'], 'sec2md_exhibit')
            tree = build_structured_document_tree(source=source, body=body, parser_profile=profile)
            corpus['documents'].append(tree['document'])
            for key in ('sections','blocks','chunks'): corpus[key].extend(tree[key])
            receipt.update(status='parsed', raw_body_sha256=body_digest, document_id=tree['document']['document_id'],
                sections=len(tree['sections']), chunks=len(tree['chunks']))
            if item['form'] == '8-K':
                from bs4 import BeautifulSoup
                links = [urljoin(item['url'], a['href']) for a in BeautifulSoup(body, 'lxml').select('a[href]')
                         if any(s in (a.get_text(' ', strip=True)+' '+a['href']).lower() for s in ('99.1','ex991','ex99-1','ex99_1','exhibit99','press release','financial results'))]
                for url in list(dict.fromkeys(links))[:1]:
                    if urlsplit(url).hostname == 'www.sec.gov' and url.rsplit('/',1)[0] == item['url'].rsplit('/',1)[0]:
                        queue.append({**item,'url':url,'form':'earnings_release'})
        except Exception as exc:
            receipt.update(status='capture_or_parse_failed', failure=f'{type(exc).__name__}: {str(exc)[:160]}', public_information_gap=False)
        receipts.append(receipt)
        (args.output/'receipts.json').write_text(json.dumps(receipts, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k:receipt.get(k) for k in ('ticker','form','period_end','status','failure')},ensure_ascii=False),flush=True)
    base = [json.loads(line) for line in args.base_nodes.read_text(encoding='utf-8').splitlines() if line.strip()]
    if corpus['documents']:
        projected = build_retrieval_nodes(corpus)
        base.extend([*projected['parents'], *projected['leaves']])
    nodes = {r['node_id']:r for r in base}
    (args.output/'retrieval_nodes.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in nodes.values()), encoding='utf-8')
    (args.output/'documents.json').write_text(json.dumps(corpus['documents'],ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__': main()
