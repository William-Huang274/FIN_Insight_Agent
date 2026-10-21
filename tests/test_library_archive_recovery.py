from contextlib import closing
from copy import deepcopy
import json
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_library_source_bundle import database, vectors_for
from retrieval.library_archive_recovery import ArchiveRecoveryCatalog, create_receipt, recover_archive, configured_catalog
from retrieval.library_chunks import split_parent
from retrieval.library_source_bundle import build_source_bundle, compact_source_bundle, expand_source_bundle, text_digest, validate_bundle_text
from retrieval.library_vectors import digest
from scripts.data_retrieval.prepare_archive_recovery import prepare
from scripts.data_retrieval.prepare_library_source_bundles import prepare as prepare_bundles
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.project_source_captures import CaptureRequest, save_capture
from sec_agent.research_foundation.organization_source_projection import source_nodes


def fixture(root, pages=None):
    archives = root/'archives'; archives.mkdir()
    archive = archives/'original.html'
    archive.write_text('<html><nav>omit</nav><p>'+('收入 USD 12.5 million\n'*400)+'</p><table><tr><td>Final</td><td>42</td></tr></table></html>', encoding='utf8')
    from retrieval.library_archive_recovery import parse_archive
    pages = pages if pages is not None else parse_archive(archive.read_bytes(), '.html')
    (root/'published').mkdir()
    path=root/'published'/'library.sqlite'; sid=database(path,'placeholder')
    with closing(sqlite3.connect(path)) as db, db:
        db.row_factory=sqlite3.Row
        db.execute('UPDATE sources SET digest=?,metadata=?',(digest(archive),json.dumps({'archive':str(archive),'unit':'USD millions'})))
        for table in ('passages','retrieval_chunks','edges','edge_chunk_links','edge_chunk_coverage'):
            db.execute(f'DELETE FROM {table}')
        parents=[]
        for i, text in enumerate(pages,1):
            for lo in range(0,len(text),3500):
                body=text[lo:lo+3500]
                parents.append(dict(id=f'{sid}:P{i}:{lo}',source_id=sid,
                                    locator=f'HTML text chars {lo}-{lo+len(body)}',body=body,digest=text_digest(body)))
        db.executemany('INSERT INTO passages VALUES(:id,:source_id,:locator,:body,:digest)',parents)
        chunks=[c for p in parents for c in split_parent(p,'original')]
        db.executemany('INSERT INTO retrieval_chunks VALUES(:id,:source_id,:parent_id,:ordinal,:char_start,:char_end,:body,:digest,:locator,:context,:kind,:flags)',chunks)
        source=dict(db.execute('SELECT * FROM sources').fetchone())
    return path,sid,archive,source,parents


def load_bundle(path,sid,catalog):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        return build_source_bundle(db,sid,digest(path),catalog)


def test_archive_real_html_catalog_capture_vector_reuse_and_detached_readback(tmp_path,monkeypatch):
    path,sid,archive,source,parents=fixture(tmp_path)
    output=tmp_path/'receipts'
    manifest=prepare(path,[sid],[archive.parent],output)
    catalog=ArchiveRecoveryCatalog(output/'catalog.json',digest(output/'catalog.json'))
    bundle=load_bundle(path,sid,catalog)
    assert source['digest']!=text_digest(bundle['text'])
    assert bundle['source']==source and 'omit' not in bundle['text'] and 'Final | 42' in bundle['text']
    assert expand_source_bundle(compact_source_bundle(bundle))==bundle
    vectors_for(bundle,tmp_path/'vectors')
    result=prepare_bundles(path,tmp_path/'vectors',[sid],tmp_path/'export',catalog)
    assert result['status']=='verified' and result['sources'][0]['reused_vectors']==len(bundle['chunks'])
    from scripts.data_retrieval.audit_library_source_intake import audit
    inventory=audit(path,tmp_path/'inventory.json',tmp_path/'vectors','2026-09-23',catalog)
    assert inventory['intake_statuses']=={'parsed_text_recoverable':1}
    assert inventory['verified_vectors']==len(bundle['chunks']) and inventory['organization_time_eligible_sources']==1
    monkeypatch.setenv('FINSIGHT_LIBRARY_RECOVERY_CATALOG',str(output/'catalog.json'))
    monkeypatch.setenv('FINSIGHT_LIBRARY_RECOVERY_SHA256',digest(output/'catalog.json'))
    import sec_agent.research_foundation.research_library as lm
    monkeypatch.setattr(lm,'open_library',lambda _:SimpleNamespace(path=path,manifest={'sha256':digest(path)}))
    workspace=AssetWorkspace(tmp_path/'assets'); project=str(uuid4())
    workspace.library.save('alice',0,{'projects':[{'id':project,'name':'Original'}],'assignments':{},'pinned':[]})
    req=CaptureRequest(project_id=project,title='HTML original',selection={'kind':'library_source','document_id':sid,'snapshot':digest(path)})
    saved=save_capture(workspace,'alice',req,None,None,path)
    assert save_capture(workspace,'alice',req,None,None,path)['document_id']==saved['document_id']
    ref=workspace.catalog('alice',project)['items'][0]['versions'][0]['ref']
    archive.unlink(); (output/'catalog.json').unlink()
    assert workspace.read_source('alice',ref)['source_bundle']==bundle
    nodes=source_nodes(bundle,'ORGDOC::original',{'title':'Original','ref':ref},'https://example.test')
    assert all(n['original_source']['original_page']==1 for n in nodes)
    assert all(n['original_source']['source_digest']==source['digest'] for n in nodes)
    with pytest.raises(FileNotFoundError):save_capture(workspace,'alice',req,None,None,path)


