"""Link section titles using original TOC targets and adjacent body evidence.

The native section key remains an identity. Display text comes from complete
original containers. No body range is expanded by this metadata repair.
"""
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import re

from lxml import etree, html
from document_structure_repairs import attestation
from source_structure_contract import normalized, _all_bold
from source_heading_units import number, tokens


def original_geometry(raw):
    try:
        raw.decode('utf-8-sig');dom=html.fromstring(raw,parser=html.HTMLParser(encoding='utf-8',no_network=True))
    except UnicodeDecodeError:dom=html.fromstring(raw,parser=html.HTMLParser(no_network=True))
    tree=dom.getroottree();paths={};anchors=defaultdict(list);links=defaultdict(list)
    spans={};pieces=[];cursor=0
    for event,e in etree.iterwalk(dom,events=('start','end','comment','pi')):
        if event in {'comment','pi'}:
            # Comments have no visible body, but their tail may contain real
            # text. Keep that tail in adjacency proofs.
            if e.tail:pieces.append(e.tail);cursor+=len(e.tail)
        elif event=='start':
            paths[tree.getpath(e)]=e
            for a in set(filter(None,(e.get('id'),e.get('name')))):anchors[a].append(e)
            if e.tag=='a' and (e.get('href') or '').startswith('#'):
                label=normalized(''.join(e.itertext()))
                if label:links[e.get('href')[1:]].append(label)
            spans[e]=[cursor,None]
            if e.text:pieces.append(e.text);cursor+=len(e.text)
        else:
            spans[e][1]=cursor
            if e.tail:pieces.append(e.tail);cursor+=len(e.tail)
    text=''.join(pieces)
    return tree,paths,spans,text,anchors,links


