from copy import deepcopy
import pytest
from retrieval.source_table_periods import build_overlay, digest, validate_overlay, MARKER
from retrieval.source_structure import source_structure
from test_source_structure import bundle


def fixture():
    raw = b'''<html><body><ix:header><xbrli:context id="current"><xbrli:entity>
    <xbrli:identifier scheme="test">42</xbrli:identifier></xbrli:entity><xbrli:period>
    <xbrli:instant>2025-06-30</xbrli:instant></xbrli:period></xbrli:context>
    <xbrli:context id="prior"><xbrli:entity><xbrli:identifier scheme="test">42</xbrli:identifier>
    </xbrli:entity><xbrli:period><xbrli:startDate>2023-07-01</xbrli:startDate>
    <xbrli:endDate>2024-06-30</xbrli:endDate></xbrli:period></xbrli:context></ix:header>
    <p>FY2025 report published September 2025</p><table>
    <tr><th rowspan="2">Cash</th><th colspan="2">June 30, 2025</th><th colspan="2">June 30, 2024</th></tr>
    <tr><td colspan="2">Current</td><td colspan="2">Prior</td></tr>
    <tr><td>Cash balance</td><td>$</td><td><ix:nonFraction name="gaap:Cash" contextRef="current" unitRef="USD" scale="3">100</ix:nonFraction></td>
    <td>$</td><td><ix:nonFraction name="gaap:CashFlow" contextRef="prior" unitRef="USD" scale="3">90</ix:nonFraction></td></tr>
    </table></body></html>'''
    text = 'FY2025 report published September 2025\n'+MARKER+'\nCash | June 30, 2025 | June 30, 2024\nCurrent | Prior\nCash balance | $ | 100 | $ | 90\n[/TABLE]'
    return raw, text


def test_explicit_context_and_geometry_preserve_distinct_periods():
    raw,text=fixture()
    overlay=build_overlay(raw,raw_sha256=digest(raw),source_digest=digest(text))
    table=overlay['tables'][0]
    assert table['status']=='original_geometry_verified'
    current=next(c for c in table['cells'] if c['text']=='100')
    prior=next(c for c in table['cells'] if c['text']=='90')
    assert current['column']==2 and prior['column']==4
    assert current['facts'][0]['period']['dates']=={'instant':'2025-06-30'}
    assert prior['facts'][0]['period']['dates']=={'startdate':'2023-07-01','enddate':'2024-06-30'}
    assert prior['facts'][0]['concept']=='gaap:CashFlow'
    assert next(c for c in table['cells'] if c['text']=='Current')['column']==1
    assert text[current['source_char_start']:current['source_char_end']]=='100'
    b=bundle(text,text.index('Cash balance'))
    b['table_period_context']=overlay
    assert validate_overlay(b)==overlay['tables']
    structures=source_structure(b)
    assert not structures['0']['tables'][0]['period_cells']
    assert len(structures['1']['tables'][0]['period_cells'])==2


def test_old_flattened_tables_abstain_and_overlays_cannot_drift():
    raw,text=fixture();b=bundle(text)
    assert source_structure(b)['0']['tables'][0]['period_binding']=='requires_original_geometry_and_periods'
    b['table_period_context']=build_overlay(raw,raw_sha256=digest(raw),source_digest=digest(text))
    changed=deepcopy(b);changed['table_period_context']['tables'][0]['cells'][0]['text']='wrong'
    with pytest.raises(ValueError,match='cell_mismatch'):source_structure(changed)
    with pytest.raises(ValueError,match='raw_digest'):build_overlay(raw+b' ',raw_sha256=digest(raw),source_digest=digest(text))
    with pytest.raises(ValueError,match='projection_mismatch'):build_overlay(raw,raw_sha256=digest(raw),source_digest=digest(text+'extra'))


def test_missing_context_never_falls_back_to_report_year():
    raw,text=fixture();raw=raw.replace(b'contextRef="current"',b'contextRef="unknown"')
    o=build_overlay(raw,raw_sha256=digest(raw),source_digest=digest(text))
    fact=next(c for c in o['tables'][0]['cells'] if c['text']=='100')['facts'][0]
    assert fact['period']=={'status':'missing_context'}


def test_invalid_spans_abstain_without_changing_legacy_projection():
    raw,text=fixture();raw=raw.replace(b'rowspan="2"',b'rowspan="9999"')
    o=build_overlay(raw,raw_sha256=digest(raw),source_digest=digest(text))
    assert o['tables'][0]['status']=='source_table_span_invalid'
    assert all(c['column'] is None for c in o['tables'][0]['cells'])
    assert next(c for c in o['tables'][0]['cells'] if c['text']=='100')['facts'][0]['period']['dates']=={'instant':'2025-06-30'}


def test_duplicate_contexts_are_rejected():
    raw,text=fixture();raw=raw.replace(b'id="prior"',b'id="current"')
    with pytest.raises(ValueError,match='context_identity'):build_overlay(raw,raw_sha256=digest(raw),source_digest=digest(text))


