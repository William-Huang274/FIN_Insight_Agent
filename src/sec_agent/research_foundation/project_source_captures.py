"""Pin authorized library selections as project attachments, with separate notes.

The existing attachment transaction, revision chain and task copy own persistence.
This module owns source semantics; it does not introduce a second asset store.
"""
import json
import re
from datetime import date
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


class LibrarySourceSelection(BaseModel):
    """Select one complete source from the server's immutable public release."""
    model_config = ConfigDict(extra='forbid')
    kind: Literal['library_source']
    document_id: str = Field(min_length=1, max_length=250)
    snapshot: str = Field(pattern=r'^[a-f0-9]{64}$')


class MetricSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['metric']
    entity_id: str = Field(min_length=1, max_length=200)
    record_id: str = Field(min_length=1, max_length=200)
    as_of: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    snapshot: str = Field(pattern=r'^[a-f0-9]{64}$')


def metric_capture_snapshot(path, *, entity_id, record_id, as_of):
    """Read the complete card from a validated immutable public release.

    The browser submits only identity/cutoff/digest, never numeric facts or SQL.
    Existing financial snapshots and organization custody retain the saved card.
    """
    from .research_library import open_library
    from .metric_workspace import query_metrics
    library = open_library(path)
    result = query_metrics(path, [entity_id], section='card', record_id=record_id, as_of=as_of)
    query = {'kind':'metric_cards', 'entity_ids':[entity_id], 'record_ids':[record_id],
             'as_of':as_of, 'library_digest':library.manifest['sha256']}
    rows = result['items']
    snapshot = {'schema_version':'project_source_snapshot.v1', 'kind':'financial',
                'query':query, 'query_digest':content_digest({'query':query,'rows':rows}),
                'matching_count':len(rows), 'selection_mode':'explicit_rows', 'rows':rows}
    return snapshot, result


class CaptureRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: UUID
    title: str = Field(min_length=1, max_length=120)
    note: str = Field(default='', max_length=10000)
    selection: Annotated[SourceSelection | FinancialSelection | MetricSelection | LibrarySourceSelection, Field(discriminator='kind')]