def proposals(document,raw):
    if sha256(raw).hexdigest()!=document['source_sha256']:raise ValueError('original_changed')
    tree,paths,spans,text,anchors,links=original_geometry(raw)
    blocks=document['blocks'];sources={s['id']:s for s in document.get('source_containers',[])}
    by_section=defaultdict(list)
    for i,b in enumerate(blocks):
        if normalized(b.get('text','')):
            candidates=b.get('native_section_binding',{}).get('candidates',[])
            if len(candidates)==1:by_section[candidates[0]].append(i)
    def locations(i):
        b=blocks[i]
        if b['kind'] not in {'text','heading'}:return []
        ids=[b['source_container_id']] if b.get('source_container_id') else b.get('source_container_candidates',[])
        out=[]
        for sid in ids:
            s=sources.get(sid,{});e=paths.get(sid.split(':',1)[-1])
            if not s or e is None or s.get('table_id') or s.get('excluded_navigation') or s.get('internal_link_only'):continue
            if e.xpath('ancestor-or-self::table | ancestor-or-self::nav | ancestor-or-self::script'):continue
            if normalized(''.join(e.itertext()))!=normalized(b['text']):continue
            out.append((sid,e))
        return out
    def incoming(e):
        """The anchor contains the first title text, never unrelated earlier text."""
        targets=[]
        for a in (e,*e.iterancestors()):
            if spans[a][0]!=spans[e][0] and normalized(text[spans[a][0]:spans[e][0]]):break
            targets.extend((k,a) for k in set(filter(None,(a.get('id'),a.get('name')))))
        for a in e.iterdescendants():
            if a not in spans:continue
            if not normalized(text[spans[e][0]:spans[a][0]]):
                targets.extend((k,a) for k in set(filter(None,(a.get('id'),a.get('name')))))
        out=[]
        for key,anchor in targets:
            if len(anchors[key])==1:
                out.extend(dict(anchor=key,label=label) for label in set(links.get(key,[])))
        return out
    proved=[];findings=[]
    for node in document['chapter_tree']:
        if node.get('title_binding',{}).get('status') not in {'heading_not_bound','ambiguous_heading'}:continue
        key=node.get('native_section_key');members=by_section.get(key,[])
        if not members:continue
        first=members[0];previous=next((j for j in range(first-1,-1,-1) if normalized(blocks[j]['text'])),None)
        starts=[first]+([previous] if previous is not None else [])
        expected=str(node.get('native_section',{}).get('item') or '').replace('.','').casefold()
        signature='signature' in key.casefold();matches=[]
        for start in starts:
            for sid,e in locations(start):
                title=normalized(blocks[start]['text'])
                if not title or len(title)>500:continue
                body_locs=locations(first)
                if start!=first:
                    body_locs=[(s,b) for s,b in body_locs if spans[e][1]<=spans[b][0]
                        and not normalized(text[spans[e][1]:spans[b][0]])]
                    if len(body_locs)!=1:continue
                actual_links=incoming(e)
                direct_links=[a for a in actual_links if tokens(a['label'].casefold())==tokens(title.casefold())]
                style=e.tag in {'h1','h2','h3','h4','h5','h6'} or _all_bold(e)
                indices=[start];source_ids=[sid];labels=[title];basis=None;anchor_proof=None
                if expected and number(title)==expected and (style or direct_links):
                    basis='matching_item_title_and_original_body_position'
                elif signature and re.fullmatch(r'signatures?',title,re.I):
                    after=next((j for j in range(start+1,len(blocks)) if normalized(blocks[j]['text'])),None)
                    if after is not None and after in members and attestation(blocks[after]['text']) and len(locations(after))==1:
                        ae=locations(after)[0][1]
                        if spans[e][1]<=spans[ae][0] and not normalized(text[spans[e][1]:spans[ae][0]]):
                            basis='signature_title_and_adjacent_original_attestation'
                elif not expected and not signature:
                    # A TOC label may span multiple complete title containers.
                    # Every fragment must be adjacent in original text order.
                    for link in actual_links:
                        target=tokens(link['label'].casefold());current=tokens(title.casefold())
                        if not current or target[:len(current)]!=current:continue
                        ii=[start];ss=[sid];tt=[title];last=e
                        while current!=target:
                            nxt=next((j for j in range(ii[-1]+1,len(blocks)) if normalized(blocks[j]['text'])),None)
                            if nxt is None or nxt not in members:break
                            choices=[(s,c) for s,c in locations(nxt) if spans[last][1]<=spans[c][0]
                                     and not normalized(text[spans[last][1]:spans[c][0]])]
                            if len(choices)!=1:break
                            ns,ne=choices[0];nt=normalized(blocks[nxt]['text']);candidate=tokens((' '.join(tt+[nt])).casefold())
                            if len(candidate)<=len(current) or target[:len(candidate)]!=candidate:break
                            ii.append(nxt);ss.append(ns);tt.append(nt);current=candidate;last=ne
                        if current==target:
                            indices=ii;source_ids=ss;labels=tt;basis='original_toc_target_and_complete_title_containers';anchor_proof=link;break
                if basis:
                    matches.append(dict(chapter_id=node['id'],section=key,blocks=indices,source_ids=source_ids,
                        title=' '.join(labels),basis=basis,first_native_block=first,
                        original_spans=[spans[paths[s.split(':',1)[-1]]] for s in source_ids],toc=anchor_proof))
        # Avoid both duplicate anchor labels and competing source locations.
        unique={repr((m['blocks'],m['source_ids'],m['title'])):m for m in matches}
        findings.append(dict(chapter_id=node['id'],section=key,first_native_block=first,
                             candidates=len(unique),status='proved' if len(unique)==1 else 'ambiguous' if unique else 'not_proved'))
        if len(unique)==1:proved.extend(unique.values())
    owners=defaultdict(set)
    for p in proved:
        for i in p['blocks']:owners[i].add(p['chapter_id'])
    return [p for p in proved if all(len(owners[i])==1 for i in p['blocks'])],findings


def repair(document,raw):
    proofs,findings=proposals(document,raw)
    if not proofs:return document,[],findings
    d=deepcopy(document);nodes={n['id']:n for n in d['chapter_tree']}
    for p in proofs:
        n=nodes[p['chapter_id']];old=n['title']
        n['prior_source_title_binding']=dict(title=n['title'],title_binding=n['title_binding'])
        n.update(title=p['title'],title_binding=dict(status='bound_source_title_link',**p))
        for o in d['outline']:
            if o['block']==n['block'] and o['title']==old:o['title']=p['title']
    d.setdefault('source_section_title_links',[]).extend(proofs)
    return d,proofs,findings


def verify(document,raw):
    proofs=document.get('source_section_title_links',[])
    if not proofs:return
    prior=deepcopy(document);nodes={n['id']:n for n in prior['chapter_tree']}
    for p in proofs:
        n=nodes[p['chapter_id']]
        if n['title']!=p['title'] or n['title_binding']!=dict(status='bound_source_title_link',**p):
            raise ValueError('source_title_link_not_consumed')
        n.update(n['prior_source_title_binding'])
    if proposals(prior,raw)[0]!=proofs:raise ValueError('source_title_link_not_reproducible')
