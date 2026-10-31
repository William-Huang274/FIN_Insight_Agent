"""Offline source-container provenance and conservative chapter reconciliation.

DOM identity, parser role, and financial meaning are separate fields. Text
matching establishes a location only when the complete container is unique;
ambiguous matches retain every candidate and never choose a nearby occurrence.
"""
from collections import defaultdict
from hashlib import sha256
import re
from statistics import median
from lxml import html


def normalized(text):
    return ' '.join(text.split())


def _bold(element):
    style = element.get('style', '').lower()
    match = re.search(r'font-weight\s*:\s*([^;]+)', style)
    return element.tag in {'b', 'strong'} or bool(match and (
        match[1].strip() in {'bold', 'bolder'} or
        match[1].strip().isdigit() and int(match[1].strip()) >= 600))


def _all_bold(element):
    """All visible text, not merely one bold word, must have bold ancestry."""
    for text in element.xpath('.//text()'):
        if not str(text).strip():
            continue
        owner = text.getparent()
        if getattr(text, 'is_tail', False):
            owner = owner.getparent()
        bold = False
        while owner is not None:
            bold |= _bold(owner)
            if owner is element:
                break
            owner = owner.getparent()
        if not bold:
            return False
    return True


def following_after_blank_layout(element):
    """Cross only demonstrably empty inline/block formatting siblings.

    Anchors, media, tables, visible tails and unknown elements are boundaries.
    Class-based styling may generate visible content, so is not assumed empty.
    """
    following = element.getnext(); skipped = []
    if normalized(element.tail or ''):
        return None, skipped
    allowed = {'div', 'p', 'span', 'font', 'br'}
    while following is not None:
        if not isinstance(following.tag, str):
            break
        if normalized(''.join(following.itertext())) or normalized(following.tail or ''):
            break
        nodes = list(following.iter())
        if any(not isinstance(n.tag, str) or n.tag not in allowed for n in nodes):
            break
        if any(any(k in n.attrib for k in ('id', 'name', 'class', 'role', 'src', 'href'))
               or re.search(r'background|border|content\s*:|url\(', n.get('style', ''), re.I)
               for n in nodes):
            break
        skipped.append(following.getroottree().getpath(following))
        following = following.getnext()
    return following, skipped


