from copy import deepcopy
from markdown_it import MarkdownIt
from apps.workbench.backend.application.report_flow import chart_tokens
from apps.workbench.backend.application.report_delivery import export_report, markdown_blocks
from test_report_delivery import sample


def test_heading_placement_uses_parser_not_fenced_or_ambiguous_heading():
    md=MarkdownIt('commonmark')
    text='## Analysis\n\nEvidence.\n\n### Detail\n\nMore.\n\n## Risks\n\nRisk.'
    tokens,placed=chart_tokens(md,text,[{'after_heading':'Analysis'}])
    i=next(i for i,t in enumerate(tokens) if t.type=='report_chart')
    assert tokens[i+1].type=='heading_open' and tokens[i+2].content=='Risks'
    assert placed=={0}
    assert chart_tokens(md,'```\n## Analysis\n```',[{'after_heading':'Analysis'}])[1]==set()
    assert chart_tokens(md,'## Analysis\n\n## Analysis',[{'after_heading':'Analysis'}])[1]==set()


def test_inline_chart_exports_keep_prose_and_single_figure():
    report=sample();report['narrative_markdown']='## Analysis\n\nFirst evidence.\n\n## Risks\n\nSecond evidence.'
    report['charts'][0]['after_heading']='Analysis'
    original=deepcopy(report)
    html,_=export_report(report,'html');text=html.decode()
    assert text.index('<figure ')<text.index('id="section-2"')
    assert text.count('<figure ')==1
    markdown,_=export_report(report,'md')
    assert markdown.decode().index(report['charts'][0]['title']) < markdown.decode().index('## Risks')
    blocks=markdown_blocks(report['narrative_markdown'],report['charts'])
    assert blocks.index(('chart',0))<blocks.index(('h2','Risks'))
    for fmt in ['pdf','docx','pptx']:
        data,_=export_report(report,fmt);assert len(data)>1000
    assert report==original
