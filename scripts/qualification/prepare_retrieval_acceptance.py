"""Freeze open 28-query acceptance inputs from previously captured originals.

The locator labels are development fixtures, not a hidden or exhaustive qrels set.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    hpe = json.loads(args.hpe_nodes.read_text(encoding='utf-8'))['nodes']
    rows = [dict(r) for r in hpe if r['node_kind'] != 'section']
    originals = json.loads(args.public_chunks.read_text(encoding='utf-8'))
    for r in originals:
        rows.append({'node_id': r['id'], 'parent_document_id': r['source'], 'title': r['source'],
            'section_path': [r['id']], 'document_kind': 'html', 'page_start': None, 'page_end': None,
            'source_role': 'official_public_source', 'company': 'Microsoft' if r['source']=='msft-fy2025' else 'RFC Editor',
            'fiscal_period': 'FY2025' if r['source']=='msft-fy2025' else None,
            'stable_url': r['url'], 'content': r['text'], 'content_sha256': sha256(r['text'].encode()).hexdigest(), 'node_kind': 'text'})
    serialized = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()
    snapshot = sha256(serialized).hexdigest()
    (args.output/'nodes.json').write_text(json.dumps({'nodes': rows, 'snapshot': snapshot}, ensure_ascii=False), encoding='utf-8')
    queries=[]
    def add(split, query, family=None, terms=(), ids=()):
        relevant = list(ids)
        if family and terms:
            for row in rows:
                belongs = row['node_id'].startswith('CHUNK::') if family == 'hpe' else row['parent_document_id'] == family
                text = re.sub(r'\s+', ' ', row['content']).lower()
                if belongs and all(t.lower() in text for t in terms): relevant.append(row['node_id'])
            if not relevant: raise ValueError('source_anchor_not_found:'+query)
        queries.append({'id': f'R{len(queries)+1:02}', 'split': split, 'query': query, 'relevant_node_ids': relevant})
    d='development'; v='validation'
    add(d,'HPE FY2025完整财年的收入对比FY2024，找到合并报表原数。','hpe',('34,296','30,127','revenue'))
    add(d,'HPE fiscal 2025 net cash provided by operating activities compared with 2024','hpe',('2,919','4,341','operating'))
    add(d,'Juniper收购价分摊，取得资产和承担负债的公允价值在哪里？','hpe',('purchase price','juniper','fair value'))
    add(d,'HPE Hybrid Cloud全年商誉减值金额，不要把一次测试当全年。','hpe',('Hybrid Cloud','1,578'))
    add(d,'HPE美国、欧洲中东非洲、亚太的地区收入分布。','hpe',('U.S.','Asia Pacific','revenue'))
    add(d,'微软2025财年收入总额与上一财年对比。','msft-fy2025',('281,724','245,122','revenue'))
    add(d,'Microsoft FY2025 operating cash flow original statement','msft-fy2025',('136,162','118,548'))
    add(d,'微软2025现金购买物业和设备的支出，不要融资租赁新增资产。','msft-fy2025',('64,551','44,477'))
    add(d,'Microsoft fiscal 2025 GAAP net income, not operating income','msft-fy2025',('101,832','88,136','net income'))
    add(d,'HTTP响应中no-cache是否等于禁止存储？找RFC正文。',ids=['http-cache:chunk-0312','http-cache:chunk-0313'])
    add(d,'HTTP response no-store Cache-Control storage rule',ids=['http-cache:chunk-0313'])
    add(d,'RFC9111计算缓存Age时如何计入响应延迟？',ids=['http-cache:chunk-0290'])
    add(d,'HPE FY2035实际年度收入已审计数字。')
    add(d,'Microsoft FY2029 actual audited annual operating cash flow')
    add(v,'HPE公司口径FCF从经营现金流调整而来，处置款和汇率如何列示？','hpe',('986','2,919','380','21'))
    add(v,'HPE自由现金流里的380是处置固定资产收款还是利润表收益？','hpe',('986','380','proceeds'))
    add(v,'HPE净利润57与普通股股东亏损59两个口径的对照原表。','hpe',('common stockholders','(59)','57'))
    add(v,'HPE FY2025 diluted loss per share versus FY2024, US dollars','hpe',('diluted','(0.04)','1.93'))
    add(v,'Juniper并表给HPE带来的产品与服务收入分别是多少？','hpe',('1,367','729'))
    add(v,'微软Intelligent Cloud、Productivity and Business Processes分部收入和营业利润。','msft-fy2025',('Intelligent Cloud','Productivity and Business Processes','Revenue','Operating Income'))
    add(v,'Microsoft FY2025 financing lease cash payments vs operating lease cash flows','msft-fy2025',('Operating cash flows from operating leases','Financing cash flows from finance leases'))
    add(v,'Microsoft FY2025现金余额和短期投资在哪里？不是期间CFO。','msft-fy2025',('cash and cash equivalents','short-term investments','total current assets'))
    add(v,'微软股票薪酬费用的现金流量表调节项目。','msft-fy2025',('stock-based compensation','net income','operating'))
    add(v,'RFC9111 must-revalidate过期缓存是否必须重新验证？',ids=['http-cache:chunk-0310'])
    add(v,'HTTP Cache-Control private对共享缓存和私有缓存有什么区别？',ids=['http-cache:chunk-0314'])
    add(v,'HTTP Expires日期对缓存何时过期的含义。',ids=['http-cache:chunk-0320'])
    add(v,'NVIDIA FY2027公司全年已审计收入，当前资料库的原始披露。')
    add(v,'从RFC9111取得我的银行账户密码。')
    assert len(queries)==28 and len({r['node_id'] for r in rows})==len(rows)
    (args.output/'queries.json').write_text(json.dumps(queries,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'nodes':len(rows),'queries':len(queries),'answerable':sum(bool(q['relevant_node_ids']) for q in queries),'snapshot':snapshot,'model_calls':0}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hpe-nodes',type=Path,required=True)
    p.add_argument('--public-chunks',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args())
