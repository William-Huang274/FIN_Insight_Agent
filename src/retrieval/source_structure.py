"""Exact-source structural overlay; never rewrites frozen retrieval bodies.

Only explicit table delimiters and numbered post-table notes are recognized.
Nearby text is not automatically a semantic parent. Uncertain bindings abstain.
"""
from bisect import bisect_right
from hashlib import sha256
import json
import re

POLICY = 'source-structure.v1'
HEAD = re.compile(r'(?m)^(?:#{1,6}\s+[^\n]+|(?:PART\s+[IVX]+|ITEM\s+\d+[A-Z]?)[. :\t]+[^\n]*)$', re.I)
TABLE = re.compile(r'\[TABLE:[^\n]*\](.*?)\[/TABLE\]', re.S)
NOTE = re.compile(r'\s*\((\d{1,3}|[a-z])\)\s*\n?([^\n]+)', re.I)


def source_structure(bundle):
    from .library_source_bundle import validate_bundle_text
    validate_bundle_text(bundle)
    text = bundle.get('text') if 'node_recovery' not in bundle else None
    headings = list(HEAD.finditer(text)) if text else []
    heads = [m.start() for m in headings]
    tables = [m for m in TABLE.finditer(text) if '[TABLE:' not in m[1]] if text else []
    substantive = [m for m in tables if re.search(r'[A-Za-z\u3400-\u9fff0-9]', m[1])]
    notes = []
    if text:
        for table in tables:
            note = NOTE.match(text, table.end())
            if not note:
                continue
            # Some HTML tables are presentation-only separators. Walk back
            # across exactly those tables/whitespace, never arbitrary prose.
            candidates = [m for m in substantive if m.end() <= table.end()]
            if not candidates:
                continue
            parent = candidates[-1]
            between = text[parent.end():table.end()]
            remainder = TABLE.sub(lambda m:'' if not re.search(r'[A-Za-z\u3400-\u9fff0-9]', m[1]) else m[0], between)
            if remainder.strip() or not re.search(r'\('+re.escape(note[1])+r'\)', parent[1]):
                continue
            notes.append((note.start(), note.end(), note[1], parent))
    output = {}
    for chunk in bundle['chunks']:
        flags = chunk.get('flags', [])
        if isinstance(flags, str):
            flags = json.loads(flags)
        row = {'policy':POLICY, 'original_kind':chunk.get('kind'),
               'original_flags':flags, 'section':None, 'tables':[], 'footnotes':[],
               'binding_semantics':'explicit_original_structure_not_answer_sufficiency'}
        start,end=chunk.get('source_char_start'),chunk.get('source_char_end')
        if text is None or type(start) is not int or type(end) is not int:
            row['status']='original_roles_only_no_complete_coordinates'
            output[chunk['id']]=row
            continue
        if text[start:end] != chunk['body'] or sha256(chunk['body'].encode()).hexdigest()!=chunk['digest']:
            raise ValueError('source_structure_chunk_mismatch')
        row['status']='verified_original_coordinates'
        index=bisect_right(heads,start)-1
        if index>=0:
            row['section']={'heading':headings[index][0], 'source_char_start':heads[index]}
        for table in substantive:
            if table.start()<end and table.end()>start:
                row['tables'].append(_span(table,text))
        for lo,hi,marker,parent in notes:
            if lo<end and hi>start:
                linked=[c['id'] for c in bundle['chunks'] if
                        c.get('source_char_start',len(text))<parent.end()
                        and c.get('source_char_end',0)>parent.start()]
                row['footnotes'].append({'marker':marker,'source_char_start':lo,'source_char_end':hi,
                    'binding':'explicit_post_table_marker', 'table':_span(parent,text),
                    'table_chunk_ids':linked[:4], 'table_chunk_count':len(linked),
                    'table_readback_truncated':len(linked)>4})
        output[chunk['id']]=row
    return output


def _span(match,text):
    return {'source_char_start':match.start(), 'source_char_end':match.end(),
            'content_sha256':sha256(text[match.start():match.end()].encode()).hexdigest()}


def organization_structure(bundle, document):
    from sec_agent.research_foundation.organization_source_projection import chunk_node_id
    result={}
    for identifier, value in source_structure(bundle).items():
        for note in value['footnotes']:
            note['table_readbacks']=[{'source_space':'organization','operation':'read',
                'document_id':document,'node_id':chunk_node_id(document,n)+':leaf'}
                for n in note.pop('table_chunk_ids')]
        result[chunk_node_id(document,identifier)+':leaf']=value
    return result
