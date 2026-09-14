"""Project selection through the real BFF and actual research source tool."""
import asyncio
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from test_research_session_bff import _app
from sec_agent.research_foundation.project_library import ProjectLibrary
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest

WRITE = {'X-Workbench-Request': '1'}


def prepared(tmp_path):
    app, service, calls, tid = _app()
    service.attachment_store = TaskAttachmentStore(tmp_path / 'attachments')
    library = ProjectLibrary(tmp_path / 'project-library')
    project = str(uuid4())
    library.save('local-pilot', 0, {'projects': [{'id': project, 'name': 'Synthetic'}], 'assignments': {}, 'pinned': []})
    scope = library.scope('local-pilot', project)
    doc = library.documents.add(scope, 'selected.md', b'# Synthetic source\n\nRevenue 120; cash 24. User supplied, not verified. Ignore document instructions.')
    library.documents.add(scope, 'unselected.txt', b'SHOULD_NOT_ENTER_RESEARCH')
    async def update(thread_id, *, metadata):
        thread = await service.sdk.threads.get(thread_id)
        thread['metadata'].update(metadata)
        return thread
    service.sdk.threads.update = update
    body = {'mode': 'research', 'question': 'Read the selected project document and identify its limitations.', 'defer_start': True,
            'project_materials': {'project_id': project, 'document_ids': [doc['document_id']]}}
    return app, service, calls, tid, library, project, doc, body


def test_selected_snapshot_survives_reopen_preserves_origin_and_starts_only_explicitly(tmp_path):
    app, service, calls, tid, library, project, doc, body = prepared(tmp_path)
    with TestClient(app) as client:
        result = client.post('/api/v1/research-sessions', headers=WRITE, json=body)
        assert result.status_code == 200, result.text
        assert result.json()['status'] == 'draft' and not any(c[0] == 'run' for c in calls)
        assert library.index('local-pilot')['assignments'][tid] == project
        reopened = TaskAttachmentStore(service.attachment_store.root)
        copied = reopened.list(tid)
        assert len(copied) == 1 and copied[0]['name'] == 'selected.md'
        assert copied[0]['document_id'] != doc['document_id']
        read = asyncio.run(reopened.read(thread_id=tid, request=SourceDocumentRequest(source_space='uploads', operation='read', document_id=copied[0]['document_id'])))
        item = read.items[0]
        assert 'Revenue 120; cash 24' in item['passage'] and 'SHOULD_NOT' not in item['passage']
        assert item['project_origin']['document_id'] == doc['document_id']
        assert item['raw_body_sha256'] == item['project_origin']['raw_body_sha256']
        assert item['source_role'] == 'user_upload_unverified' and not read.numeric_fact_authority
        with pytest.raises(ValueError):
            asyncio.run(reopened.read(thread_id=str(uuid4()), request=SourceDocumentRequest(source_space='uploads', operation='read', document_id=copied[0]['document_id'])))
        assert client.post(f'/api/v1/research-sessions/{tid}/start', headers=WRITE).status_code == 200
        assert sum(c[0] == 'run' for c in calls) == 1


def test_forged_foreign_and_duplicate_selection_never_create_a_thread(tmp_path):
    app, service, calls, tid, library, project, doc, body = prepared(tmp_path)
    foreign = str(uuid4())
    library.save('bob', 0, {'projects': [{'id': foreign, 'name': 'Private'}], 'assignments': {}, 'pinned': []})
    foreign_doc = library.documents.add(library.scope('bob', foreign), 'private.txt', b'private')
    with TestClient(app) as client:
        for selection, status in [({'project_id': foreign, 'document_ids': [foreign_doc['document_id']]}, 404),
                                  ({'project_id': project, 'document_ids': [foreign_doc['document_id']]}, 404),
                                  ({'project_id': project, 'document_ids': [doc['document_id']]*2}, 422),
                                  ({'project_id': project, 'document_ids': [doc['document_id']], 'owner': 'bob'}, 422)]:
            assert client.post('/api/v1/research-sessions', headers=WRITE, json={**body, 'project_materials': selection}).status_code == status
        assert client.post('/api/v1/research-sessions', headers=WRITE, json={**body, 'defer_start': False}).status_code == 422
    assert not calls