@pytest.mark.parametrize('fault',['raw','body','locator','missing','duplicate','page_hash','source','library','extra_page'])
def test_archive_receipt_rejects_identity_content_and_coverage_drift(tmp_path,fault):
    path,sid,archive,source,parents=fixture(tmp_path)
    receipt=create_receipt(source,parents,digest(path),archive)
    if fault=='raw':receipt['raw_sha256']='0'*64
    if fault=='body':parents[0]['body']='tampered'
    if fault=='locator':parents[0]['locator']='HTML text chars 1-3501'
    if fault=='missing':parents.pop()
    if fault=='duplicate':parents[-1]=parents[0]
    if fault=='page_hash':receipt['pages'][0]['sha256']='0'*64
    if fault=='source':receipt['source_id']='other'
    if fault=='library':receipt['library_sha256']='0'*64
    if fault=='extra_page':receipt['pages'].append(deepcopy(receipt['pages'][0]))
    with pytest.raises(ValueError):recover_archive(source,parents,digest(path),receipt)


def test_pdf_blank_pages_preserved_and_page_offsets_not_flattened(tmp_path,monkeypatch):
    path,sid,archive,source,parents=fixture(tmp_path,pages=['First page','','Last page'])
    for p in parents:
        number=int(p['id'].split(':P')[-1].split(':')[0])
        p['locator']=p['locator'].replace('HTML text',f'PDF page {number}')
    from retrieval.library_archive_recovery import FORMAT, PROFILES
    receipt=dict(format=FORMAT,source_id=sid,library_sha256=digest(path),raw_sha256=source['digest'],parser=PROFILES['.pdf'],
                 pages=[dict(number=i+1,text=t,sha256=text_digest(t)) for i,t in enumerate(['First page','','Last page'])])
    text,recovered,provenance=recover_archive(source,parents,digest(path),receipt)
    assert text=='First page\f\fLast page'
    assert [p['original_page'] for p in recovered]==[1,3]
    bundle={'source':source,'text':text,'archive_recovery':provenance}
    validate_bundle_text(bundle)
    provenance['pages'].pop(1)
    with pytest.raises(ValueError):validate_bundle_text(bundle)


def test_catalog_pins_version_paths_receipts_and_allowed_archives(tmp_path,monkeypatch):
    path,sid,archive,source,parents=fixture(tmp_path)
    with pytest.raises(ValueError,match='allowed_roots'):
        prepare(path,[sid],[tmp_path/'elsewhere'],tmp_path/'denied')
    assert json.loads((tmp_path/'denied'/'catalog.json').read_text())['status']=='failed'
    output=tmp_path/'receipts'; manifest=prepare(path,[sid],[archive.parent],output)
    with pytest.raises(ValueError,match='catalog_digest'):
        ArchiveRecoveryCatalog(output/'catalog.json','0'*64)
    catalog=ArchiveRecoveryCatalog(output/'catalog.json',digest(output/'catalog.json'))
    with pytest.raises(ValueError,match='library_mismatch'):catalog.recover(source,parents,'0'*64)
    with pytest.raises(ValueError,match='catalog_required'):load_bundle(path,sid,None)
    monkeypatch.setenv('FINSIGHT_LIBRARY_RECOVERY_CATALOG',str(output/'catalog.json'))
    monkeypatch.delenv('FINSIGHT_LIBRARY_RECOVERY_SHA256',raising=False)
    with pytest.raises(ValueError,match='configuration_incomplete'):configured_catalog()
    payload=output/(manifest['sources'][sid]['sha256']+'.json')
    payload.write_text('{}')
    with pytest.raises(ValueError,match='receipt_digest'):catalog.recover(source,parents,digest(path))


def test_changed_raw_file_cannot_be_replayed(tmp_path):
    path,sid,archive,source,parents=fixture(tmp_path)
    archive.write_text('replaced')
    with pytest.raises(ValueError,match='raw_digest'):create_receipt(source,parents,digest(path),archive)


@pytest.mark.parametrize('fault',['text_tail','raw_digest','page_span','page_digest','parsed_digest'])
def test_saved_binary_source_retains_both_digest_domains(tmp_path,fault):
    path,sid,archive,source,parents=fixture(tmp_path)
    output=tmp_path/'receipts';prepare(path,[sid],[archive.parent],output)
    catalog=ArchiveRecoveryCatalog(output/'catalog.json',digest(output/'catalog.json'))
    bundle=compact_source_bundle(load_bundle(path,sid,catalog))
    if fault=='text_tail':bundle['text']+='lost boundary'
    if fault=='raw_digest':bundle['source']['digest']='0'*64
    if fault=='page_span':bundle['archive_recovery']['pages'][0]['source_char_end']-=1
    if fault=='page_digest':bundle['archive_recovery']['pages'][0]['sha256']='0'*64
    if fault=='parsed_digest':bundle['archive_recovery']['parsed_text_sha256']='0'*64
    with pytest.raises(ValueError):expand_source_bundle(bundle)
