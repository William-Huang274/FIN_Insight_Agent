"""Complete-container lexical equivalence and original visibility alignment.

Tokens preserve case, words, numbers, signs, units and punctuation. Only spaces
between otherwise identical tokens may differ. Ambiguous visible occurrences
remain alternatives; no nearest or first occurrence is selected.
"""
from collections import defaultdict
from hashlib import sha256
import json

from source_heading_units import tokens
from source_visibility import container_evidence


def token_digest(text):
    return sha256(json.dumps(tokens(text),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def repair(document,raw):
    if sha256(raw).hexdigest()!=document['source_sha256']:raise ValueError('source_identity_changed')
    evidence=container_evidence(raw,[s['id'].split(':',1)[-1] for s in document.get('source_containers',[]) if s.get('text')])
    source_updates={};index=defaultdict(list);source_by_id={};visibility_records={}
    for s in document.get('source_containers',[]):
        item=s;original=evidence.get(s['id'].split(':',1)[-1]);proof=original.get('visibility') if original else None
        if proof:
            purpose=s.get('source_display_purpose')
            excluded=purpose['within_navigation'] if purpose and purpose['candidate_policy']=='body_content' else True
            item=dict(s,source_visibility=dict(status='hidden_at_capture' if purpose else 'non_display_metadata',**proof),excluded_navigation=excluded)
            if item!=s:source_updates[s['id']]=item
            visibility_records[s['id']]=dict(source_id=s['id'],visibility=item['source_visibility'])
        source_by_id[s['id']]=item
        if (original and not original['visibility'] and original['text']==item.get('text') and item.get('text')
            and not item.get('excluded_navigation') and item.get('role') not in {'table','container'}):
            index[token_digest(item['text'])].append(item)
    changes=[];alternatives=[]
    for i,b in enumerate(document['blocks']):
        if b['kind']=='table' or not b.get('text','').strip():continue
        status=b.get('source_location_status')
        old_source=source_by_id.get(b.get('source_container_id'),{})
        if status not in {'unresolved','ambiguous'} and not old_source.get('source_visibility'):continue
        key=token_digest(b['text']);matches=[s for s in index.get(key,[]) if tokens(s['text'])==tokens(b['text'])]
        if len(matches)>1:
            alternatives.append(dict(block=i,source_ids=[s['id'] for s in matches],token_sha256=key,
                basis='all_complete_visible_token_equivalent_occurrences',unique_position=False,numeric_authority=False))
        if len(matches)!=1:continue
        s=matches[0]
        changes.append(dict(block=i,source_container_id=s['id'],token_sha256=key,source_text_sha256=s['text_sha256'],
            previous_status=status,previous_candidates=b.get('source_container_candidates',[]),
            previous_source_container_id=b.get('source_container_id'),
            basis='complete_original_token_sequence_unique_visible_container'))
    visibility_list=[visibility_records[sid] for sid in sorted(visibility_records)]
    if (not source_updates and not changes and document.get('source_visibility_repairs',[])==visibility_list
        and document.get('source_equivalent_occurrence_proofs',[])==alternatives):return document,[]
    d=dict(document);d['source_containers']=[source_updates.get(s['id'],s) for s in document.get('source_containers',[])]
    d['blocks']=list(document['blocks'])
    for p in changes:
        b=dict(d['blocks'][p['block']]);d['blocks'][p['block']]=b;s=source_by_id[p['source_container_id']]
        b.update(source_container_id=s['id'],source_container_candidates=[s['id']],source_location_status='unique_complete_container',
                 source_alignment_basis=p['basis'],source_alignment_proof=p)
        # Preserve existing role, chapter ownership, text and physical identity.
    for p in alternatives:
        b=dict(d['blocks'][p['block']]);d['blocks'][p['block']]=b
        b.update(source_container_id=None,source_container_candidates=p['source_ids'],source_location_status='ambiguous',
                 source_alignment_alternatives=p)
    located_blocks={p['block'] for p in changes+alternatives}
    d['pre_chunks']=[dict(c,source_container_id=d['blocks'][c['block']].get('source_container_id'))
                     if c['block'] in located_blocks else c for c in document['pre_chunks']]
    d['source_location_alignment_repairs']=document.get('source_location_alignment_repairs',[])+changes
    if visibility_list:d['source_visibility_repairs']=visibility_list
    if alternatives:d['source_equivalent_occurrence_proofs']=alternatives
    return d,changes


def verify(document,raw):
    if sha256(raw).hexdigest()!=document['source_sha256']:raise ValueError('source_identity_changed')
    sources={s['id']:s for s in document.get('source_containers',[])}
    if document.get('source_display_purpose_repairs') or any(s.get('source_display_purpose') for s in sources.values()):
        from source_display_purpose import verify as verify_display
        verify_display(document,raw)
    evidence=container_evidence(raw,[s['id'].split(':',1)[-1] for s in sources.values() if s.get('text')])
    unique=defaultdict(list)
    for s in sources.values():
        original=evidence.get(s['id'].split(':',1)[-1])
        if (original and original['text']==s.get('text') and not original['visibility']
            and not s.get('excluded_navigation') and s.get('role') not in {'table','container'}):
            unique[token_digest(original['text'])].append(s['id'])
    for p in document.get('source_visibility_repairs',[]):
        s=sources[p['source_id']];fresh=evidence.get(s['id'].split(':',1)[-1],{}).get('visibility')
        purpose=s.get('source_display_purpose')
        expected=dict(status='hidden_at_capture' if purpose else 'non_display_metadata',**(fresh or {}))
        excluded=purpose['within_navigation'] if purpose and purpose['candidate_policy']=='body_content' else True
        if s.get('source_visibility')!=expected or s.get('excluded_navigation')!=excluded:
            raise ValueError('source_visibility_not_reproducible')
    for p in document.get('source_location_alignment_repairs',[]):
        b=document['blocks'][p['block']];s=sources[p['source_container_id']]
        if (b.get('source_container_id')!=s['id'] or b.get('source_location_status')!='unique_complete_container'
            or s.get('excluded_navigation') or evidence.get(s['id'].split(':',1)[-1],{}).get('visibility')
            or token_digest(b['text'])!=p['token_sha256'] or token_digest(s['text'])!=p['token_sha256']
            or tokens(b['text'])!=tokens(s['text']) or s['text_sha256']!=p['source_text_sha256']
            or unique[p['token_sha256']]!=[s['id']]):
            raise ValueError('source_token_alignment_not_reproducible')
    for p in document.get('source_equivalent_occurrence_proofs',[]):
        b=document['blocks'][p['block']]
        if (p['unique_position'] or p['numeric_authority'] or b.get('source_container_id')
            or b.get('source_location_status')!='ambiguous' or len(p['source_ids'])<2
            or p['source_ids']!=unique[p['token_sha256']] or b.get('source_container_candidates')!=p['source_ids']
            or token_digest(b['text'])!=p['token_sha256']):
            raise ValueError('original_occurrence_alternatives_not_reproducible')
    proof_blocks={p['block'] for p in document.get('source_location_alignment_repairs',[])+document.get('source_equivalent_occurrence_proofs',[])}
    for c in document['pre_chunks']:
        if c['block'] in proof_blocks and c.get('source_container_id')!=document['blocks'][c['block']].get('source_container_id'):
            raise ValueError('source_location_not_consumed_by_prechunk')
