"""Read-only, offline report presentation. Research objects remain unchanged."""
from __future__ import annotations

import base64
from html import escape
import io
import re
from urllib.parse import urlsplit

from markdown_it import MarkdownIt


def safe_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in {"https", "http"} and parsed.netloc else None
    except ValueError:
        return None


def citation_cards(report):
    """A readable projection, not a replacement for canonical citation identity."""
    cards = []
    for number, (key, citation) in enumerate(report.get("citations", {}).items(), 1):
        claim = citation.get("claim") or {}
        sources = []
        for source in citation.get("sources", []):
            calc = source.get("calculation") or (source if
                source.get("result_state") == "non_authoritative_metric"
                and source.get("arithmetic_verified") is True else {})
            url = safe_url(source.get("source_url"))
            urls = list(dict.fromkeys(filter(None, [url, *(
                safe_url(v) for v in source.get("citation_urls", []))])))
            title = source.get("title")
            if not title:
                trace = source.get("formula_trace") or {}
                title = trace.get("metric_title") or source.get("metric_id")
                if not title:
                    title = "来源绑定计算" if calc else "已绑定原文"
                if source.get("ticker"):
                    title = source["ticker"] + " · " + title
            details = " · ".join(dict.fromkeys(str(source[k]) for k in
                ("fiscal_period", "period", "period_start", "period_end", "publication_date", "unit") if source.get(k)))
            quotes = (claim.get("citation_quotes") or {}).get(source.get("source_id"), [])
            # Organization citations carry the authorized, checkpoint-bound
            # excerpt directly; no additional source lookup is needed on export.
            if not quotes and isinstance(source.get("text"), str) and source["text"]:
                quotes = [source["text"]]
            calculations = []
            if calc.get("expression"):
                calculations.append(f"{calc['expression']} = {calc.get('value_decimal', '')} {calc.get('result_unit', '')}")
                for name, operand in calc.get("operands", {}).items():
                    provenance = operand.get("source_provenance") or {}
                    calculations.append(f"{name} = {operand.get('value_decimal', '')} "
                        + " · ".join(str(provenance[k]) for k in
                            ("title", "fiscal_period", "period_end", "unit") if provenance.get(k)))
                    if operand.get("assumption_note"):
                        calculations.append("假设：" + str(operand["assumption_note"]))
                    for link in [provenance.get("source_url"), *provenance.get("citation_urls", [])]:
                        if safe_url(link) and link not in urls:
                            urls.append(link)
                if calc.get("rationale"):
                    calculations.append(calc["rationale"])
                calculations.append("作者计算，非发行人直接披露；算术验证不等于金融口径验证。")
            elif calc:
                calculations.append("计算回执摘要：" + str(calc.get("value_decimal", ""))
                    + " " + str(calc.get("result_unit") or calc.get("unit") or "")
                    + "；此摘要未包含完整公式与操作数，请回读原始计算依据。")
            if source.get("value_decimal") is not None:
                calculations.append(f"{source['value_decimal']} {source.get('unit', '')}")
            trace = source.get("formula_trace") or {}
            if trace.get("formula"):
                calculations.append(trace["formula"])
                calculations.extend(f"{p.get('metric_id', '')} = {p.get('value_decimal', '')} {p.get('unit', '')}"
                    for p in trace.get("inputs", []))
            sources.append(dict(title=title, details=details, urls=urls,
                                quotes=quotes, calculations=calculations))
        cards.append(dict(number=number, key=key, statement=claim.get("statement", ""),
                          sources=sources))
    return cards


def chart_source_links(chart):
    """Retain chart provenance independently of narrative citation coverage."""
    links = []
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"source_url", "url"} and safe_url(item):
                    links.append(item)
                elif key == "citation_urls" and isinstance(item, list):
                    links.extend(filter(None, (safe_url(url) for url in item)))
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for point in chart.get("points", []):
        visit(point.get("provenance", {}))
    return list(dict.fromkeys(links))