def source_containers(raw):
    try:
        raw.decode('utf-8-sig')
        tree = html.fromstring(raw,parser=html.HTMLParser(encoding='utf-8'))
    except UnicodeDecodeError: tree = html.fromstring(raw)
    root = tree.getroottree()
    digest = sha256(raw).hexdigest()
    targets={a.get('href')[1:] for a in tree.xpath('//a[starts-with(@href,"#")]') if a.get('href')[1:]}
    rows = []; elements = {}; identities = {}
    tags = {'body', 'article', 'section', 'header', 'ul', 'ol', 'p', 'div', 'li', 'table', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
    # One DOM pass; never repeatedly scan the entire document per block.
    for el in tree.iter():
        if not isinstance(el.tag, str) or el.tag not in tags:
            continue
        wrapper = el.tag in {'body', 'article', 'section', 'header', 'ul', 'ol'} or (
            el.tag in {'p', 'div', 'li'} and bool(el.xpath('.//p|.//div|.//table|.//li')))
        excluded = bool(el.xpath('ancestor-or-self::script|ancestor-or-self::style|'
                                'ancestor-or-self::nav|ancestor-or-self::aside|'
                                'ancestor-or-self::footer|ancestor-or-self::*[local-name()="hidden"]'))
        text = '' if wrapper else normalized(''.join(el.itertext()))
        if not text and not wrapper:
            continue
        xpath = root.getpath(el); sid = digest + ':' + xpath
        role = 'container' if wrapper else 'table' if el.tag == 'table' else 'paragraph'
        level = None; basis = 'original_container'
        if re.fullmatch('h[1-6]', el.tag):
            role = 'heading'; level = int(el.tag[1]); basis = 'explicit_html_heading'
        elif el.get('role') == 'heading' and el.get('aria-level', '').isdigit():
            role = 'heading'; level = int(el.get('aria-level')); basis = 'explicit_aria_heading'
        elif not wrapper and el.tag != 'table' and len(text) <= 180 and _all_bold(el):
            # A style candidate is not an independently verified heading.
            role = 'styled_heading_candidate'; basis = 'whole_container_bold'
        row = {'id': sid, 'xpath': xpath, 'html_id': el.get('id'), 'tag': el.tag,
               'role': role, 'level': level, 'role_basis': basis,
               'text': text, 'excluded_navigation': excluded,
               'text_sha256': sha256(text.encode()).hexdigest()}
        row['referenced_anchor']=bool((el.get('id') and el.get('id') in targets) or
            any(a.get('id') in targets or a.get('name') in targets for a in el.xpath('.//a[@id or @name]')))
        sizes=[]
        if not wrapper and el.tag!='table':
            for styled in el.iter():
                match=re.search(r'font-size\s*:\s*([\d.]+)(pt|px)\b',styled.get('style') or '',re.I)
                if match:sizes.append(float(match[1])*(.75 if match[2].lower()=='px' else 1))
        row['font_size_pt']=max(sizes) if sizes else None
        links=normalized(''.join(''.join(a.itertext()) for a in el.xpath('.//a[starts-with(@href,"#")]')))
        row['internal_link_only']=bool(text and links==text)
        rows.append(row); elements[sid] = el; identities[el] = sid
    for row in rows:
        el = elements[row['id']]; parent = el.getparent()
        while parent is not None and parent not in identities:
            parent = parent.getparent()
        row['parent_id'] = identities.get(parent)
        table = el.getparent()
        while table is not None and table.tag != 'table':
            table = table.getparent()
        row['table_id'] = identities.get(table)
        if row['role'] == 'table':
            cells = el.xpath('./tr/td|./tr/th|./tbody/tr/td|./tbody/tr/th|./thead/tr/th|./thead/tr/td')
            has_numeric = any(re.search(r'\d', ''.join(c.itertext())) for c in cells)
            explicit_layout = el.get('role') in {'presentation', 'none'}
            row['table_role'] = 'layout_explicit' if explicit_layout else 'physical_table_unresolved'
            row['numeric_content_present'] = has_numeric
            row['financial_semantics_inferred'] = False
    children = defaultdict(list)
    body_sizes=[r['font_size_pt'] for r in rows if r['role']=='paragraph' and len(r['text'])>180 and r['font_size_pt']]
    body_size=median(body_sizes) if body_sizes else None
    for row in rows:
        if row['role']=='styled_heading_candidate':
            large=bool(body_size and row['font_size_pt'] and row['font_size_pt']>body_size*1.15)
            el=elements[row['id']]; following, skipped=following_after_blank_layout(el)
            followed_by_prose=(following is not None and isinstance(following.tag, str)
                               and len(normalized(''.join(following.itertext())))>180)
            if skipped:
                followed_by_prose=bool(followed_by_prose and following.tag in {'p','div'}
                    and not following.xpath('.//table|.//img|.//svg|.//video|.//h1|.//h2|.//h3|.//h4|.//h5|.//h6'))
                row['blank_layout_context']={'skipped_xpaths':skipped,
                    'following_xpath':root.getpath(following) if following is not None else None,
                    'followed_by_prose':followed_by_prose}
            row['heading_eligible']=bool(large or row['referenced_anchor'] or (not row['table_id'] and followed_by_prose))
            row['role_basis']='whole_container_bold_referenced_anchor' if row['referenced_anchor'] else 'whole_container_bold_larger_font' if large else 'whole_container_bold_followed_by_prose' if row['heading_eligible'] else 'whole_container_bold_only'
            if row['table_id'] and not large:
                row['role']='table_label_candidate'
        if row['table_id'] and row['role'] in {'heading', 'styled_heading_candidate'}:
            children[row['table_id']].append(row['id'])
    for row in rows:
        if row['role'] == 'table':
            row['embedded_heading_ids'] = children[row['id']]
            if children[row['id']] and row['table_role'] != 'layout_explicit':
                row['table_role'] = 'mixed_structure_requires_review'
    return rows


def attach_source_structure(blocks, raw, metadata=None, sec=False):
    rows = source_containers(raw); by_text = defaultdict(list); table_surfaces = defaultdict(list)
    for row in rows:
        if row['text'] and not row['excluded_navigation']:
            by_text[row['text']].append(row)
            if row['role'] == 'table':
                table_surfaces[re.sub(r'\s+', '', row['text'])].append(row)
    linked = 0
    for block in blocks:
        text = normalized(block['text'])
        matches = by_text.get(text, [])
        if block['kind'] == 'table':
            # Cell delimiters are exporter formatting, not original content.
            # Match the complete ordered cell surface, never a title substring.
            surface = ''.join(re.sub(r'\s+', '', c['text']) for key in ('headers', 'rows', 'footer')
                              for row in block.get(key, []) for c in row)
            matches = table_surfaces.get(surface, []) if surface else []
        block['source_container_candidates'] = [r['id'] for r in matches]
        block['source_location_status'] = 'unique_complete_container' if len(matches) == 1 else 'ambiguous' if matches else 'unresolved'
        if len(matches) != 1:
            continue
        row = matches[0]; linked += 1
        block['source_container_id'] = row['id']; block['source_role'] = row['role']
        block['source_parent_id'] = row['parent_id']
        block['source_font_size_pt']=row['font_size_pt']
        if row['role'] == 'table':
            block['source_table_role'] = row['table_role']
            block['embedded_heading_ids'] = row['embedded_heading_ids']
        elif row['role'] == 'heading':
            block.update(kind='heading', level=row['level'], heading_basis=row['role_basis'])
        elif sec and row['role'] == 'styled_heading_candidate' and row.get('heading_eligible') and not row['table_id']:
            # Retain uncertainty and original role; generic chapter topology only.
            block.update(kind='heading', level=3, heading_basis=row['role_basis'])
        if row.get('internal_link_only'):
            block['heading_usage']='navigation_reference'
    # Metadata is a document property. Prefer the uniquely corresponding original
    # visible H element; do not substitute a site-suffixed metadata title for it.
    title = normalized((metadata or {}).get('title', ''))
    candidates = [r for r in rows if r['role'] == 'heading' and not r['excluded_navigation']
                  and (r['text'] == title or title.startswith(r['text'] + ' | ')
                       or title.startswith(r['text'] + ' - '))]
    document_title = {'metadata_title': title, 'source_candidates': [r['id'] for r in candidates],
                      'status': 'verified_original_heading' if len(candidates) == 1 else 'unresolved'}
    if len(candidates) == 1:
        row = candidates[0]; document_title.update(text=row['text'], source_container_id=row['id'])
        if not any(b.get('source_container_id') == row['id'] for b in blocks):
            blocks.insert(0, {'kind': 'heading', 'text': row['text'], 'level': 1,
                             'heading_basis': 'metadata_and_original_heading_agree',
                             'source_container_id': row['id'], 'source_role': row['role'],
                             'source_location_status': 'unique_complete_container',
                             'source_container_candidates': [row['id']]})
    return blocks, {'source_containers': rows, 'document_title': document_title,
                    'container_mapping': {'unique_blocks': linked, 'block_count': len(blocks)},
                    'source_identity_namespace': 'raw_sha256:original_dom_xpath'}


PART = re.compile(r'^PART\s+([IVX]+)\b', re.I)
ITEM = re.compile(r'^ITEM\s+(\d+(?:\.\d+)?[A-Z]?)\b', re.I)


def reconcile_chapters(blocks, sec=False, containers=()):
    """One tree for downstream pre-chunks; repeated labels stay occurrences.

No cross-Part Item merging. Native/parser levels remain in separate fields.
Repeated running labels restore their existing path, rather than adding nodes.
"""
    nodes = []; stack = []; active_part = None; known = {}; by_id = {}
    sources={r['id']:r for r in containers}
    for index, block in enumerate(blocks):
        if block['kind'] != 'heading':
            block['chapter_ids'] = [n['id'] for n in stack]
            block['chapter_blocks'] = [n['block'] for n in stack]
            embedded=[]
            for sid in block.get('embedded_heading_ids',[]):
                source=sources[sid]
                node={'id':'embedded:'+sid,'block':index,'title':source['text'],
                      'level':source['level'],'parent_id':stack[-1]['id'] if stack else None,
                      'source_container_id':sid,'basis':source['role_basis'],
                      'embedded_in_table':block.get('source_container_id'),
                      'scope':'physical_container_only','occurrence_blocks':[index]}
                nodes.append(node);embedded.append(node['id'])
            block['embedded_chapter_ids']=embedded
            continue
        if block.get('heading_usage')=='navigation_reference':
            block['chapter_ids']=[n['id'] for n in stack]
            block['chapter_blocks']=[n['block'] for n in stack]
            continue
        text = normalized(block['text']); level = block.get('level')
        block['parser_level'] = level
        part = PART.match(text) if sec else None
        item = ITEM.match(text) if sec else None
        key = None
        signature_boundary = sec and block.get('sec_section_boundary') == 'signatures'
        if signature_boundary:
            active_part = None; stack = []; level = 1
        elif part:
            active_part = part[1].upper(); level = 1; key = ('part', active_part)
        elif item:
            level = 2 if active_part else 1; key = ('item', active_part, item[1].upper())
        elif sec and isinstance(level, int):
            formal = next((n for n in reversed(stack) if n['basis']=='sec_part_item_label'), None)
            minimum_level = formal['level'] + 1 if formal else 1
            if block.get('source_font_size_pt'):
                size=block['source_font_size_pt'];level=minimum_level
                for ancestor in reversed(stack):
                    # Font heuristics operate inside the current formal section.
                    # In 8-K filings an Item can be a root without any Part.
                    if ancestor is formal:break
                    other=ancestor.get('font_size_pt')
                    if ancestor['basis']=='sec_part_item_label' or not other:continue
                    if other==size:level=ancestor['level'];break
                    if other>size:level=ancestor['level']+1;break
            level=max(minimum_level,level)
        if key in known:
            node = known[key]; block['chapter_occurrence_of'] = node['id']
            node['occurrence_blocks'].append(index)
            # Repeated Part/Item page headers must not discard the subsection.
            if node['id'] not in [n['id'] for n in stack]:
                path = []; current = node
                while current:
                    path.append(current); current = by_id.get(current['parent_id'])
                stack = list(reversed(path))
        else:
            if not isinstance(level, int) or level < 1:
                stack = []
            else:
                while stack and stack[-1]['level'] >= level:
                    stack.pop()
            node = {'id': f'chapter:{index}', 'block': index, 'title': text, 'level': level,
                    'parent_id': stack[-1]['id'] if stack else None,
                    'source_container_id': block.get('source_container_id'),
                    'font_size_pt':block.get('source_font_size_pt'),
                    'basis': 'sec_signature_boundary' if signature_boundary else 'sec_part_item_label' if key else block.get('heading_basis', 'parser_heading'),
                    'occurrence_blocks': [index]}
            nodes.append(node); by_id[node['id']] = node
            if key: known[key] = node
            if isinstance(level, int) and level > 0: stack.append(node)
        block['level'] = level
        block['chapter_ids'] = [n['id'] for n in stack]
        block['chapter_blocks'] = [n['block'] for n in stack]
    return nodes