def catalog_at(path,b,overlay):
    import json
    path.mkdir(exist_ok=True)
    payload=json.dumps(overlay).encode();(path/'overlay.json').write_bytes(payload)
    cat={'format':'source-table-period-catalog.v1','library_sha256':b['library_sha256'],
        'sources':{b['source']['id']:{'file':'overlay.json','sha256':digest(payload),'source_digest':b['source']['digest']}}}
    raw=json.dumps(cat).encode();(path/'catalog.json').write_bytes(raw)
    return path/'catalog.json',digest(raw)


def test_catalog_requires_digest_library_identity_and_contained_path(tmp_path,monkeypatch):
    import json
    from retrieval.source_table_periods import enrich_from_catalog
    raw,text=fixture();b=bundle(text);b['source']['id']='source';b['library_sha256']='library'
    assert enrich_from_catalog(b) is b
    overlay=build_overlay(raw,raw_sha256=digest(raw),source_digest=digest(text))
    path,sha=catalog_at(tmp_path,b,overlay)
    monkeypatch.setenv('FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG',str(path))
    monkeypatch.setenv('FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG_SHA256',sha)
    new=enrich_from_catalog(b)
    assert 'table_period_context' not in b and new['text']==b['text']
    assert validate_overlay(new)
    with pytest.raises(ValueError,match='library_mismatch'):enrich_from_catalog({**b,'library_sha256':'other'})
    cat=json.loads(path.read_bytes());cat['sources']['source']['file']='../outside.json'
    payload=json.dumps(cat).encode();path.write_bytes(payload)
    monkeypatch.setenv('FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG_SHA256',digest(payload))
    with pytest.raises(ValueError,match='path_invalid'):enrich_from_catalog(b)
    path.write_bytes(payload+b' ')
    with pytest.raises(ValueError,match='catalog_digest'):enrich_from_catalog(b)


def test_capture_publish_readback_consumes_period_overlay(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4
    from test_library_source_bundle import database,bundle_at
    from test_organization_research_inputs import fixture as organization_fixture
    from test_organization_execution_access import runtime_at,runtime_grant
    from sec_agent.research_foundation.asset_workspace import AssetWorkspace
    from sec_agent.research_foundation.project_source_captures import CaptureRequest,save_capture
    from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    import sec_agent.research_foundation.research_library as library_module
    raw,text=fixture();dbpath=tmp_path/'library.sqlite';sid=database(dbpath,text);b=bundle_at(dbpath,sid)
    overlay=build_overlay(raw,raw_sha256=digest(raw),source_digest=digest(text))
    path,sha=catalog_at(tmp_path/'catalog',b,overlay)
    monkeypatch.setenv('FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG',str(path))
    monkeypatch.setenv('FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG_SHA256',sha)
    monkeypatch.setattr(library_module,'open_library',lambda _:SimpleNamespace(path=dbpath,manifest={'sha256':b['library_sha256']}))
    workspace=AssetWorkspace(tmp_path/'private');project=str(uuid4())
    workspace.library.save('alice',0,{'projects':[{'id':project,'name':'Original'}],'assignments':{},'pinned':[]})
    saved=save_capture(workspace,'alice',CaptureRequest(project_id=project,title='Periods',selection={
        'kind':'library_source','document_id':sid,'snapshot':b['library_sha256']}),None,None,dbpath)
    ref=next(v['ref'] for a in workspace.catalog('alice',project)['items'] for v in a['versions'] if v['ref']['version_id']==saved['document_id'])
    shared,grant=organization_fixture(tmp_path/'base');first=grant['manifest']['inputs'][0];rid=str(uuid4())
    binding=shared.publish(workspace,'alice',rid,grant['organization_id'],first['space_id'],ref)
    grant['manifest']['inputs']=[{**first,'resource_id':rid,'ref':binding['ref']}]
    grant['inputs']=[{'resource_id':rid,'binding':binding}]
    reader,state=runtime_at(shared,runtime_grant(grant));nav=OrganizationSourceNavigation(reader,workbench_url='http://localhost')
    found=nav.navigate({'source_space':'organization','operation':'search','query':'Cash balance'}).items[0]
    read=nav.navigate(found['readback']).items[0]
    assert read['passage']==text and not read['numeric_fact_authority']
    cells=read['source_structure']['tables'][0]['period_cells']
    assert {f['period']['dates'].get('instant') for c in cells for f in c['facts']}=={'2025-06-30',None}
    limited=nav.navigate({**found['readback'],'character_offset':1,'max_characters':2000}).items[0]
    assert limited['source_structure']['period_window_status']=='partial_read_requires_complete_cell_readback'
    assert not limited['source_structure']['tables'][0]['period_cells']
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(found['readback'])


def test_organization_readback_includes_structure_and_revocation(tmp_path,monkeypatch):
    from test_organization_candidate_index import prepared,query
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    nav,reader,state,directory,grant=prepared(tmp_path,monkeypatch)
    item=nav.navigate(query()).items[0]
    original=nav.navigate(item['readback']).items[0]
    assert original['source_structure']['status']=='verified_original_coordinates'
    assert original['result_state']=='source_bound_passage'
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(item['readback'])