CSS = """
:root{--ink:#172b3d;--muted:#607183;--teal:#087c80;--line:#dbe4e8;--paper:#fff}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:90px}
body{margin:0;background:#edf2f4;color:var(--ink);font-family:"Microsoft YaHei","PingFang SC",sans-serif}
a{color:var(--teal);text-decoration:none}a:hover{text-decoration:underline}
.topbar{background:#102a3a;color:white;padding:17px 4vw;display:flex;justify-content:space-between;align-items:center;gap:18px}
.brand{font-size:16px;font-weight:700;letter-spacing:2px}.edition{font-size:12px;opacity:.75}
.layout{display:grid;grid-template-columns:245px minmax(0,960px);gap:28px;max-width:1280px;margin:32px auto;padding:0 20px}
nav{position:sticky;top:28px;align-self:start;max-height:90vh;overflow:auto;padding:16px 10px}
nav h2{font-size:12px;letter-spacing:2px;color:var(--muted);margin:0 0 16px}
nav a{display:block;font-size:13px;line-height:1.65;color:#42596a;padding:7px 10px;border-left:2px solid var(--line)}
nav a:hover,nav a:focus{border-color:var(--teal);background:#e1eaed}
main{min-width:0;background:var(--paper);box-shadow:0 6px 32px #142a3910;border:1px solid var(--line)}
main,nav{overflow-wrap:anywhere}
header{padding:44px 48px 30px;border-top:5px solid var(--teal);border-bottom:1px solid var(--line)}
.kicker{font-size:12px;letter-spacing:2px;color:var(--teal);font-weight:700}
h1{font-size:32px;line-height:1.55;letter-spacing:-.6px;margin:18px 0 22px}
.status{font-size:12px;color:var(--muted);line-height:1.8}
.stats{display:flex;gap:24px;margin-top:20px;font-size:12px;color:var(--muted)}
.downloads{display:flex;gap:10px;flex-wrap:wrap;margin-top:20px}.downloads a{border:1px solid var(--line);border-radius:4px;padding:7px 14px;font-size:13px}
article,.appendix{padding:12px 48px 36px}
article{font-size:15px;line-height:1.95}
h2{font-size:22px;line-height:1.6;margin:34px 0 17px;padding-top:8px;color:#10364a}
h3{font-size:18px;margin:27px 0 12px}
p{margin:0 0 17px}strong{font-weight:700;color:#12394d}
li{margin:9px 0}ol,ul{padding-left:24px}
blockquote{border-left:3px solid var(--teal);margin:22px 0;padding:12px 20px;background:#f2f8f8;color:#42596a}
sup.cite{font-size:10px;margin:0 2px;white-space:nowrap;line-height:0}
.table-wrap{overflow-x:auto;margin:24px 0;border:1px solid var(--line);border-radius:4px}
table{border-collapse:collapse;width:100%;font-size:12px;line-height:1.75}
th{background:#eaf2f4;color:#163b4e;text-align:left}td,th{padding:11px 12px;vertical-align:top;border-bottom:1px solid var(--line);min-width:110px}
tr:nth-child(even){background:#f8fafb}figure{margin:28px 0;padding:18px;border:1px solid var(--line);break-inside:avoid}
figure img{width:100%;height:auto}figcaption{font-size:13px;line-height:1.8;color:#475e6d}
.appendix{border-top:1px solid var(--line);font-size:13px;line-height:1.8}
.ref{border-bottom:1px solid var(--line);padding:18px 0;scroll-margin-top:28px}
.ref:target{background:#fff7df;outline:3px solid #eed69b;padding:18px 12px}
.ref h3{font-size:15px;margin:0 0 8px}.ref p{margin-bottom:8px}
.source{padding:10px 0 10px 14px;border-left:2px solid #d7e4e8;margin:10px 0}
.meta{color:var(--muted);font-size:12px}details{margin-top:9px}summary{cursor:pointer;color:var(--teal)}
.quote{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#f5f8fa;padding:12px}
pre{max-width:100%;overflow-x:auto;padding:14px;background:#f5f8fa;font-size:12px;line-height:1.7}
code{overflow-wrap:anywhere}footer{font-size:12px;color:var(--muted);padding:22px 48px;background:#f7fafb;border-top:1px solid var(--line)}
@media(max-width:850px){.layout{display:block;margin:16px auto;padding:0 10px}nav{position:static;max-height:190px;margin-bottom:16px;padding:12px;background:white;border:1px solid var(--line)}header{padding:28px 22px 24px}h1{font-size:26px}article,.appendix{padding-left:22px;padding-right:22px}article{font-size:15px}h2{font-size:20px}footer{padding:20px}.edition{display:none}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{body{background:white}.topbar,nav,.downloads{display:none}.layout{display:block;padding:0;margin:0;max-width:none}main{border:0;box-shadow:none}header{padding:0 0 24px}article,.appendix{padding:0}h2,h3{break-after:avoid}tr{break-inside:avoid}a{color:inherit}.ref{break-inside:avoid}.table-wrap{overflow:visible}footer{padding:12px 0}details:not([open]){display:none}}
"""


