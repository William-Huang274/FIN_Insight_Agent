"""Rebind case-equivalent headings only after every occurrence matches raw DOM."""
from copy import deepcopy
from hashlib import sha256
from lxml import html
from native_document_adaptation import section_display_title
from source_structure_contract import normalized


def repair(document, raw):
    if sha256(raw).hexdigest()!=document['source_sha256']:raise ValueError('original_changed')
    try:
        raw.decode('utf-8-sig');dom=html.fromstring(raw,parser=html.HTMLParser(encoding='utf-8'))
    except UnicodeDecodeError:dom=html.fromstring(raw)
    tree=dom.getroottree();paths={tree.getpath(e):e for e in dom.iter()}
    sources={s['id']:s for s in document.get('source_containers',[])}
    proposals=[]
    for n in document['chapter_tree']:
        if n.get('title_binding',{}).get('status') not in {'heading_not_bound','ambiguous_heading'}:continue
        key=n.get('native_section_key');fields=n.get('native_section',{})
        indices=[i for i,b in enumerate(document['blocks']) if b.get('native_section_binding',{}).get('candidates')==[key]]
        if not indices:continue
        label,index,binding=section_display_title(key,fields,indices,document['blocks'])
        if binding['status']!='bound_heading':continue
        occurrences=[];invalid=False
        for i in indices:
            b=document['blocks'][i]
            if b['kind']!='heading' or normalized(b['text']).casefold()!=normalized(label).casefold():continue
            sid=b.get('source_container_id');source=sources.get(sid,{});element=paths.get((sid or '').split(':',1)[-1])
            if (b.get('source_location_status')!='unique_complete_container' or not source
                or source.get('table_id') or source.get('excluded_navigation') or source.get('internal_link_only')
                or element is None or normalized(''.join(element.itertext()))!=normalized(b['text'])):
                invalid=True;break
            occurrences.append(dict(block=i,source_container_id=sid,text=b['text']))
        if invalid or not occurrences or index not in [o['block'] for o in occurrences]:continue
        proposals.append(dict(chapter_id=n['id'],title=label,block=index,occurrences=occurrences,
            basis='case_equivalent_native_headings_verified_original_containers'))
    if not proposals:return document,[]
    d=deepcopy(document);nodes={n['id']:n for n in d['chapter_tree']}
    for p in proposals:
        n=nodes[p['chapter_id']];oldtitle=n['title']
        n['prior_equivalent_title_binding']=dict(title=n['title'],title_binding=n['title_binding'])
        n.update(title=p['title'],title_binding=dict(status='bound_case_equivalent_heading',**p))
        for o in d['outline']:
            if o['block']==n['block'] and o['title']==oldtitle:o['title']=p['title']
    d.setdefault('equivalent_section_title_repairs',[]).extend(proposals)
    return d,proposals


def verify(document,raw):
    proofs=document.get('equivalent_section_title_repairs',[])
    if not proofs:return
    prior=deepcopy(document);nodes={n['id']:n for n in prior['chapter_tree']}
    for p in proofs:
        n=nodes[p['chapter_id']]
        if n['title_binding']!=dict(status='bound_case_equivalent_heading',**p) or n['title']!=p['title']:
            raise ValueError('equivalent_title_not_consumed')
        n.update(n['prior_equivalent_title_binding'])
    if repair(prior,raw)[1]!=proofs:raise ValueError('equivalent_title_not_reproducible')
