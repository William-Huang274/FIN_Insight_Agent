"""Reconcile chapter roles from frozen parser artifacts, without re-parsing.

This is a separately versioned stage: every output binds the exact parser
artifact. It repairs proven inline heading fragments and one-row SEC heading
containers, without editing physical tables or inventing original positions.
"""
import argparse
from collections import Counter,defaultdict
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from source_structure_contract import normalized,reconcile_chapters,PART,ITEM
from document_structure_audit import outline
from retrieval.narrative_chunks import sentence_groups


def join_heading_fragments(blocks,sources):
    candidates=defaultdict(list)
    for row in sources:
        if row.get('excluded_navigation') or row.get('table_id'):continue
        if row['role']=='heading' or row.get('heading_eligible'):
            text=row['text']
            if text:candidates[text[0]].append(row)
    result=[];repairs=[];i=0
    while i<len(blocks):
        first=blocks[i];text=normalized(first['text']);parent=first.get('native_parent_id');proofs=[]
        if first.get('native_role') in {'heading','text'} and parent and text:
            for row in candidates.get(text[0],[]):
                target=row['text']
                if target==text or not target.startswith(text):continue
                current=text
                for end in range(i+1,min(i+16,len(blocks))):
                    b=blocks[end]
                    if b.get('native_parent_id')!=parent or b.get('native_role') not in {'heading','text'}:break
                    suffix=normalized(b['text'])
                    options={normalized(current+suffix),normalized(current+' '+suffix)}
                    options={v for v in options if target.startswith(v)}
                    if len(options)!=1:break
                    current=options.pop()
                    if current==target:
                        if any(v.get('native_role')=='heading' for v in blocks[i:end+1]):proofs.append((end,row))
                        break
        if len(proofs)==1:
            end,row=proofs[0]
            # A fragment may start as text and end as a native heading. Copying
            # only the first fragment silently discards the parser's level.
            native_levels=sorted({b['level'] for b in blocks[i:end+1]
                                  if b.get('kind')=='heading' and type(b.get('level')) is int
                                  and b['level']>0})
            original_level=row.get('level')
            resolved_level=(original_level if type(original_level) is int and original_level>0
                            else native_levels[0] if len(native_levels)==1 else None)
            receipt={'basis':'complete_original_heading_shared_native_parent',
                     'input_blocks':list(range(i,end+1)),'native_parent_id':parent,'source_container_id':row['id'],
                     'native_heading_levels':native_levels,'restored_level':resolved_level,
                     'level_basis':'explicit_original_level' if type(original_level) is int and original_level>0
                     else 'consistent_native_heading_level' if len(native_levels)==1 else 'unresolved'}
            merged={**first,'kind':'heading','text':row['text'],'source_container_id':row['id'],
                    'level':resolved_level,
                    'source_parent_id':row['parent_id'],'source_role':row['role'],
                    'source_container_candidates':[row['id']],'source_location_status':'unique_complete_container',
                    'heading_basis':receipt['basis'],'source_font_size_pt':row.get('font_size_pt'),
                    'stage_input_blocks':list(range(i,end+1)),'heading_restoration':receipt}
            result.append(merged);repairs.append(receipt);i=end+1
        else:
            result.append({**first,'stage_input_blocks':[i]});i+=1
    return result,repairs


def compact_title(text):
    return ''.join(c.casefold() for c in text if c.isalnum())


def has_native_signature_section(sections):
    identifier=re.compile(r'^(?:part_[ivx]+_)?signatures?$',re.I)
    title=re.compile(r'^(?:Part\s+[IVX]+\s*[-–:]\s*)?Signatures?$',re.I)
    return any(identifier.fullmatch(str(key)) or identifier.fullmatch(s.get('title','').strip())
               or title.fullmatch(s.get('title','').strip()) for key,s in sections.items())


def signature_attestation(blocks, index, sources):
    """Use the next complete original paragraph, never remote matching text."""
    for following in blocks[index+1:]:
        text=normalized(following['text'])
        if not text:continue
        source=sources.get(following.get('source_container_id'))
        if (following['kind']!='text' or not source
                or following.get('source_location_status')!='unique_complete_container'
                or text!=source['text'] or source.get('excluded_navigation') or source.get('table_id')):
            return None
        if (re.match(r'^Pursuant to the requirements of\b',text,re.I)
                and re.search(r'\bSecurities Exchange Act of 1934\b',text,re.I)
                and re.search(r'\bregistrant\b',text,re.I)
                and re.search(r'\bcaused this report to be signed\b',text,re.I)
                and re.search(r'\bduly authorized\b',text,re.I)):
            return source['id']
        return None
    return None


