"""Observed document locators, using markdown-it rather than generated URLs.

SEC's hosted text sometimes removes hrefs but retains its filing-index table.
That explicit, bounded compatibility route resolves only filenames in its
Document column against the already captured accession directory.
"""
import re
from urllib.parse import urljoin, urlsplit

from .external_sources import ExternalSourceError, _canonicalize_candidate_url


def observed_document_links(text: str, parent_url: str, *, limit: int = 40) -> list[dict]:
    from markdown_it import MarkdownIt

    tokens = MarkdownIt('commonmark').enable('table').parse(text)
    candidates = []
    for token in tokens:
        children = token.children or []
        for i, child in enumerate(children):
            if child.type == 'link_open':
                label = []
                for following in children[i + 1:]:
                    if following.type == 'link_close':
                        break
                    label.append(following.content)
                candidates.append((child.attrGet('href'), ''.join(label), 'markdown_link'))

    parsed = urlsplit(parent_url)
    if (parsed.hostname in {'sec.gov', 'www.sec.gov'} and
            re.fullmatch(r'/Archives/edgar/data/\d+/\d{18}/\d{10}-\d{2}-\d{6}-index\.html?', parsed.path)):
        rows, cells = [], None
        for token in tokens:
            if token.type == 'tr_open':
                cells = []
            elif token.type == 'inline' and cells is not None:
                cells.append(token.content.strip())
            elif token.type == 'tr_close' and cells is not None:
                rows.append(cells)
                cells = None
        document_column = None
        for cells in rows:
            if 'Document' in cells and 'Type' in cells:
                document_column = cells.index('Document')
                continue
            if document_column is not None and len(cells) > document_column:
                filename = cells[document_column].split(' ', 1)[0]
                if re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:htm|html|txt|xml|xsd)', filename):
                    candidates.append((filename, filename,
                        'runtime_compatibility:sec_filing_index_document_column'))

    links, seen = [], {parent_url}
    for href, label, origin in candidates:
        if not href or href.startswith('#'):
            continue
        try:
            url = _canonicalize_candidate_url(urljoin(parent_url, href))
        except ExternalSourceError:
            continue
        if url in seen:
            continue
        seen.add(url)
        links.append({'url': url, 'title': label[:512] or url, 'origin': origin})
        if len(links) >= limit:
            break
    return links
