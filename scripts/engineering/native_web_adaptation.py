"""Consume frozen Trafilatura XML as a candidate, retaining native provenance.

Native XML positions are NOT original HTML positions. Previous repaired FIN
artifacts remain separate and must not be overwritten by this candidate.
"""
import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path

from lxml import etree
from native_document_capture import read_capture
from native_document_adaptation import finish
from source_structure_contract import reconcile_chapters


BLOCK_TAGS = {'head', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'item', 'li', 'code', 'quote', 'table'}


def adapt_web(capture):
    native = capture['native']; document = native.get('document')
    if not document or not document.get('body'):
        raise ValueError('native_web_body_unavailable')
    body = document['body']['$xml']
    root = etree.fromstring(body.encode(), etree.XMLParser(resolve_entities=False, no_network=True))
    tree = root.getroottree(); blocks = []; nodes = []; issues = []
    def tag(e): return etree.QName(e).localname if isinstance(e.tag, str) else 'comment'
    for e in root.iter():
        nodes.append(dict(path=tree.getpath(e), tag=tag(e), attributes=dict(e.attrib),
                          parent_path=tree.getpath(e.getparent()) if e.getparent() is not None else None,
                          text=e.text, tail=e.tail))
    def emit(text, e, role='text', **extra):
        if not text: return
        blocks.append(dict(kind=role, text=text, native_xml_path=tree.getpath(e),
                           native_role=tag(e), native_attributes=dict(e.attrib),
                           original_location_status='not_mapped_from_native_xml', **extra))
    def walk(e):
        name = tag(e)
        if name == 'table':
            rows = []; headers = []
            for row in e.iter():
                if tag(row) not in ('row', 'tr'): continue
                if next((a for a in row.iterancestors() if tag(a) == 'table'), None) is not e: continue
                cells = []
                for cell in row:
                    if tag(cell) not in ('cell', 'td', 'th'): continue
                    cells.append(dict(text=''.join(cell.itertext()), is_header=tag(cell)=='th' or cell.get('role')=='head',
                                      rowspan=cell.get('rowspan', '1'), colspan=cell.get('colspan', '1'),
                                      native_attributes=dict(cell.attrib), native_xml_path=tree.getpath(cell)))
                if cells:
                    (headers if all(c['is_header'] for c in cells) else rows).append(cells)
            emit(''.join(e.itertext()), e, 'table', rows=rows, headers=headers, footer=[],
                 native_xml=etree.tostring(e, encoding='unicode', with_tail=False),
                 structure_gap='original_table_cells_and_scope_require_review')
            issues.append(dict(kind='original_table_cells_and_scope_require_review', native_xml_path=tree.getpath(e)))
            return
        if name in BLOCK_TAGS and not any(tag(d) in BLOCK_TAGS for d in e.iterdescendants()):
            text = ''.join(e.itertext())
            if name == 'head' or name in {'h1','h2','h3','h4','h5','h6'}:
                level_tag = e.get('rend', '') if name == 'head' else name
                level = int(level_tag[1:]) if level_tag in {'h1','h2','h3','h4','h5','h6'} else None
                emit(text, e, 'heading', level=level, heading_basis='native_web_explicit_heading')
                if level is None: issues.append(dict(kind='native_heading_level_unknown', native_xml_path=tree.getpath(e)))
            else:
                emit(text, e, candidate_role='code_candidate' if name == 'code' else None)
            return
        emit(e.text, e)
        for child in e:
            walk(child)
            emit(child.tail, child, native_text_slot='tail')
    walk(root)
    if ''.join(b['text'] for b in blocks) != ''.join(root.itertext()):
        raise ValueError('native_web_text_partition_not_conserved')
    chapters = reconcile_chapters(blocks)
    issues.append(dict(kind='page_purpose_and_original_body_coverage_require_review'))
    result = dict(route='trafilatura_native', source_sha256=capture['source_sha256'],
                  blocks=blocks, chapter_tree=chapters, source_containers=[], issues=issues,
                  native_xml_nodes=nodes, native_body_xml=body,
                  native_comments=document.get('commentsbody'),
                  native_metadata={k:v for k,v in document.items() if k not in ('body','commentsbody')},
                  native_text_partition_complete=True, original_content_coverage_verified=False,
                  page_purpose='unreviewed', document_title=dict(text=document.get('title'), status='metadata_only_not_verified_original_heading'))
    return finish(result)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--baseline-artifact', type=Path, required=True)
    p.add_argument('--baseline-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    a=p.parse_args()
    receipt=json.loads((a.capture/'receipt.json').read_bytes())
    native=read_capture(a.capture/'native.json.gz', expected_sha256=receipt['native_sha256'], expected_source_sha256=receipt['source_sha256'])
    if native['route']!='trafilatura': raise ValueError('wrong_native_route')
    if sha256(a.baseline_artifact.read_bytes()).hexdigest()!=a.baseline_sha256:
        raise ValueError('frozen_baseline_digest_mismatch')
    doc=adapt_web(native)
    from finalize_structure_prechunks import classify
    final=classify(doc)
    a.output.mkdir(parents=True, exist_ok=False)
    packed=gzip.compress(json.dumps(doc,ensure_ascii=False).encode(),mtime=0)
    (a.output/'document.json.gz').write_bytes(packed)
    (a.output/'prechunks.json.gz').write_bytes(gzip.compress(json.dumps(final,ensure_ascii=False).encode(),mtime=0))
    result=dict(source_sha256=native['source_sha256'], native_sha256=receipt['native_sha256'],
                parent_fin_path=str(a.baseline_artifact),parent_fin_sha256=a.baseline_sha256,
                implementation_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                artifact_sha256=sha256(packed).hexdigest(), blocks=len(doc['blocks']),chapters=len(doc['chapter_tree']),
                tables=sum(b['kind']=='table' for b in doc['blocks']), native_text_partition_complete=True,
                original_content_coverage_verified=False, quality_pass=False,published=False,provider_calls=0)
    (a.output/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':main()
