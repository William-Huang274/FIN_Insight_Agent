"""Recover complete SEC Item sequences using unique original TOC bounds."""
from collections import defaultdict
import re

from source_structure_contract import normalized


def complete_section_sequences(blocks, sources, membership, spans, sections, native_membership=None):
    """Require a unique Item heading, ordered containers and the entire section.

    No nearest-text choice, old chapter assumption, or None/Reserved special case.
    Tables, overlapping ranges and partial section text remain unresolved.
    """
    proposals=[]
    for key, section in sections.items():
        item=section['fields'].get('item')
        whole=normalized(section.get('native_text') or '')
        if item is None or not whole:continue
        def candidates(block):
            ids=([block['source_container_id']] if block.get('source_container_id') else block.get('source_container_candidates',[]))
            return [sid for sid in ids if sid in sources and sid in spans and membership.get(sid)=={key}
                    and not sources[sid].get('table_id') and not sources[sid].get('excluded_navigation')
                    and not sources[sid].get('internal_link_only')
                    and normalized(sources[sid]['text'])==normalized(block['text'])]
        anchors=[]
        for i,b in enumerate(blocks):
            if b['kind']!='heading':continue
            if native_membership and native_membership.get(i) and native_membership[i]!={key}:continue
            text=normalized(b['text']);m=re.match(r'^item\s*(\d+(?:\.\d+)?[a-z]?)(?=[\s.:\[]|$)',text,re.I)
            if not m or m[1].replace('.','').lower()!=str(item).replace('.','').lower():continue
            if not whole.startswith(text):continue
            choices=candidates(b)
            if len(choices)==1:anchors.append((i,choices[0]))
        if len(anchors)!=1:continue
        start,_=anchors[0]
        end=next((j for j in range(start+1,len(blocks)) if blocks[j]['kind']=='heading'),len(blocks))
        matched=[];texts=[];previous_end=-1
        for i in range(start,end):
            b=blocks[i]
            if not normalized(b['text']):continue
            if native_membership and native_membership.get(i) and native_membership[i]!={key}:break
            if b['kind']=='table':break
            choices=candidates(b)
            if len(choices)!=1:break
            sid=choices[0];left,right=spans[sid]
            if left<=previous_end:break
            previous_end=right;matched.append(dict(block=i,source_id=sid));texts.append(b['text'])
        else:
            if normalized(' '.join(texts))==whole:
                proposals.append(dict(section=key,bindings=matched,basis='complete_item_sequence_in_unique_original_toc_range'))
    owners=defaultdict(set)
    for p in proposals:
        for b in p['bindings']:owners[b['block']].add(p['section'])
    return [p for p in proposals if all(len(owners[b['block']])==1 for b in p['bindings'])]