def html_report(report, review_status, download_links=None):
    from .report_delivery import chart_png, chart_display_unit, readable_report
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    cards = citation_cards(report)
    text, _ = readable_report(report)
    tokens = md.parse(text)
    toc = []
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            anchor = f"section-{len(toc) + 1}"
            token.attrSet("id", anchor)
            toc.append((anchor, tokens[i+1].content))
    body = md.renderer.render(tokens, md.options, {})
    # Replace only rendered text nodes, not attributes or code/link targets.
    def references_in_html(value):
        pieces = re.split(r"(<[^>]+>)", value)
        in_link_or_code = 0
        for i, piece in enumerate(pieces):
            if piece.startswith("<"):
                if re.match(r"<(?:a|code)\b", piece):
                    in_link_or_code += 1
                elif re.match(r"</(?:a|code)>", piece):
                    in_link_or_code = max(0, in_link_or_code-1)
            elif not in_link_or_code:
                pieces[i] = re.sub(r"\[(\d+)\]", lambda m:
                    f'<sup class="cite"><a href="#ref-{m[1]}" aria-label="查看来源 {m[1]}">[{m[1]}]</a></sup>'
                    if 1 <= int(m[1]) <= len(cards) else m[0], piece)
        return "".join(pieces)
    body = references_in_html(body).replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    figures = []
    for i, chart in enumerate(report.get("charts", []), 1):
        data = base64.b64encode(chart_png(chart)).decode("ascii")
        rows = "".join(f"<tr><td>{escape(p['label'])}</td><td>{escape(p['series'])}</td><td>{p['value']:g}</td></tr>" for p in chart["points"])
        figures.append(f'<figure><img alt="{escape(chart["title"], quote=True)}" src="data:image/png;base64,{data}">'
            f'<figcaption><strong>图 {i} · {escape(chart["title"])}</strong>'
            + references_in_html(md.render(chart["interpretation"]))
            + f'<details><summary>查看图表数据 · {escape(chart_display_unit(chart))}</summary>'
            f'<div class="table-wrap"><table><thead><tr><th>项目</th><th>系列</th><th>数值</th></tr></thead><tbody>{rows}</tbody></table></div></details>'
            + '<p class="meta">' + " · ".join(f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">图表来源 {j+1}</a>' for j, url in enumerate(chart_source_links(chart))) + "</p></figcaption></figure>")
    refs = []
    for card in cards:
        sources = []
        for source in card["sources"]:
            links = " · ".join(f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">来源原文{n+1 if len(source["urls"]) > 1 else ""}</a>' for n, url in enumerate(source["urls"]))
            extra = ""
            if source["calculations"]:
                extra += "<p>计算与输入</p>" + "".join(f'<div class="quote">{escape(line)}</div>' for line in source["calculations"])
            if source["quotes"]:
                extra += "<details><summary>展开本引用绑定的摘录</summary>" + "".join(f'<div class="quote">{escape(q)}</div>' for q in source["quotes"]) + "</details>"
            sources.append(f'<div class="source"><strong>{escape(source["title"])}</strong>'
                f'<div class="meta">{escape(source["details"])}</div>{links}{extra}</div>')
        refs.append(f'<section class="ref" id="ref-{card["number"]}"><h3>[{card["number"]}] 引用依据</h3>'
            + (f'<p>{escape(card["statement"])}</p>' if card["statement"] else "")
            + "".join(sources) + ('<p class="meta">此项为研究说明，未绑定外部来源。</p>' if not sources else "") + "</section>")
    navigation = "".join(f'<a href="#{anchor}">{escape(label)}</a>' for anchor, label in toc)
    if figures:
        navigation += '<a href="#charts">图表与出处</a>'
    navigation += '<a href="#sources">引用依据</a>'
    downloads = []
    for label, url in (download_links or {}).items():
        # Only explicitly supplied HTTP(S) URLs or simple sibling filenames.
        if safe_url(url) or (isinstance(url, str) and re.fullmatch(r"[A-Za-z0-9_-]+\.(?:pdf|docx|html|zip)", url)):
            downloads.append(f'<a href="{escape(url, quote=True)}">{escape(label)}</a>')
    return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
        f'<title>{escape(report["title"])}</title><style>{CSS}</style></head><body>'
        '<div class="topbar"><span class="brand">FinSight / 研究</span><span class="edition">报告阅读版 · 可离线阅读</span></div>'
        f'<div class="layout"><nav aria-label="报告目录"><h2>阅读目录</h2>{navigation}</nav><main>'
        f'<header><div class="kicker">RESEARCH REPORT / 研究报告</div><h1>{escape(report["title"])}</h1>'
        f'<div class="status">{escape(review_status)}</div><div class="stats"><span>{len(toc)} 个章节</span>'
        f'<span>{len(cards)} 项引用</span><span>{len(figures)} 张图表</span></div>'
        + (f'<div class="downloads">{"".join(downloads)}</div>' if downloads else "") + '</header>'
        f'<article>{body}</article>'
        + (f'<section class="appendix" id="charts"><h2>图表与出处</h2>{"".join(figures)}</section>' if figures else "")
        + f'<section class="appendix" id="sources"><h2>引用依据</h2><p class="meta">编号与正文对应。引用说明与摘录保留作者的证据绑定，展示不代表对结论的另行确认。</p>{"".join(refs)}</section>'
        '<footer>FinSight · 本阅读版保留报告原有正文、引用对应关系及图表数据。审阅意见与运行记录单独保存。</footer>'
        '</main></div></body></html>').encode("utf-8")


def pdf_report(report, review_status):
    """Typeset parsed Markdown, retaining emphasis, lists and readable references."""
    from pathlib import Path
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from matplotlib import get_data_path
    from .report_delivery import readable_report, chart_png
    regular = Path("C:/Windows/Fonts/msyh.ttc")
    bold = Path("C:/Windows/Fonts/msyhbd.ttc")
    font = "FinCJK" if regular.is_file() else "STSong-Light"
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font, str(regular), subfontIndex=0) if regular.is_file() else UnicodeCIDFont(font))
    bold_font = "FinCJKBold" if bold.is_file() else font
    if bold_font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(bold_font, str(bold), subfontIndex=0))
    pdfmetrics.registerFontFamily(font, normal=font, bold=bold_font, italic=font, boldItalic=bold_font)
    fallback = "FinSymbols"
    if fallback not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(fallback, str(Path(get_data_path()) / "fonts/ttf/DejaVuSans.ttf")))
    glyphs = getattr(pdfmetrics.getFont(font).face, "charToGlyph", None)
    symbols = pdfmetrics.getFont(fallback).face.charToGlyph
    def txt(value):
        return "".join((f'<font name="{fallback}">{escape(c)}</font>' if glyphs is not None and ord(c) not in glyphs and ord(c) in symbols else escape(c))
            if c != "\n" else "<br/>" for c in str(value))
    body_style = ParagraphStyle("Body", fontName=font, fontSize=10, leading=17, spaceAfter=7.5, wordWrap="CJK", textColor=colors.HexColor("#172b3d"))
    small = ParagraphStyle("Small", parent=body_style, fontSize=8, leading=12, spaceAfter=5)
    heading = ParagraphStyle("Heading", parent=body_style, fontName=bold_font, fontSize=15, leading=23, spaceBefore=19, spaceAfter=12, keepWithNext=True)
    title_style = ParagraphStyle("Title", parent=heading, fontSize=23, leading=34, spaceBefore=0, spaceAfter=19)
    text, _ = readable_report(report)
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    def inline(token):
        out = []
        active_link = False
        for child in token.children or []:
            if child.type in {"text", "code_inline"}:
                out.append(txt(child.content))
            elif child.type in {"softbreak", "hardbreak"}:
                out.append("<br/>")
            elif child.type in {"strong_open", "strong_close"}:
                out.append("<b>" if child.type.endswith("open") else "</b>")
            elif child.type in {"em_open", "em_close"}:
                out.append("<i>" if child.type.endswith("open") else "</i>")
            elif child.type == "link_open":
                url = safe_url(child.attrGet("href"))
                active_link = bool(url)
                if url:
                    out.append(f'<link href="{escape(url, quote=True)}" color="#087c80">')
            elif child.type == "link_close" and active_link:
                out.append("</link>")
                active_link = False
        return "".join(out) or txt(token.content)
    def para(value, style=body_style):
        return Paragraph(txt(value), style)
    story = [para("FINSIGHT / RESEARCH", small), para(report["title"], title_style),
             para(review_status, small), Spacer(1, 12)]
    tokens = md.parse(text)
    i, pending_heading, lists, prefix = 0, False, [], ""
    while i < len(tokens):
        token = tokens[i]
        if token.type == "table_open":
            rows = []
            while i < len(tokens) and tokens[i].type != "table_close":
                item = tokens[i]
                if item.type == "tr_open":
                    rows.append([])
                elif item.type == "inline":
                    rows[-1].append(Paragraph(inline(item), small))
                i += 1
            width = max(map(len, rows))
            widths = ([50] + [432 / (width-1)] * (width-1)) if width >= 4 else [482/width]*width
            table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e8f0f3")),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#f6f9fa")]),
                ("LINEBELOW",(0,0),(-1,-1),.35,colors.HexColor("#dbe4e8")),("VALIGN",(0,0),(-1,-1),"TOP"),
                ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
            story.extend([table, Spacer(1,12)])
        elif token.type == "heading_open":
            pending_heading = True
        elif token.type in {"ordered_list_open", "bullet_list_open"}:
            lists.append(int(token.attrGet("start") or 1) if token.type == "ordered_list_open" else None)
        elif token.type in {"ordered_list_close", "bullet_list_close"}:
            lists.pop()
        elif token.type == "list_item_open":
            prefix = (f"{lists[-1]}. " if lists[-1] is not None else "• ")
            if lists[-1] is not None:
                lists[-1] += 1
        elif token.type == "inline":
            story.append(Paragraph(txt(prefix) + inline(token), heading if pending_heading else body_style))
            prefix, pending_heading = "", False
        elif token.type in {"fence", "code_block"}:
            story.append(para(token.content, small))
        i += 1
    if report.get("charts"):
        story.extend([PageBreak(), para("图表与出处", heading)])
    for i, chart in enumerate(report.get("charts", []), 1):
        story.extend([para(f"图 {i} · {chart['title']}", heading),
            Image(io.BytesIO(chart_png(chart)), width=482, height=231.36)])
        for token in md.parse(chart["interpretation"]):
            if token.type == "inline":
                story.append(Paragraph(inline(token), small))
        for url in chart_source_links(chart):
            story.append(Paragraph(f'<link href="{escape(url, quote=True)}" color="#087c80">图表来源：{txt(url)}</link>', small))
    cards = citation_cards(report)
    if cards:
        story.extend([PageBreak(), para("来源索引", heading),
            para("编号与正文对应；网页阅读版另提供本引用绑定的原文摘录。来源、期间及作者测算保留，导出不构成新的研究确认。", small)])
    for card in cards:
        title = "；".join(dict.fromkeys(s["title"] for s in card["sources"])) or "研究说明"
        story.append(para(f'[{card["number"]}] {title}', ParagraphStyle("RefHead",parent=small,fontName=bold_font,spaceBefore=8,keepWithNext=True)))
        if not card["sources"] and card["statement"]:
            story.append(para(card["statement"], small))
        for source in card["sources"]:
            if source["details"]:
                story.append(para(source["details"], small))
            for url in source["urls"]:
                # Visible complete URL remains usable in print and is clickable.
                story.append(Paragraph(f'<link href="{escape(url, quote=True)}" color="#087c80">{txt(url)}</link>', small))
            for line in source["calculations"]:
                story.append(para(line, small))
    output = io.BytesIO()
    def footer(canvas, doc):
        canvas.setStrokeColor(colors.HexColor("#dbe4e8"))
        canvas.line(56, 39, A4[0]-56, 39)
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor("#607183"))
        canvas.drawString(56, 26, "FinSight · 研究报告")
        canvas.drawRightString(A4[0]-56, 26, f"{doc.page}")
    SimpleDocTemplate(output, pagesize=A4, leftMargin=56, rightMargin=56, topMargin=46,
        bottomMargin=52, title=report["title"], author="FinSight").build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
