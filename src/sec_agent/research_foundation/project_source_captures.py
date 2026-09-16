"""Pin authorized library selections as project attachments, with separate notes.

The existing attachment transaction, revision chain and task copy own persistence.
This module owns source semantics; it does not introduce a second asset store.
"""
import json
import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .financial_library import FinancialQuery, financial_page, content_digest
from .public_library import library_nodes, document_catalog
from .asset_workspace import AssetConflict


class SourceSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['library']
    document_id: str = Field(min_length=1, max_length=250)
    snapshot: str = Field(pattern=r'^[a-f0-9]{64}$')
    section_ids: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(min_length=1, max_length=100)


class FinancialSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['financial']
    query: FinancialQuery
    snapshot: str = Field(pattern=r'^[a-f0-9]{64}$')
    row_ids: list[Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]] = Field(min_length=1, max_length=100)


class CaptureRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: UUID
    title: str = Field(min_length=1, max_length=120)
    note: str = Field(default='', max_length=10000)
    selection: Annotated[SourceSelection | FinancialSelection, Field(discriminator='kind')]


def source_snapshot(selection, attachments_root, fact_mart):
    if selection.kind == 'library':
        rows, digest = library_nodes(attachments_root)
        if digest != selection.snapshot:
            raise AssetConflict('知识库在阅读后已更新，请重新打开原文、核对并选择；尚未保存。')
        chosen = set(selection.section_ids)
        sections = [r for r in rows if r['parent_document_id'] == selection.document_id and r['node_kind'] == 'section' and r['node_id'] in chosen]
        if len(chosen) != len(selection.section_ids) or len(sections) != len(chosen):
            raise AssetConflict('所选原文章节不属于当前文档或已变化，请重新读取。')
        doc = next(d for d in document_catalog(rows) if d['document_id'] == selection.document_id)
        doc = {k:v for k,v in doc.items() if k != 'preview'}
        payload = {'schema_version':'project_source_snapshot.v1', 'kind':'library', 'origin':doc,
                   'library_digest':digest, 'selection_mode':'explicit_sections',
                   'sections':[{k:r.get(k) for k in ('node_id','parent_document_id','section_path','content','content_sha256','stable_url','publication_date','period_end','fiscal_period')} for r in sections]}
    else:
        page = financial_page(fact_mart, selection.query)
        if page['snapshot'] != selection.snapshot:
            raise AssetConflict('财务查询结果在选择后已变化，请重新查询并核对；尚未保存。')
        chosen = set(selection.row_ids)
        rows = [r for r in page['items'] if r['selection_id'] in chosen]
        if len(chosen) != len(selection.row_ids) or len(rows) != len(chosen):
            raise AssetConflict('所选记录不属于当前查询页，请重新选择。')
        payload = {'schema_version':'project_source_snapshot.v1', 'kind':'financial',
                   'query':page['selection_query'], 'query_digest':page['snapshot'],
                   'matching_count':page['total'], 'selection_mode':'explicit_rows', 'rows':rows}
    if len(json.dumps(payload, ensure_ascii=False).encode()) > 2*1024*1024:
        raise ValueError('选择内容超过单份快照2MiB，请减少章节后再保存；未截断原文。')
    return payload


def capture_manifest(snapshot):
    result = {'schema_version':snapshot['schema_version'], 'kind':snapshot['kind'],
              'snapshot_digest':content_digest(snapshot), 'selection_mode':snapshot['selection_mode']}
    if snapshot['kind'] == 'library':
        result.update(origin=snapshot['origin'], library_digest=snapshot['library_digest'],
                      section_ids=[s['node_id'] for s in snapshot['sections']])
    else:
        result.update(query=snapshot['query'], query_digest=snapshot['query_digest'],
                      matching_count=snapshot['matching_count'], selected_count=len(snapshot['rows']))
    return result


def render_capture(snapshot, note):
    """Source bytes and user opinion have explicit, stable boundaries in tool reads."""
    lines = ['# 固定来源快照', '这是用户明确选择的保存范围，不代表完整披露或全部查询结果。原始资料仍需结合期间与上下文核验。',
             '来源快照校验：'+content_digest(snapshot)]
    if snapshot['kind'] == 'library':
        doc = snapshot['origin']
        lines += ['文档：'+str(doc['title']), '原始文档标识：'+doc['document_id'],
                  '原始来源：'+str(doc['stable_url']), '披露日期：'+str(doc['publication_date']),
                  '报告期：'+str(doc.get('period_end') or doc.get('fiscal_period'))]
        for s in snapshot['sections']:
            lines += ['## 原文章节 '+s['node_id'], '章节路径：'+' / '.join(s['section_path'] or []), s['content'] or '']
    else:
        lines += ['## 财务选择范围', '筛选条件：'+json.dumps(snapshot['query'],ensure_ascii=False),
                  f"筛选共 {snapshot['matching_count']} 条，本资产明确选择 {len(snapshot['rows'])} 条；不是完整查询结果。",
                  '数值保持来源原值与单位，不合并同期间的不同披露版本。查询部署默认数据库不会自动代表本快照。']
        for i,r in enumerate(snapshot['rows'],1):
            lines += [f"## 财务原始记录 {i}", '```json\n'+json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2)+'\n```']
    lines += ['# 用户批注（非来源事实）', note or '（暂无批注）']
    return '\n\n'.join(lines)


def safe_title(title):
    value = re.sub(r'[/\\:\x00\r\n]', ' ', title).strip()
    return (value[:116] or '保存的来源') + ('' if value.lower().endswith('.md') else '.md')


def save_capture(workspace, owner, body, attachments_root, fact_mart):
    scope = workspace.library.scope(owner, body.project_id)
    snapshot = source_snapshot(body.selection, attachments_root, fact_mart)
    return workspace.library.documents.add(scope, safe_title(body.title), render_capture(snapshot, body.note).encode(),
        source_capture={'snapshot':snapshot,'note':body.note})


def read_capture(store, row):
    if not row.get('project_origin',{}).get('asset_capture'):
        return None
    with store.connect() as db:
        captured = db.execute('SELECT snapshot,note FROM attachment_captures WHERE object_id=?', (row['id'],)).fetchone()
    if not captured:
        raise AssetConflict('来源快照记录缺失，不能维护批注。')
    snapshot, note = json.loads(captured['snapshot']), captured['note']
    if capture_manifest(snapshot) != row['project_origin']['asset_capture'] or render_capture(snapshot, note).encode() != row['body']:
        raise AssetConflict('来源快照完整性校验失败。')
    return {'snapshot':snapshot,'note':note}