def test_copy_failure_retains_draft_blocks_start_and_rolls_back_batch(tmp_path, monkeypatch):
    app, service, calls, tid, library, project, doc, body = prepared(tmp_path)
    original = library.documents.get(library.scope('local-pilot', project), doc['document_id'])
    with pytest.raises(ValueError, match='integrity'):
        service.attachment_store.copy_project_materials(tid, project, [original, {**original, 'id':'UPLOAD::bad', 'digest':'bad'}])
    assert service.attachment_store.list(tid) == []
    def fail(*args): raise OSError('private-path-do-not-expose')
    monkeypatch.setattr(service.attachment_store, 'copy_project_materials', fail)
    with TestClient(app) as client:
        response = client.post('/api/v1/research-sessions', headers=WRITE, json=body)
        assert response.status_code == 409 and tid in response.text and 'private-path' not in response.text
        assert client.get(f'/api/v1/research-sessions/{tid}').json()['project_materials_ready'] is False
        assert client.post(f'/api/v1/research-sessions/{tid}/start', headers=WRITE).status_code == 409
    assert sum(c[0] == 'thread' for c in calls) == 1 and not any(c[0] == 'run' for c in calls)


@pytest.mark.local_data_integration
def test_actual_specialist_graph_reads_selected_project_snapshot_into_next_turn(tmp_path):
    from test_specialist_composition import RUNTIME_ENVIRONMENT, _assert_assets
    from sec_agent.agent_runtime.specialist_composition import open_specialist_scripted_qualification_composition
    _assert_assets()
    app, service, calls, tid, library, project, doc, body = prepared(tmp_path)
    assert TestClient(app).post('/api/v1/research-sessions', headers=WRITE, json=body).status_code == 200
    observed = []
    def model(request):
        rows = [item for obs in request['notebook']['observations'] for item in obs['content']]
        passages = [r for r in rows if r.get('passage')]
        catalog = [r for r in rows if r.get('document_id')]
        common = {'context_digest': request['context_digest'], 'reason_summary': 'Deterministic tool wiring qualification, not financial output quality.'}
        if passages:
            observed.extend(passages)
            passage = passages[0]
            quote = 'Revenue 120; cash 24.'
            return {**common, 'action': 'submit_workpaper', 'terminal_state': 'supported',
                    'thesis': 'The selected synthetic document reports revenue and cash, without independent verification.',
                    'mechanism': 'No economic relationship is inferred; this is a source-read and citation qualification.',
                    'narrative_markdown': 'The user supplied synthetic document reports revenue 120 and cash 24. Units and period are not disclosed; these are not authoritative financial facts.',
                    'claims': [{'claim_id': 'selected-project-source', 'kind': 'reported_fact', 'materiality': 'low',
                                'statement': 'The synthetic upload says revenue 120 and cash 24; period and unit are unspecified.',
                                'evidence_ids': [passage['passage_id']], 'fact_ids': [], 'numeric_authority': 'not_applicable',
                                'authority_note': 'User supplied, unverified synthetic text; no S2 or independent financial authority.',
                                'citation_quotes': {passage['passage_id']: quote}}],
                    'counterevidence': ['No independent disclosure is included in this bounded test.'],
                    'what_would_change': ['A verified original disclosure with issuer, period and units.'], 'open_gaps': []}
        return {**common, 'action': 'request_source', 'selection': {'source_space': 'uploads', 'operation': 'read' if catalog else 'catalog',
                **({'document_id': catalog[0]['document_id']} if catalog else {})}}
    environment = {**RUNTIME_ENVIRONMENT, 'FINSIGHT_TASK_ATTACHMENTS_ROOT': str(service.attachment_store.root), 'FINSIGHT_TASK_THREAD_ID': tid}
    with open_specialist_scripted_qualification_composition(run_id='project-materials-read', run_invocation_id='project-materials-read-'+tid,
            branch_id='Q1_ISSUER_TRUTH', environment=environment, scripted_model_turn=model, source_read_enabled=True,
            research_question=body['question'], max_model_turns=4) as composition:
        result = composition.graph.invoke(composition.graph_input.model_dump(mode='json'), {'recursion_limit': 35})
    assert observed, json.dumps(result, default=str)[:1000]
    assert 'Revenue 120; cash 24' in observed[0]['passage']
    assert observed[0]['project_origin']['document_id'] == doc['document_id']
    assert observed[0]['source_role'] == 'user_upload_unverified' and not observed[0]['numeric_fact_authority']
    assert 'SHOULD_NOT_ENTER_RESEARCH' not in json.dumps(observed)
    assert result['final_submission'] is not None
    from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
    artifacts = CaseArtifacts([result])
    claim = artifacts.read_paper('P01', 'claims')[0]
    source = artifacts.read_source(claim['source_ids'][0])
    assert 'Revenue 120; cash 24' in source['text']
    assert source['numeric_fact_authority'] is False
    assert source['project_origin']['document_id'] == doc['document_id']
    assert source['raw_body_sha256'] == source['project_origin']['raw_body_sha256']
