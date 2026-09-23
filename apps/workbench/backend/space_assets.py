"""Explicit immutable publication into organization custody, behind Java ACLs.

No user-provided owner or path. Old project assets remain independent; Java
revokes the published resource. Research/Agent handoff is intentionally absent.
"""
import json
from uuid import UUID

from fastapi import HTTPException
from sec_agent.research_foundation.asset_workspace import AssetWorkspace, AssetRef, AssetConflict
from sec_agent.research_foundation.project_library import ProjectConflict
from sec_agent.research_foundation.project_source_captures import read_capture


class SpaceAssets:
    def __init__(self, root):
        self.workspace = AssetWorkspace(root)
        with self.workspace.library.documents.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS space_publications('
                       'id TEXT PRIMARY KEY,actor TEXT NOT NULL,source_ref TEXT NOT NULL,binding TEXT NOT NULL)')

    def publish(self, source, actor, resource_id, organization_id, space_id, ref):
        resource_id, organization_id, space_id = map(lambda v: str(UUID(str(v))), (resource_id, organization_id, space_id))
        ref = AssetRef.model_validate(ref)
        encoded = ref.model_dump_json()
        if ref.kind != 'document':
            raise ValueError('本批支持文件及已保存的知识/财务选取；SEC连接需先保存为受控资料')
        version, row = source.resolve(actor, ref)
        owner = 'organization:' + organization_id
        library = self.workspace.library
        with library.documents.connect() as db:
            prior = db.execute('SELECT * FROM space_publications WHERE id=?', (resource_id,)).fetchone()
        if prior:
            binding = json.loads(prior['binding'])
            if prior['actor'] != actor or prior['source_ref'] != encoded or binding['space_id'] != space_id or binding['organization_id'] != organization_id:
                raise AssetConflict('发布标识已用于另一资源或空间')
            self.workspace.resolve(owner, binding['ref'])
            return binding
        index = library.index(owner)
        if not any(p['id'] == space_id for p in index['projects']):
            # Internal physical namespace only, not a user-visible research project.
            try:
                library.save(owner, index['revision'], {'projects': [*index['projects'], {'id': space_id, 'name': '组织资料空间'}],
                    'assignments': index['assignments'], 'pinned': index['pinned']})
            except ProjectConflict:
                if not any(p['id'] == space_id for p in library.index(owner)['projects']):
                    raise
        scope = library.scope(owner, space_id)
        capture = read_capture(source.library.documents, row)
        # Explicit publication has independent custody. Keep research lineage in
        # the binding, not the original store's live dependency-ACL mechanism.
        kwargs = {'source_capture': {'snapshot': capture['snapshot'], 'note': capture['note']}} if capture else {'deduplicate': True}
        saved = library.documents.add(scope, row['name'], row['body'], **kwargs)
        target = next(v for a in self.workspace.catalog(owner, space_id)['items'] for v in a['versions'] if v['ref']['version_id'] == saved['document_id'])
        binding = {'organization_id': organization_id, 'space_id': space_id, 'ref': target['ref'],
                   'source_ref': ref.model_dump(mode='json'), 'title': version['title'], 'source_role': version['role'],
                   'source_provenance': row.get('project_origin', {}),
                   'resource_type': 'database' if version['role'] == 'database' else 'knowledge' if capture else 'files'}
        with library.documents.connect() as db:
            db.execute('INSERT INTO space_publications VALUES(?,?,?,?) ON CONFLICT(id) DO NOTHING',
                       (resource_id, actor, encoded, json.dumps(binding, ensure_ascii=False)))
            prior = db.execute('SELECT * FROM space_publications WHERE id=?', (resource_id,)).fetchone()
            if prior['actor'] != actor or prior['source_ref'] != encoded or json.loads(prior['binding']) != binding:
                raise AssetConflict('发布标识冲突，请读取原发布结果')
        return binding

    def read(self, binding):
        org, space = str(UUID(binding['organization_id'])), str(UUID(binding['space_id']))
        ref = AssetRef.model_validate(binding['ref'])
        if str(ref.project_id) != space:
            raise HTTPException(502, '空间与保存版本不匹配')
        result = self.workspace.read('organization:' + org, ref)
        return {**result, 'version': {**result['version'], 'role': binding['source_role']}, 'editable': False,
                'publication': {'organization_id': org, 'space_id': space,
                'source_ref': binding['source_ref'], 'resource_type': binding['resource_type']}}
