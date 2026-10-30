"""Offline structural diagnostics and sentence pre-chunks, never recall scores."""
from collections import Counter
import json
import re
from xml.etree import ElementTree as ET
from lxml import html
from retrieval.narrative_chunks import sentence_groups
from probe_document_parsers import parse
from restore_parser_paragraphs import restore
from structured_web_blocks import normalize_web
from source_structure_contract import attach_source_structure, reconcile_chapters


def norm(text):return ' '.join(text.split())


def outline(blocks):
    headings=[];stack=[];issues=[]
    for i,b in enumerate(blocks):
        if b['kind']!='heading' or b.get('chapter_occurrence_of') or b.get('heading_usage')=='navigation_reference':continue
        level=b.get('level')
        if type(level)!=int or level<1:
            issues.append({'kind':'heading_level_unknown','block':i});stack=[]
        else:
            if stack and level>stack[-1]['level']+1:
                issues.append({'kind':'heading_level_jump','block':i})
            while stack and stack[-1]['level']>=level:stack.pop()
        parent=stack[-1]['block'] if stack else None
        headings.append({'block':i,'title':b['text'],'level':level,'parent_block':parent,
                         'basis':b.get('heading_basis','parser_declared_not_independently_verified')})
        if type(level)==int and level>0:stack.append({'level':level,'block':i})
        if len(norm(b['text']))<8:
            issues.append({'kind':'short_heading_requires_review','block':i,'text':b['text']})
    return headings,issues


def markdown_blocks(text):
    blocks=[];pending=[];fenced=False
    def flush():
        if pending:blocks.append({'kind':'text','text':''.join(pending)});pending.clear()
    for line in text.splitlines(keepends=True):
        if re.match(r'^\s*(```|~~~)',line):fenced=not fenced
        match=None if fenced else re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$',line)
        if match:
            flush();blocks.append({'kind':'heading','level':len(match[1]),'text':match[2],
                                  'heading_basis':'explicit_markdown_atx'})
        elif not line.strip():pending.append(line);flush()
        else:pending.append(line)
    flush();return blocks


