"""Place saved charts beside exact section anchors using the Markdown parser."""
from markdown_it.token import Token


def chart_tokens(md, text, charts):
    tokens = md.parse(text)
    headings = [(i, tokens[i+1].content, int(t.tag[1:])) for i,t in enumerate(tokens) if t.type == 'heading_open']
    insertions, placed = {}, set()
    for index, chart in enumerate(charts):
        matches = [h for h in headings if chart.get('after_heading') and h[1] == chart['after_heading']]
        if len(matches) != 1:
            continue  # Legacy or ambiguous placement remains a visible appendix.
        start, _, level = matches[0]
        end = next((i for i,_,depth in headings if i > start and depth <= level), len(tokens))
        item = Token('report_chart', '', 0)
        item.meta = {'index': index, 'line': tokens[end].map[0] if end < len(tokens) else len(text.splitlines(keepends=True))}
        insertions.setdefault(end, []).append(item)
        placed.add(index)
    result=[]
    for i in range(len(tokens)+1):
        result.extend(insertions.get(i, []))
        if i<len(tokens):result.append(tokens[i])
    return result, placed