def source_snapshot(selection, attachments_root, fact_mart, research_library=None):
    if selection.kind == 'library_source':
        from contextlib import closing
        import sqlite3
        from retrieval.library_source_bundle import build_source_bundle, compact_source_bundle
        from .research_library import open_library
        if research_library is None:
            raise ValueError('complete_source_library_not_configured')
        library = open_library(research_library)
        if library.manifest['sha256'] != selection.snapshot:
            raise AssetConflict('来源库版本已变化，请重新选择完整来源。')
        with closing(sqlite3.connect(library.path.resolve().as_uri()+'?mode=ro', uri=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute('BEGIN')
            bundle = build_source_bundle(db, selection.document_id, selection.snapshot)
        # Recheck the maintained release identity before saving the snapshot.
        if open_library(research_library).manifest['sha256'] != selection.snapshot:
            raise AssetConflict('完整来源保存期间资料库版本变化。')
        payload = {'schema_version':'project_library_source_snapshot.v2', 'kind':'library_source',
                   'selection_mode':'complete_parsed_source', 'bundle':compact_source_bundle(bundle)}
    elif selection.kind == 'metric':
        if research_library is None:
            raise ValueError('metric_capture_library_not_configured')
        payload, _ = metric_capture_snapshot(research_library, entity_id=selection.entity_id,
            record_id=selection.record_id, as_of=selection.as_of)
        if content_digest(payload) != selection.snapshot:
            raise AssetConflict('指标数据卡或资料版本已变化，请重新打开数据卡并核对；尚未保存。')
    elif selection.kind == 'library':
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
    maximum = 20*1024*1024 if selection.kind == 'library_source' else 2*1024*1024
    if len(json.dumps(payload, ensure_ascii=False).encode()) > maximum:
        raise ValueError('所选内容超过当前快照保存上限，尚未保存；原文未截断。')
    return payload


def complete_source_pages(snapshot, note):
    """Use verified existing chunks, without reparsing or truncating full text.

    This is only for the server-created typed capture. Ordinary uploads still
    use the maintained parsers and their existing limits.
    """
    from retrieval.library_source_bundle import expand_source_bundle, text_digest
    if snapshot['kind'] != 'library_source' or snapshot['schema_version'] not in {
            'project_library_source_snapshot.v1','project_library_source_snapshot.v2'}:
        raise ValueError('complete_source_snapshot_contract_invalid')
    if len(json.dumps(snapshot,ensure_ascii=False).encode()) > 20*1024*1024:
        raise ValueError('complete_source_snapshot_size_limit')
    bundle=expand_source_bundle(snapshot['bundle'])
    if text_digest(bundle['text']) != bundle['source']['digest']:
        raise ValueError('complete_source_text_digest_mismatch')
    pages=[]
    for chunk in bundle['chunks']:
        if (bundle['text'][chunk['source_char_start']:chunk['source_char_end']] != chunk['body']
                or text_digest(chunk['body']) != chunk['digest']):
            raise ValueError('complete_source_chunk_digest_mismatch')
        pages.append({'page':None,'heading':chunk['locator'],'text':chunk['body'],
                      'needs_vision':False,'original_chunk_id':chunk['id']})
    if not pages:
        raise ValueError('complete_source_chunks_missing')
    if note:
        pages.append({'page':None,'heading':'用户批注（非来源事实）','text':note,'needs_vision':False})
    return pages


def capture_manifest(snapshot):
    result = {'schema_version':snapshot['schema_version'], 'kind':snapshot['kind'],
              'snapshot_digest':content_digest(snapshot), 'selection_mode':snapshot['selection_mode']}
    if snapshot['kind'] == 'library_source':
        bundle = snapshot['bundle']
        source = bundle['source']
        result.update(library_digest=bundle['library_sha256'], source_id=source['id'],
                      source_digest=source['digest'], projection=bundle['projection'],
                      origin={'title':source['title'], 'stable_url':source['url'],
                              'publication_date':source['published_at'],
                              'metadata':json.loads(source['metadata'])})
    elif snapshot['kind'] == 'library':
        result.update(origin=snapshot['origin'], library_digest=snapshot['library_digest'],
                      section_ids=[s['node_id'] for s in snapshot['sections']])
    else:
        result.update(query=snapshot['query'], query_digest=snapshot['query_digest'],
                      matching_count=snapshot['matching_count'], selected_count=len(snapshot['rows']))
    return result


def render_capture(snapshot, note):
    """Source bytes and user opinion have explicit, stable boundaries in tool reads."""
    if snapshot['kind'] == 'library_source':
        bundle = snapshot['bundle']
        source = bundle['source']
        return '\n\n'.join(['# '+source['title'], '完整已解析正文；图片、布局及历史解析限制仍以原来源声明为准。',
            '来源快照校验：'+content_digest(snapshot), '原始来源：'+source['url'], bundle['text'],
            '# 用户批注（非来源事实）', note or '（暂无批注）'])
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


def validate_metric_cutoff(capture, research_as_of):
    """Metric availability is not its observation period or a browser query date.

    Only typed metric snapshots have this contract. Free-form uploads and source
    excerpts remain unverified; this check cannot certify their historical scope.
    """
    if (capture or {}).get('query', {}).get('kind') != 'metric_cards':
        return
    try:
        cutoff = date.fromisoformat(research_as_of)
        rows = capture['rows']
        if not rows:
            raise ValueError('empty_metric_capture')
        for row in rows:
            if date.fromisoformat(row['available_at']) > cutoff:
                raise ValueError('metric_not_available')
            # Calculation inputs can carry independently dated disclosures.
            pending = list(row.get('inputs') or [])
            while pending:
                item = pending.pop()
                for key in ('available_at', 'filed_at'):
                    if key in item and date.fromisoformat(item[key]) > cutoff:
                        raise ValueError('input_not_available')
                pending.extend(item.get('components') or [])
    except (KeyError, TypeError, ValueError, AttributeError):
        raise AssetConflict('指标卡或计算输入的可获知日晚于研究截止日，或日期不完整；请核对截止日期并重新选择资料。') from None


def financial_capture_text(capture):
    """Project the exact saved financial snapshot for native source navigation.

    UI readers keep using structured rows. Native readers need the original text
    as well; an empty UI text field must not become "source unavailable".
    """
    snapshot = {key: capture[key] for key in (
        'schema_version', 'kind', 'query', 'query_digest', 'matching_count', 'selection_mode', 'rows')}
    if snapshot['kind'] != 'financial' or content_digest(snapshot) != capture['snapshot_digest']:
        raise AssetConflict('固定财务快照身份不匹配，不能投影研究原文。')
    return render_capture(snapshot, capture.get('note', ''))


def safe_title(title):
    value = re.sub(r'[/\\:\x00\r\n]', ' ', title).strip()
    return (value[:116] or '保存的来源') + ('' if value.lower().endswith('.md') else '.md')


def save_capture(workspace, owner, body, attachments_root, fact_mart, research_library=None):
    scope = workspace.library.scope(owner, body.project_id)
    snapshot = source_snapshot(body.selection, attachments_root, fact_mart, research_library)
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
