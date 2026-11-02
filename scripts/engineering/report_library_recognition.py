"""Render a full-scope recognition audit without conflating flags with errors."""
import argparse
from collections import Counter,defaultdict
import html
import json
from pathlib import Path

from audit_source_binding_lineage import digest,read_json,read_lines

LABELS={
 'derived_integrity_failure':'已有转录或节点的完整性检查失败',
 'encoding_loss_requires_original':'存在替换字符，需从原件核对编码损失',
 'scoped_derived_content_not_full_original':'仅有转录或局部范围，不能声称覆盖完整原件',
 'current_original_not_yet_parsed':'当前原件存在，但本轮尚未完成解析',
 'new_original_parse_failure':'补跑失败，需按执行日志处理',
 'engineering_audit_failure':'结构或完整性检查失败',
 'current_source_changed_or_unavailable':'当前原件变化或不可读，需要重定基线',
 'parser_source_identity_mismatch':'解析产物与当前原件身份不匹配',
 'structure_evidence_review':'层级、旧章节或原文位置仍需证据核对',
 'unresolved_native_title':'原生标题尚未唯一绑定到正文',
 'section_without_native_blocks_or_source_heading':'原生分区尚未建立正文或标题对应',
 'shared_original_range':'多个分区共用原范围，需区分交叉引用和边界问题',
 'heading_proof_unresolved':'完整标题的原件定位或角色证据不足',
 'source_scope_boundary_deferred':'新旧范围冲突，暂保留原归属',
 'conflicting_heading_parent_evidence':'标题父级存在相互冲突的证据',
 'unverified_heading_part':'尚未验证标题所属 Part',
 'explicit_heading_coverage_review':'显式 HTML 标题未匹配，需核对是否真实章节',
 'logical_table_header_footnote_quality_not_accepted':'物理表格已保留，逻辑表头与脚注关系尚未验收',
 'no_native_sections_format_route':'此格式没有原生分区，应沿节点结构适配',
 'web_purpose_and_original_coverage_not_accepted':'网页用途、正文覆盖与标题需原件对照',
 'markdown_rendered_html_table_quality_not_accepted':'Markdown 嵌入 HTML、表格及渲染结构待核验',
 'pdf_layout_quality_not_independently_accepted':'PDF 版面、读序、复杂表格或图像文字待质量验收',
 'record_consumer_semantics_not_accepted':'结构化记录已保留，字段消费或 SQL 回读未验收',
 'unrecognized_record_schema':'结构化载荷缺少已识别的记录合同',
 'zero_chapters_requires_source_review':'无章节结果待原件核对；不直接视作漏标题',
}


def run(root):
    root=Path(root);summary=read_json(root/'summary.json');rows=read_lines(root/'library-bindings.jsonl')
    issues=read_lines(root/'issues.jsonl');by_id=defaultdict(list)
    for item in issues:by_id[item['document_id']].append(item)
    assert len(rows)==len({r['document_id'] for r in rows})==summary['total_bindings']
    assert set(by_id)<={r['document_id'] for r in rows}
    groups=[]
    for kind,count in summary['issue_counts'].items():
        group=dict(kind=kind,description=LABELS.get(kind,kind),records=count,
                   affected_bindings=summary['issue_binding_counts'][kind],
                   unique_artifact_records=summary['unique_artifact_issue_counts'].get(kind,0))
        groups.append(group)
    (root/'problem-groups.json').write_text(json.dumps(groups,ensure_ascii=False,indent=2),encoding='utf8')
    table=[]
    for row in rows:
        findings=by_id[row['document_id']]
        descriptions=[]
        for kind in dict.fromkeys(i['kind'] for i in findings):
            matched=[i for i in findings if i['kind']==kind]
            descriptions.append(LABELS.get(kind,kind)+f'（{len(matched)}条记录）')
        source=row.get('current_source') or {}
        values=[row.get('title',''),row['document_id'],row['recognition_audit']['state'],
                source.get('path') or source.get('url') or row.get('url',''),
                '\n'.join(descriptions) or '本轮检查未发现提示；不等于人工质量通过']
        table.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in values)+'</tr>')
    page='<!doctype html><meta charset="utf-8"><title>全库识别审计</title><style>body{font:14px system-ui;margin:24px;color:#243047}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{padding:10px;border:1px solid #d6dce5;overflow-wrap:anywhere;white-space:pre-line}th{background:#eef3f9}input{padding:10px;width:65%}</style>'
    page+=f'<h1>全库识别审计：{len(rows)} 条统一资料</h1><p>原 409 条已经合入同一清单。提示包括已证实缺陷、未决结构和质量验证缺口，不能相加当作错误数。各路线保留自己的版本；quality_pass=false。</p>'
    page+='<input id="q" placeholder="搜索公司、资料、稳定 ID 或问题"><span id="n"></span><table><thead><tr><th>资料</th><th>身份</th><th>检查状态</th><th>来源</th><th>剩余事项</th></tr></thead><tbody>'+''.join(table)+'</tbody></table><script>q.oninput=()=>{let c=0;document.querySelectorAll("tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(q.value.toLowerCase());if(!r.hidden)c++});n.textContent=" 显示 "+c};q.oninput();</script>'
    (root/'current-library.html').write_text(page,encoding='utf8')
    for name,items in [('active-library.jsonl',[r for r in rows if r.get('active',True)]),
                       ('parse-plan.jsonl',[dict(document_id=r['document_id'],**r['recognition_audit']) for r in rows])]:
        (root/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in items),encoding='utf8')
    lines=['# 全库文档识别复核',f'统一范围：{len(rows)} 个稳定绑定。',
        '本页区分工程检查、结构疑点和原件质量验收；没有把零报错当作准确率。',
        '## 剩余问题（同一资料可落入多类）',
        '| 类别 | 涉及绑定 | 提示记录 |','|---|---:|---:|']
    for g in groups:lines.append(f"| {g['description']} | {g['affected_bindings']} | {g['records']} |")
    lines+=['','## 处理边界','通用修复优先处理身份、容器映射、标题角色、章节归属和预分块消费；格式专属处理用于 SEC 无分区附件、PDF 版面和结构化记录合同。',
            '原件不可得、原位置有多个同等候选及原文损坏继续保留明确范围。单份补丁须附原件摘要和局部坐标，本轮不建立公司或题目黑名单。']
    (root/'review.zh-CN.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    integrity=dict(scope_pass=True,total_bindings=len(rows),engineering_pass=summary['engineering_pass'],quality_pass=False,
                   files={p.name:digest(p.read_bytes()) for p in root.iterdir() if p.is_file() and p.name!='integrity-final.json'})
    (root/'integrity-final.json').write_text(json.dumps(integrity,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);run(p.parse_args().root)
