"""Resolve duplicate TOC identities with native endpoints and original Items.

An alias has no independent native section, identical original endpoints, and
one extra letter beyond the native identity. Actual Item text must agree with
the canonical identity; genuine alphabetic Items are never folded by spelling.
"""
from collections import defaultdict
from copy import deepcopy
import re


ITEM=re.compile(r'^item\s*(\d+(?:\.\d+)?[a-z]?)(?=[\s.:\[—–-]|$)',re.I)


def item_number(text):
    m=ITEM.match(' '.join(text.split()))
    return m[1].replace('.','').casefold() if m else None


def prove(native,sources,ranges,spans):
    sections=native.get('sections',{});boundaries=native.get('toc_boundaries',{})
    grouped=defaultdict(list)
    for key,bounds in ranges.items():grouped[tuple(bounds)].append(key)
    proofs=[]
    for bounds,keys in sorted(grouped.items()):
        actual=sorted(k for k in keys if k in sections)
        absent=sorted(k for k in keys if k not in sections)
        if len(actual)!=1 or not absent:continue
        canonical=actual[0];expected=str(sections[canonical]['fields'].get('item') or '').replace('.','').casefold()
        if not expected:continue
        canonical_boundary=boundaries[canonical]
        def endpoint_identity(b):
            return (b.get('fields',{}).get('anchor_id'),b.get('fields',{}).get('end_element_id'),
                    b.get('element_paths',{}))
        if not (canonical_boundary.get('fields',{}).get('anchor_id') or canonical_boundary.get('element_paths',{}).get('start_element')):continue
        candidates=[];all_original_items=set()
        for source in sources:
            span=spans.get(source['id'])
            if (not span or not bounds[0]<=span[0] or not span[1]<bounds[1]
                or source.get('excluded_navigation') or source.get('internal_link_only')):continue
            number=item_number(source['text'])
            if number:all_original_items.add(number)
            if (source.get('table_id') or source.get('role') in {'table','container'}
                or len(source['text'])>240):continue
            if number:candidates.append((span[0],source['id'],number,source['text']))
        candidates.sort()
        if not candidates or candidates[0][2]!=expected:continue
        for alias in absent:
            if (not alias.startswith(canonical) or len(alias)!=len(canonical)+1 or not alias[-1].isalpha()
                or endpoint_identity(boundaries[alias])!=endpoint_identity(canonical_boundary)):continue
            # If the supposedly extra letter exists as an actual Item in this
            # range, its identity is unresolved, never an approved alias.
            if expected+alias[-1].casefold() in all_original_items:continue
            proofs.append(dict(alias=alias,canonical=canonical,original_range=list(bounds),
                original_heading_source_id=candidates[0][1],original_heading=candidates[0][3],
                original_item=expected,canonical_boundary=deepcopy(canonical_boundary),alias_boundary=deepcopy(boundaries[alias]),
                basis='same_original_endpoints_native_identity_and_body_item',
                alias_has_independent_native_section=False))
    return proofs


def effective_ranges(ranges,proofs):
    aliases={p['alias'] for p in proofs}
    return {key:value for key,value in ranges.items() if key not in aliases}


def repair(document,capture):
    from source_heading_units import geometry
    if document['source_sha256']!=capture['source_sha256']:raise ValueError('toc_source_identity_changed')
    raw_ranges,spans=geometry(capture['native'],document.get('source_containers',[]))
    proofs=prove(capture['native'],document.get('source_containers',[]),raw_ranges,spans)
    if not proofs:return document,[]
    d=deepcopy(document);aliases={p['alias'] for p in proofs}
    original=d.get('native_toc_raw_shared_ranges',d.get('shared_native_range_groups',[]))
    d['native_toc_raw_shared_ranges']=deepcopy(original)
    active=[]
    for group in original:
        keys=[k for k in group['sections'] if k not in aliases]
        if len(keys)>1:active.append(dict(group,sections=keys))
    d['native_toc_identity_aliases']=proofs
    d['shared_native_range_groups']=active
    return d,proofs


def verify(document,capture):
    proofs=document.get('native_toc_identity_aliases',[])
    if not proofs:return
    previous=deepcopy(document)
    previous['shared_native_range_groups']=previous['native_toc_raw_shared_ranges']
    updated,fresh=repair(previous,capture)
    if proofs!=fresh or document['shared_native_range_groups']!=updated['shared_native_range_groups']:
        raise ValueError('toc_identity_alias_proof_not_reproducible')