def inspect(raw,job):
    mime=(job['capture'].get('content_type') or '').lower();issues=[];repairs=[];extra={}
    stripped=raw.lstrip()
    sniffed_json=None;valid_json_prefix=False
    if 'json' not in mime and stripped.startswith((b'{',b'[')):
        try:sniffed_json=json.loads(raw);valid_json_prefix=True
        except (ValueError,UnicodeError):
            issues.append({'kind':'bracket_prefixed_text_not_valid_json'})
    if stripped.startswith(b'%PDF'):
        from io import BytesIO
        from pypdf import PdfReader
        doc=PdfReader(BytesIO(raw));blocks=[]
        for i,page in enumerate(doc.pages):
            blocks.append({'kind':'text','text':page.extract_text() or '', 'page':i+1})
        extra={'pdf_outline':str(doc.outline),'pages':len(doc.pages)};route='pypdf_text_diagnostic'
        issues.append({'kind':'pdf_font_heading_hierarchy_not_qualified'})
        if not any(norm(b['text']) for b in blocks):issues.append({'kind':'pdf_no_text_layer'})
    elif 'json' in mime or valid_json_prefix:
        obj=json.loads(raw) if 'json' in mime else sniffed_json;route='structured_json';blocks=[]
        extra={'root_type':type(obj).__name__,'root_keys':list(obj) if isinstance(obj,dict) else [],
               'root_count':len(obj) if isinstance(obj,(dict,list)) else 1}
        return {'route':route,'blocks':[],'outline':[],'issues':[],
                'pre_chunks':[],'structured_object':obj,'chapter_applicability':'not_applicable',**extra}
    elif ('xml' in mime or stripped.startswith(b'<?xml')) and b'<html' not in raw[:1000].lower():
        root=ET.fromstring(raw);route='structured_xml';blocks=[]
        extra={'root_tag':root.tag,'elements':sum(1 for _ in root.iter()),
               'structured_xml':raw.decode('utf-8-sig')}
        return {'route':route,'blocks':[],'outline':[],'issues':[], 'pre_chunks':[],
                'chapter_applicability':'not_applicable',**extra}
    elif 'html' in mime or re.search(br'<(?:!doctype\s+html|html|body)\b',raw[:2000],re.I):
        route='edgartools' if 'sec.gov' in job['domain'] else 'trafilatura_xml'
        output=parse(raw,job['title'],route,job.get('form') or '')
        blocks=output['blocks'] if route=='edgartools' else normalize_web(output)
        blocks,repairs=restore(blocks,raw)
        blocks,structure=attach_source_structure(blocks,raw,output.get('document_metadata'),route=='edgartools')
        tree=html.fromstring(raw)
        explicit=[{'text':norm(''.join(n.itertext())),'level':int(n.tag[1]),
                   'xpath':tree.getroottree().getpath(n)} for n in tree.xpath('//h1|//h2|//h3|//h4|//h5|//h6')
                   if not n.xpath('ancestor::nav|ancestor::script|ancestor::style')]
        recognized={norm(b['text']) for b in blocks if b['kind']=='heading'}
        missing=[h for h in explicit if h['text'] and h['text'] not in recognized]
        extra={'explicit_html_headings':explicit,'unmatched_explicit_headings':missing,
               'parser_sections':output.get('sections',{}),'form_resolution':output.get('form_resolution'),
               'original_tables':len(tree.xpath('//table'))}
        extra.update(structure)
        del output,tree
        if missing:issues.append({'kind':'explicit_heading_not_retained_as_heading','count':len(missing)})
        if route=='trafilatura_xml' and extra['original_tables']>sum(b['kind']=='table' for b in blocks):
            issues.append({'kind':'fewer_tables_than_dom_requires_layout_table_review'})
        # Independent comparator on all HTML: retain native hierarchy/table
        # tuples, do not flatten its full output into retrieval evidence.
        try:
            comparison=parse(raw,job['title'],'datamule_clean',job.get('form') or '')
            extra['datamule_comparison']={'native':comparison['native'],'tuples':comparison['tuples']}
        except Exception as exc:
            issues.append({'kind':'datamule_comparator_failed','error':type(exc).__name__,'detail':str(exc)[:500]})
    else:
        text=raw.decode('utf-8-sig');route='markdown_or_plain_text';blocks=markdown_blocks(text)
    chapters=reconcile_chapters(blocks,route=='edgartools',extra.get('source_containers',()))
    extra['chapter_tree']=chapters
    headings,heading_issues=outline(blocks);issues+=heading_issues
    chunks=[];stack=[]
    for i,b in enumerate(blocks):
        chapter_path=b.get('chapter_blocks',[])
        if b['kind']=='heading':
            level=b.get('level')
            if not isinstance(level,int):stack=[]
            else:
                while stack and stack[-1][0]>=level:stack.pop()
                stack.append((level,i))
            continue
        if b['kind']=='table':
            chunks.append({'kind':'table','block':i,'heading_path':chapter_path,
                           'chapter_ids':b.get('chapter_ids',[]),'source_container_id':b.get('source_container_id'),
                           'representation':'original_table_cells_not_numeric_SQL_replacement'})
            continue
        for start,end,text in sentence_groups(b['text']):
            chunks.append({'kind':'prose','block':i,'start':start,'end':end,'heading_path':chapter_path,
                           'chapter_ids':b.get('chapter_ids',[]),'source_container_id':b.get('source_container_id')})
            if len(text.encode())>6000:issues.append({'kind':'oversize_complete_sentence','block':i,'start':start,'end':end})
    if not headings and sum(len(b['text']) for b in blocks)>20000:
        issues.append({'kind':'long_document_without_recognized_heading'})
    return {'route':route,'blocks':blocks,'outline':headings,'issues':issues,
            'paragraph_repairs':repairs,'pre_chunks':chunks,**extra}
