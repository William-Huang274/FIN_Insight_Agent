"""Publish a local current-parser selection after verifying recovered receipts."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path

from audit_source_binding_lineage import digest, read_json, read_lines


def run(args):
    parent=Path(args.baseline);out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    rows=read_lines(parent/'library-bindings.jsonl')
    parsed=read_json(Path(args.parsed)/'summary.json')
    assert parsed['processed']==parsed['planned'] and not parsed['statuses'].get('failed')
    receipts={r['document_id']:r for r in parsed['rows']}
    assert len(receipts)==parsed['planned']
    removed={r['sha256'] for r in read_lines(parent/'excluded-bodies.jsonl')}
    incorporated=[]
    for row in rows:
        if row['document_id'] in receipts:
            receipt=receipts[row['document_id']]
            assert receipt['source_sha256']==row['current_source']['current_sha256']
            for artifact in receipt['artifacts'].values():
                assert digest(Path(artifact['path']).read_bytes())==artifact['sha256']
            artifact=receipt['artifacts']['document']
            row['current_parser_artifact']=dict(**artifact,route=receipt['route'],receipt=receipt,quality_pass=False)
            row['processing'].update(stage='continue_structure_quality',state='engineering_checked_quality_pending',
                current_parser_artifact=row['current_parser_artifact'])
            row['responsible_stage']='continue_structure_quality'
            incorporated.append(row['document_id'])
        assert not row.get('current_source') or row['current_source'].get('current_sha256') not in removed
        assert all(c['current_sha256'] not in removed for c in row.get('candidates',[]))
    assert set(incorporated)==set(receipts)
    for name,values in [('library-bindings.jsonl',rows),('active-library.jsonl',[r for r in rows if r['active']]),
                        ('parse-plan.jsonl',[r['processing'] for r in rows if r['active']])]:
        (out/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in values),encoding='utf8')
    by_id={r['document_id']:r for r in rows}
    issues=read_lines(args.issues)
    for issue in issues:
        if issue['kind']=='source_lineage_review':
            row=by_id[issue['document_id']]
            issue['previous_review']=dict(issue)
            issue.update(stage=row['processing']['stage'],current_source=row['current_source'],
                         historical_review_blocks_processing=False,selection_id=out.parent.name+'/'+out.name)
    (out/'library-issues.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in issues),encoding='utf8')
    for name in ['excluded-bodies.jsonl','version-changes.jsonl','unavailable-locators.jsonl']:
        (out/name).write_bytes((parent/name).read_bytes())
    summary=read_json(parent/'summary.json')
    summary.update(selection_id=out.parent.name+'/'+out.name,parent_baseline=str(parent),
        incorporated_recovered_parses=len(incorporated),current_stages=dict(Counter(r['processing']['stage'] for r in rows)),
        parsed_receipts_sha256=digest((Path(args.parsed)/'summary.json').read_bytes()),
        implementation_sha256=digest(Path(__file__).read_bytes()),quality_pass=False)
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    labels={'continue_structure_quality':'已有解析结果，继续质量检查','derived_content_processing':'按已有衍生内容继续处理',
            'parse_current_original':'来源已补齐，进行当前原件解析','excluded_invalid_body':'无效正文已剔除'}
    table=[]
    for row in rows:
        current=row.get('current_source') or row.get('parent_original') or {}
        values=[row['title'],row['document_id'],labels.get(row['processing']['stage'],row['processing']['stage']),
                current.get('current_sha256','仅有已保存衍生内容'),current.get('path') or current.get('url') or row['url']]
        table.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in values)+'</tr>')
    page='<!doctype html><meta charset="utf-8"><title>当前全库识别基线</title><style>body{font:14px system-ui;margin:24px;color:#273246}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{border:1px solid #d6dce5;padding:9px;overflow-wrap:anywhere}th{background:#eff3f9;position:sticky;top:0}input{padding:10px;width:60%}</style>'
    page+=f'<h1>当前全库识别基线</h1><p>{len(rows)}条统一管理；已剔除{summary["unique_invalid_bodies"]}份无效正文及其{summary["invalid_candidate_bindings"]}条候选关联。来源版本核对与解析质量分别记录；质量仍需继续验收。</p>'
    page+='<input id="q" placeholder="搜索标题、ID、阶段、文件路径"><span id="n"></span><table><thead><tr><th>资料</th><th>稳定身份</th><th>当前处理阶段</th><th>当前内容摘要</th><th>来源位置</th></tr></thead><tbody>'+''.join(table)+'</tbody></table><script>q.oninput=()=>{let c=0;document.querySelectorAll("tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(q.value.toLowerCase());if(!r.hidden)c++});n.textContent=" 显示 "+c};q.oninput();</script>'
    (out/'current-library.html').write_text(page,encoding='utf8')
    integrity=dict(pass_=True,total=len(rows),unique_ids=len({r['document_id'] for r in rows}),
        invalid_current_sources=0,incorporated_parses=len(incorporated),quality_pass=False,
        files={p.name:digest(p.read_bytes()) for p in out.iterdir() if p.is_file()})
    assert integrity['total']==integrity['unique_ids']==summary['total_bindings']
    (out/'integrity-final.json').write_text(json.dumps(integrity,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k in ('selection_id','current_stages','incorporated_recovered_parses','total_bindings')},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','parsed','issues','output'):p.add_argument('--'+name,required=True)
    run(p.parse_args())
