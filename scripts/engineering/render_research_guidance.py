"""Render maintained research guidance for human review; never dispatch models.

Run from a checkout with PYTHONPATH=src. Output is a self-contained private/local
artifact, not a frozen run configuration or proof of model compliance.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import html
import json
from pathlib import Path
import subprocess

from markdown_it import MarkdownIt

from sec_agent.agent_runtime.conversation_agent import research_system_prompt
from sec_agent.agent_runtime.harness_delegate import delegation_guidance
from sec_agent.agent_runtime.source_toolkit import source_tool_guidance
from sec_agent.agent_runtime.synthesis_guidance import final_author_guidance
from sec_agent.agent_runtime.working_memory_tools import WORKING_MEMORY_GUIDANCE
from sec_agent.research_foundation.research_depth import depth_guidance
from sec_agent.research_foundation.research_methods import (
    BASIC_RESEARCH_GUIDANCE, METHOD_TOOL_GUIDANCE, get_research_method,
    research_writing_guidance,
)

ROOT = Path(__file__).resolve().parents[2]
MD = MarkdownIt('commonmark', {'html': False}).enable('table')
CHANGES = [
    ('停止取数与结束研究分别决定', 'research_foundation/research_depth.py',
     '旧规则允许关键数据私有或尚未发生时给出缺口后结束。新规则先判断未知影响哪一层，再检查是否还有有依据的范围或比较。保留合理停止，避免把缺一个数等同于整项关系已完成。'),
    ('始终对照原问题与实际回答', 'research_foundation/methods/agent_guidance.md',
     '保留允许领域判断与明确假设的原则，补上委派、验收之间的目标连续性。收窄后的结果可用，原题的重要剩余部分仍需有人负责。'),
    ('负责人负责重要关系的剩余部分', 'agent_runtime/synthesis_guidance.py',
     '在原有 finding/unresolved 和笔记中说明已回答什么、未知怎样影响判断。最终综合先检查新发现是否改变方向、排序、时点或范围，再组织正文。'),
    ('委派和验收入口同步', 'agent_runtime/harness_consultations.py',
     '工具说明保留原问题、条件、反证及来源绑定，增加对实际回答与交办问题的比较。参数、调用ID和权限保持兼容，没有新增表格或自动判定研究充分。'),
    ('复核从新发现的影响出发', 'agent_runtime/harness_delegate.py',
     '检查者先看新发现应改变什么，再看作者有没有作必要比较。意见应给出可执行的调查或分析；不会只要求删除强词或确认全文自洽。'),
    ('未决事项绑定相关判断', 'agent_runtime/research_actions.py',
     '未决项引用受影响的条件判断或相邻附注，详细原因留在 rationale。重要条件对读者可见，旧错误与未采用算法无需变成逐项免责声明。版本和引文检查不放松。'),
    ('负责人方法补齐收口教学', 'research_foundation/methods/lead.md',
     '区分反例检查和前瞻判断，允许缩小范围，同时保留会影响总判断的剩余关系。继续使用原有验收字段。'),
    ('未知参数仍可推进条件分析', 'research_foundation/methods/scenario_sensitivity.md',
     '区分方向、幅度、时点与精度，说明合同上下界、可比观察和工程关系怎样参与推断；保持不编造参数和概率的要求。'),
    ('区分阶段笔记与最终回答', 'research_foundation/methods/writer.md',
     '阶段笔记可提出下一项调查，最终回答应呈现已完成比较后的当前倾向。增加阶段认识到最终判断的教学衔接；自然中文金额仍须保持数值等价。'),
    ('复核方法检查问题是否被收窄', 'research_foundation/methods/verifier.md',
     '作者的解释自洽之外，检查原题的重要剩余部分及新发现的决策影响；保留充分依据支持的判断。'),
    ('按实际困难提供方法入口', 'research_foundation/research_methods.py',
     '反例后无结论、未知参数难分析、新发现未影响回答分别指向准确章节。全文仍按需读取，不要求每次调用方法。'),
]
NAMES = {
    'get_research_method', 'read_public_source', 'read_legislation',
    'read_regional_disclosures', 'search_korean_disclosures', 'read_market_prices',
    'read_market_expectations', 'query_hithink', 'query_public_data',
    'discover_source_tools', 'consult_research_agent', 'WriteWorkingNote',
    'ReadWorkingNote', 'SearchWorkingNotes', 'browse_context',
}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, encoding='utf-8')


def tool_docs():
    modules = ['harness_consultations.py', 'research_actions.py', 'harness_artifact_tools.py']
    wanted = {'consult_research_agent', 'assess_research_result', 'read_research_agent_result',
              'respond_research_action', 'save_research_report', 'edit_research_report',
              'deliver_current_report'}
    result = []
    for module in modules:
        path = ROOT/'src/sec_agent/agent_runtime'/module
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
                result.append((node.name, str(path.relative_to(ROOT)), ast.get_docstring(node) or ''))
    return result


def card(title, content, meta='', ident='', group='prompt', code=False):
    body = '<pre>'+html.escape(content)+'</pre>' if code else MD.render(content)
    return (f'<details class="entry" data-group="{group}" id="{ident}"><summary>'
            f'<strong>{html.escape(title)}</strong><span>{html.escape(meta)}</span></summary>'
            f'<div class="body">{body}</div></details>')


def render(compare_ref):
    catalog = get_research_method()['methods']
    components = [
        ('基本研究职责', '常驻 · conversation_agent → BASIC_RESEARCH_GUIDANCE', BASIC_RESEARCH_GUIDANCE),
        ('方法目录与按困难选择的入口', '工具开放时常驻 · METHOD_TOOL_GUIDANCE；不包含方法全文', METHOD_TOOL_GUIDANCE),
        ('主负责人及最终综合', '配置研究助手/原生接管时 · final_author_guidance', final_author_guidance({'research_delegate': {'model': 'deepseek-flash'}})),
        ('Flash 调查职责', 'purpose=investigate · delegation_guidance', delegation_guidance('investigate')),
        ('Flash 复核职责', 'purpose=review · delegation_guidance', delegation_guidance('review')),
        ('局部草稿职责', 'purpose=draft 且宿主准入时 · delegation_guidance', delegation_guidance('draft')),
        ('工作笔记', '工具开放时常驻 · WORKING_MEMORY_GUIDANCE', WORKING_MEMORY_GUIDANCE),
        ('资料工具导航', '随工具授权生成 · source_tool_guidance；未修改', source_tool_guidance(NAMES)),
        ('专题底稿写作摘要', '调用 research_writing_guidance(workpaper) 的路径；原生主会话不默认加载', research_writing_guidance('workpaper')),
        ('综合报告写作摘要', '调用 research_writing_guidance(report) 的路径；原生主会话不默认加载', research_writing_guidance('report')),
    ]
    for level in ('brief', 'standard', 'deep'):
        components.append((f'研究深度 · {level}', '按任务选择一个档位 · depth_guidance', depth_guidance(level)))
    prompts = ''.join(card(t, s, meta, f'prompt-{i}', code=True) for i, (t,meta,s) in enumerate(components))
    tools = ''.join(card(t,s,meta,group='tool',code=True) for t,meta,s in tool_docs())
    methods=''; rows=''; manifest=[]
    changed={'lead','writer','verifier','scenario_sensitivity'}
    for c in catalog:
        r=get_research_method(c['method_id']); mid=r['method_id']
        label='本轮修改' if mid in changed else ('兼容别名' if mid=='financial_quality' else '保留')
        rows += f'<tr><td><a href="#method-{mid}" class="jump">{html.escape(mid)}</a></td><td>{html.escape(r["title"])}</td><td>v{r["content_version"]}</td><td>{label}</td></tr>'
        methods += card(f'{mid} · {r["title"]}',r['content'],f'v{r["content_version"]} · {label} · 按需读取',f'method-{mid}','method')
        manifest.append({k:r[k] for k in ('method_id','content_version','resource_digest','sections')})
    change_html=''
    for title,rel,why in CHANGES:
        path='src/sec_agent/'+rel
        old=git('show',f'{compare_ref}:{path}');new=(ROOT/path).read_text(encoding='utf-8')
        diff='\n'.join(difflib.unified_diff(old.splitlines(),new.splitlines(),fromfile=compare_ref[:10]+'/'+path,tofile='审改后/'+path,lineterm=''))
        change_html+=f'<article class="change"><h3>{html.escape(title)}</h3><p>{html.escape(why)}</p>'+card('查看准确修改对照',diff,path,group='change',code=True)+'</article>'
    assembled=research_system_prompt(NAMES,depth_guidance('deep'))+final_author_guidance({'research_delegate': {'model': 'deepseek-flash'}})
    preview=card('源码拼装示例：Sol 主负责人 / deep',assembled,
        '非真实请求 · 不含任务题面、冻结覆盖、来源快照、工具schema和压缩记录','assembled',code=True)
    head=git('rev-parse','HEAD').strip()
    data={'base_ref':compare_ref,'checkout_head':head,'status':'source_revision_not_deployed_or_paid_validated',
          'methods':manifest,'prompt_components':[{'title':t,'injection':m,'characters':len(s),'sha256':hashlib.sha256(s.encode()).hexdigest()} for t,m,s in components]}
    document=PAGE.replace('@@HEAD@@',html.escape(head[:12])).replace('@@BASE@@',html.escape(compare_ref[:12]))
    for key,value in [('CHANGES',change_html),('PROMPTS',prompts),('TOOLS',tools),('ROWS',rows),('METHODS',methods),('PREVIEW',preview),('COUNT',str(len(catalog)))]:
        document=document.replace('@@'+key+'@@',value)
    return document,data


PAGE='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FinSight · 研究指导审改与完整目录</title><style>
:root{color-scheme:light;--ink:#172e38;--muted:#526a75;--line:#d9e2e4;--accent:#116d67;--paper:#fff}*{box-sizing:border-box}body{margin:0;background:#f2f5f3;color:var(--ink);font:16px/1.8 "Segoe UI","Microsoft YaHei",sans-serif}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}header{background:#173c42;color:#fff;padding:52px max(28px,calc((100vw - 1160px)/2)) 40px}header p{color:#d2e7e5;max-width:900px}h1{font-size:36px;line-height:1.3;margin:12px 0 22px}h2{font-size:26px;margin:0 0 18px}h3{font-size:19px;line-height:1.5;margin:0 0 10px}.eyebrow{font-size:13px;letter-spacing:2px;color:#91d4c8}.pill{display:inline-block;padding:3px 12px;background:#d6eee7;color:#13564d;border-radius:20px;font-size:13px;margin:0 6px 6px 0}.layout{max-width:1220px;margin:auto;display:grid;grid-template-columns:210px minmax(0,1fr);gap:36px;padding:32px 28px}nav{position:sticky;top:20px;align-self:start;font-size:14px}nav a{display:block;padding:8px 0}nav p{color:var(--muted);font-size:12px}section{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:28px;margin-bottom:24px;scroll-margin-top:20px}.lead{font-size:20px;font-weight:600}.muted{color:var(--muted);font-size:14px}.notice{border-left:4px solid #d4a953;padding:12px 18px;background:#fcf8eb}.flow{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.flow div{background:#edf5f1;padding:18px;border-radius:8px}.flow b{display:block;color:var(--accent);margin-bottom:8px}.change{margin:24px 0 32px}.entry{margin:12px 0;border:1px solid var(--line);border-radius:8px;overflow:hidden}.entry summary{cursor:pointer;padding:16px 18px;background:#f8faf9}.entry summary strong{font-weight:600}.entry summary span{display:block;font-size:12px;color:var(--muted);margin-left:17px;overflow-wrap:anywhere}.entry[open] summary{border-bottom:1px solid var(--line)}.body{padding:18px 22px;overflow-wrap:anywhere}.body h1{font-size:26px}.body h2{font-size:22px;margin-top:26px}.body h3{margin-top:20px}pre{font:14px/1.9 Consolas,"Microsoft YaHei",monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:0}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}th{background:#edf3f1}blockquote{border-left:3px solid #8ab6ac;padding-left:18px;color:var(--muted);margin:18px 0}.controls{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}input,select,button{font:inherit;padding:10px 12px;border:1px solid #bbccca;border-radius:7px;background:white;color:var(--ink)}input{min-width:150px;flex:1}button{cursor:pointer}button:hover{background:#eaf4ef}[hidden]{display:none!important}.status{font-size:13px;color:var(--muted)}footer{padding:10px 0 40px;color:var(--muted);font-size:13px}.table-wrap{overflow:auto}@media(max-width:760px){header{padding:30px 20px}h1{font-size:28px}.layout{display:block;padding:20px 12px}nav{position:static;display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}nav p{display:none}section{padding:20px 16px}.flow{grid-template-columns:1fr}.body{padding:15px}td,th{padding:8px}}@media print{nav,.controls{display:none}body{background:white}.layout{display:block;padding:0}header{padding:20px;background:white;color:#173c42}header p{color:#526a75}section{break-inside:avoid}details{break-inside:auto}}
</style></head><body><header><div class="eyebrow">FINSIGHT / RESEARCH GUIDANCE REVIEW</div><h1>让重要问题走到有依据的判断</h1><p>研究指导、原生提示词与方法库审改。先保留问题，再检验未知的影响；给出当前倾向及其理由，并在值得继续调查时继续。</p><span class="pill">源代码已审改</span><span class="pill">未部署 · 未做付费效果验证</span><span class="pill">独立 HTML · 无外部资源</span></header><div class="layout"><nav><a href="#overview">01 审改目标与边界</a><a href="#changes">02 修改原因与准确对照</a><a href="#prompts">03 当前提示词清单</a><a href="#tools">04 工具中的研究要求</a><a href="#catalog">05 方法总目录</a><a href="#methods">06 方法全文</a><a href="#validation">07 验证及尚未完成</a><p>对照基线 @@BASE@@<br>生成时 HEAD @@HEAD@@<br>内容取自当前工作树。</p></nav><main>
<section id="overview"><h2>01 / 这次改什么</h2><p class="lead">保留最初值得研究的关系，检查实际回答是否足以支持原题判断。</p><div class="flow"><div><b>提出与委派</b>说明问题及它可能改变的判断；调整范围时保留重要剩余部分。</div><div><b>调查与验收</b>分别决定何时停止取数、何时收束分析；检验未知影响方向、幅度、时点还是精度。</div><div><b>复核与成文</b>检查新发现是否改变答案；正文呈现当前认识，审计经过保留在记录中。</div></div><p>不增加固定任务数、公司数、全文审稿轮次或格式化计划。继续允许依据充分的有限判断、明确假设和合理停止。没有修改预算、工具权限、来源身份或 258k 原生压缩基准。</p><div class="notice">本页“当前”指本次源码修订。线上服务及历史任务冻结配置尚未切换；离线通过只能证明输入与接口兼容，不能证明模型已经研究得更深入。</div></section>
<section id="changes"><h2>02 / 为什么这样改</h2><p class="muted">每项包含目的与准确源码差异。没有把上一题的公司、数字或应得结论写进通用规则。</p>@@CHANGES@@</section>
<section id="prompts"><h2>03 / 当前提示词清单</h2><p>覆盖本次 Sol 主持、Flash 委派的原生研究路径。下面区分常驻、条件注入与其他写作节点可用摘要；它们并非每次全部进入模型。具体题面、日期、当前稿、来源与复核结果属于动态任务输入。</p>@@PROMPTS@@@@PREVIEW@@<details class="entry"><summary><strong>动态输入与宿主规则</strong><span>每次准入/恢复生成，不能用一份静态提示词替代</span></summary><div class="body"><ul><li>原始题面、当前命令、研究截止日；委派时原题独立保留，question/context 由负责人生成。</li><li>当前稿件、来源导航、工作笔记、已完成调查与意见处理；是待检查研究内容，不是系统授权或自动成立的事实。</li><li>工具 schema 与回执随实际授权提供；此页列出与研究收口相关的工具说明，检索供应商参数仍由工具目录提供。</li><li>底座原生压缩摘要与运行上下文：本次未改其上游模板，也未将历史纠错自动转为新的有效结论。</li><li>模型选择、推理强度、预算和重试属于宿主配置；方法不能授予权限或额度。</li></ul></div></details></section>
<section id="tools"><h2>04 / 工具里的研究要求</h2><p>这部分和系统指引共同影响行为。已同步委派、验收和意见处理说明；字段及线协议保持兼容。</p>@@TOOLS@@</section>
<section id="catalog"><h2>05 / 方法总目录 · @@COUNT@@ 项</h2><p>完整方法通过 get_research_method 按 ID/章节读取；financial_quality 复用 finance 的财务质量章节。基本研究职责另列于提示词清单。</p><div class="table-wrap"><table><thead><tr><th>ID</th><th>方法</th><th>版本</th><th>本轮状态</th></tr></thead><tbody>@@ROWS@@</tbody></table></div></section>
<section id="methods"><h2>06 / 当前方法全文</h2><div class="controls"><input id="search" aria-label="搜索方法" placeholder="搜索 ID、标题或正文关键词"><button id="expand" type="button">展开可见方法</button><button id="collapse" type="button">折叠方法</button></div><p class="status" id="count" aria-live="polite"></p>@@METHODS@@</section>
<section id="validation"><h2>07 / 验证与后续</h2><p>离线检查覆盖实际指引拼装、方法章节读取及版本、委派与原题交接、原生验收兼容；本页由源文件生成，避免清单与配置手工漂移。真实研究质量仍需后续有预算的验收，不能用词句检查或调用次数证明。</p><p><b>仍未在本次解决：</b>复核交接再次带入未采纳原始提案的数据投影；详细方法是否被模型主动读取；模型能否将新发现转化为更深入的条件判断；长上下文对取舍能力的实际影响。它们不会因为修改了说明而被标为通过。</p><p>后续应固定一个重要关系及已有证据，观察原问题是否保留、新证据是否改变判断、未知参数是否得到合理处理，以及正文是否准确呈现研究结果。允许作出“当前无法完成这一判断”的结论，但要和一般资料缺口分开。</p></section><footer>由维护中的方法资源和提示词函数生成。生成清单及哈希保存在相邻 JSON 文件；不包含凭据、完整模型推理或私有来源正文。</footer></main></div><script>
const entries=[...document.querySelectorAll('#methods .entry')];function filter(){let q=document.querySelector('#search').value.trim().toLocaleLowerCase();let count=0;entries.forEach(e=>{e.hidden=!e.textContent.toLocaleLowerCase().includes(q);if(!e.hidden)count++});document.querySelector('#count').textContent=`显示 ${count} / ${entries.length} 项方法`;}document.querySelector('#search').addEventListener('input',filter);document.querySelector('#expand').onclick=()=>entries.filter(e=>!e.hidden).forEach(e=>e.open=true);document.querySelector('#collapse').onclick=()=>entries.forEach(e=>e.open=false);document.querySelectorAll('.jump').forEach(a=>a.addEventListener('click',()=>{document.querySelector('#search').value='';filter();document.querySelector(a.hash).open=true}));filter();
</script></body></html>'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--compare-ref',default='HEAD')
    args=parser.parse_args()
    document,manifest=render(args.compare_ref)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(document,encoding='utf-8')
    args.output.with_suffix('.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'html':str(args.output),'methods':len(manifest['methods']),'prompt_components':len(manifest['prompt_components'])},ensure_ascii=False))


if __name__=='__main__':
    main()