def table_heading(block,source):
    if not source or source.get('internal_link_only') or source.get('excluded_navigation'):return None
    rows=[]
    for key in ('headers','rows','footer'):
        for row in block.get(key,[]):
            cells=[normalized(c['text']) for c in row if normalized(c['text'])]
            if cells:rows.append(cells)
    # A TOC/exhibit/financial table is not a document heading just because one
    # cell starts with Item. Only a complete, single nonempty heading row qualifies.
    if len(rows)!=1 or len(rows[0])>3 or any(
            re.search(r'\d',c) and re.fullmatch(r'[\s$€£¥()+−–—,.\d%\-]+',c)
            for c in rows[0]):return None
    text=' '.join(rows[0])
    if len(text)>240 or not (PART.match(text) or ITEM.match(text)):return None
    if re.search(r'\b(?:PART\s+[IVX]+|ITEM\s+\d)',text[5:],re.I):return None
    if compact_title(text)!=compact_title(source['text']):return None
    return text


def refine(document):
    d=dict(document)
    if not d.get('blocks'):return d
    sources=d.get('source_containers',[]);by_id={r['id']:r for r in sources}
    blocks,repairs=join_heading_fragments(d['blocks'],sources)
    sec=d['route']=='edgartools'
    native_titles=[compact_title(s['title']) for s in d.get('parser_sections',{}).values()
                   if re.match(r'^Item\s+\d',s.get('title',''),re.I)]
    native_signatures=has_native_signature_section(d.get('parser_sections',{}))
    multi_item=re.compile(r'^Items?\s+\d+[A-Z]?(?:\.\d+)?(?:\s*(?:,|&|and)\s*\d+[A-Z]?(?:\.\d+)?)+\.?$',re.I)
    repeats=Counter(normalized(b['text']) for b in blocks if b['kind']=='heading')
    changes=[]
    for i,b in enumerate(blocks):
        for key in ('chapter_ids','chapter_blocks','chapter_occurrence_of','embedded_chapter_ids',
                    'sec_section_boundary','sec_section_boundary_basis'):
            b.pop(key,None)
        if 'parser_level' in b:b['level']=b.pop('parser_level')
        source=by_id.get(b.get('source_container_id'))
        if not sec:continue
        if (b['kind']=='heading' and source
                and not source.get('excluded_navigation') and not source.get('table_id')
                and b.get('source_location_status')=='unique_complete_container'
                and re.fullmatch(r'SIGNATURES?', normalized(b['text']), re.I)
                and normalized(b['text'])==source['text']):
            attestation=signature_attestation(blocks,i,by_id) if not native_signatures else None
            if native_signatures or attestation:
                basis=('native_signature_section_and_complete_original_container' if native_signatures
                       else 'complete_original_signature_heading_and_attestation')
                b.update(sec_section_boundary='signatures',sec_section_boundary_basis=basis)
                changes.append({'block':i,'basis':basis,'source_container_id':source['id'],
                                'attestation_source_container_id':attestation})
        if b['kind']=='heading' and multi_item.fullmatch(normalized(b['text'])) and repeats[normalized(b['text'])]>1:
            b.update(heading_usage='navigation_reference',heading_reference_role='repeated_multi_item_running_label')
            changes.append({'block':i,'basis':'repeated_multi_item_running_label'})
        if b['kind']=='table':
            title=table_heading(b,source)
            if title:
                b['structural_heading']=title;b['source_table_role']='section_heading_container'
                changes.append({'block':i,'basis':'complete_single_row_sec_heading','source_container_id':source['id']})
        elif b['kind']!='heading' and source and not source.get('internal_link_only'):
            text=normalized(b['text']);key=compact_title(text)
            supported=any(len(t)>14 and key.startswith(t) for t in native_titles)
            formal_bold=source.get('role')=='styled_heading_candidate' and not source.get('table_id')
            if (ITEM.match(text) or PART.match(text)) and len(text)<=240 and (supported or formal_bold):
                b.update(kind='heading',level=1,heading_basis='complete_bold_sec_label_container' if formal_bold else 'complete_container_and_native_section_title')
                changes.append({'block':i,'basis':b['heading_basis'],'source_container_id':source['id']})
    views=[]
    for b in blocks:
        v=dict(b)
        if b.get('structural_heading'):
            v.update(kind='heading',text=b['structural_heading'],level=1,heading_basis='complete_single_row_sec_heading')
        views.append(v)
    chapters=reconcile_chapters(views,sec,sources)
    for node in chapters:
        if node['basis']!='sec_part_item_label':continue
        occurrences=[(i,views[i]) for i in node['occurrence_blocks']]
        node['label_occurrences']=[{'block':i,'text':v['text']} for i,v in occurrences]
        for i,v in occurrences:
            label=normalized(v['text']);match=PART.match(label) or ITEM.match(label)
            if multi_item.fullmatch(label):continue
            if match and label[match.end():].strip(' .:') and v.get('source_container_id'):
                node.update(title=label,representative_block=i,source_container_id=v['source_container_id'])
                break
    for b,v in zip(blocks,views):
        for key in ('chapter_ids','chapter_blocks','chapter_occurrence_of','embedded_chapter_ids','level','parser_level'):
            if key in v:b[key]=v[key]
    headings,issues=outline(views)
    chapter_at={n['block']:n for n in chapters if not n.get('embedded_in_table')}
    for heading in headings:
        if heading['block'] in chapter_at:
            heading['title']=chapter_at[heading['block']]['title']
    d['issues']=[r for r in d.get('issues',[]) if r['kind'] not in {
        'heading_level_unknown','heading_level_jump','short_heading_requires_review','oversize_complete_sentence'}]+issues
    chunks=[]
    for i,b in enumerate(blocks):
        if b['kind']=='heading':continue
        common={'block':i,'heading_path':b.get('chapter_blocks',[]),'chapter_ids':b.get('chapter_ids',[]),
                'source_container_id':b.get('source_container_id')}
        if b['kind']=='table':
            chunks.append({**common,'kind':'table','representation':'section_heading_layout_not_data_table' if b.get('structural_heading') else 'original_table_cells_not_numeric_SQL_replacement'})
        else:
            for start,end,text in sentence_groups(b['text']):
                chunks.append({**common,'kind':'prose','start':start,'end':end})
                if len(text.encode())>6000:d['issues'].append({'kind':'oversize_complete_sentence','block':i,'start':start,'end':end})
    d.update(blocks=blocks,outline=headings,chapter_tree=chapters,pre_chunks=chunks,
             chapter_refinements={'joined_heading_containers':repairs,'role_changes':changes})
    return d


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    for sub in ('documents','receipts'):(a.output/sub).mkdir(exist_ok=True)
    identity={'parser_stage':json.loads((a.input/'execution-identity.json').read_bytes()),
              'refinement_code_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
              'dependencies':{name:sha256((ROOT/name).read_bytes()).hexdigest() for name in [
                  'scripts/engineering/source_structure_contract.py','scripts/engineering/document_structure_audit.py',
                  'src/retrieval/narrative_chunks.py','src/retrieval/object_view_compiler_v2.py']},
              'validator_sha256':sha256(Path(__file__).with_name('validate_source_structure_audit.py').read_bytes()).hexdigest()}
    stamp=a.output/'execution-identity.json'
    if stamp.exists() and json.loads(stamp.read_bytes())!=identity:raise ValueError('refinement_identity_changed')
    stamp.write_text(json.dumps(identity,ensure_ascii=False),encoding='utf8')
    from validate_source_structure_audit import validate
    totals=Counter()
    for path in sorted((a.input/'receipts').glob('*.json')):
        receipt=json.loads(path.read_bytes())
        if receipt['status']!='inspected':raise ValueError('parser_stage_failed')
        target=a.output/'receipts'/path.name
        raw=(a.input/'documents'/(receipt['id']+'.json.gz')).read_bytes()
        if sha256(raw).hexdigest()!=receipt['artifact_sha256']:raise ValueError('input_artifact_changed')
        if target.exists():
            saved=json.loads(target.read_bytes());artifact=a.output/'documents'/(receipt['id']+'.json.gz')
            if saved['parent_artifact_sha256']!=receipt['artifact_sha256'] or sha256(artifact.read_bytes()).hexdigest()!=saved['artifact_sha256']:
                raise ValueError('refinement_resume_artifact_changed')
            totals.update(saved['chapter_refinements']);totals['documents']+=1
            continue
        started=time.perf_counter();d=refine(json.loads(gzip.decompress(raw)));errors=validate(d)
        if errors:raise ValueError(json.dumps({'id':receipt['id'],'errors':errors}))
        output=a.output/'documents'/(receipt['id']+'.json.gz')
        with gzip.open(output,'wt',encoding='utf8',compresslevel=3) as f:json.dump(d,f,ensure_ascii=False)
        row={**receipt,'parent_artifact_sha256':receipt['artifact_sha256'],
             'artifact_sha256':sha256(output.read_bytes()).hexdigest(),'artifact_bytes':output.stat().st_size,
             'headings':len(d['outline']),'blocks':len(d['blocks']),'pre_chunks':len(d['pre_chunks']),
             'issues':dict(Counter(r['kind'] for r in d['issues'])),
             'chapter_refinements':{k:len(v) for k,v in d.get('chapter_refinements',{}).items()},
             'refinement_elapsed_seconds':time.perf_counter()-started}
        target.write_text(json.dumps(row,ensure_ascii=False),encoding='utf8')
        totals.update(row['chapter_refinements']);totals['documents']+=1
    (a.output/'refinement-summary.json').write_text(json.dumps(dict(totals),ensure_ascii=False),encoding='utf8')
    print(json.dumps(dict(totals)))


if __name__=='__main__':main()
