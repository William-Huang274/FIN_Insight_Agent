"""Readable projections of archived material; never invent article bodies or dates."""
import json
from hashlib import sha256

DIRECTORIES = {'news_discovery', 'community_repository', 'model_catalogue', 'community_feedback'}


def archived_text(db, source_id):
    """Reassemble Collector's 250-character overlap, verifying the source digest."""
    source = db.execute('SELECT digest FROM sources WHERE id=?', (source_id,)).fetchone()
    rows = db.execute('SELECT body,locator FROM passages WHERE source_id=? ORDER BY rowid', (source_id,)).fetchall()
    if not rows:
        return ''
    parts = [r['body'] for r in rows]
    candidates = [''.join(parts[:1] + [p[250:] for p in parts[1:]]), ''.join(parts)]
    for text in candidates:
        if sha256(text.encode()).hexdigest() == source['digest']:
            return text
    # Never parse truncated or overlapping JSON as a complete record list.
    if len(parts) == 1:
        return parts[0]
    raise ValueError('archive_reassembly_digest_mismatch')


def directory_records(db, source):
    metadata=source.get('metadata', {})
    if isinstance(metadata,str):metadata=json.loads(metadata)
    category = source.get('category') or metadata.get('category')
    if category not in DIRECTORIES:
        return None
    parsed = json.loads(archived_text(db, source['id']))
    if not isinstance(parsed, list) or not all(isinstance(r, dict) for r in parsed):
        raise ValueError('directory_expected_object_list')
    records = []
    for index, row in enumerate(parsed):
        title = row.get('title') or row.get('full_name') or row.get('modelId') or row.get('id')
        url = row.get('url') or row.get('html_url')
        if category == 'model_catalogue':
            url = 'https://huggingface.co/' + str(row.get('id', ''))
        published = row.get('published_at')
        created = row.get('created_at') or row.get('createdAt')
        updated = row.get('updated_at') or row.get('lastModified')
        records.append({'record_index': index, 'source_id': source['id'],
            'title': str(title or f'未命名条目 {index+1}'), 'url': url,
            'publisher': row.get('publisher') or row.get('author') or row.get('author_association'),
            'published_at': published, 'created_at': created, 'updated_at': updated,
            'summary': row.get('description') or '', 'body': row.get('body') or '',
            'body_available': bool(row.get('body')), 'record_kind': category,
            'metrics': {k: row[k] for k in ('stargazers_count','forks_count','downloads','likes','comments','state','language') if row.get(k) is not None}})
    return records


def material_preview(db, source):
    """Dates retain their meaning; an excerpt is not a generated abstract."""
    meta = source['metadata']
    source['captured_at'] = meta.get('captured_at') or meta.get('known_at')
    source['display_title'] = str(source.get('title') or '').strip() or str(meta.get('document_number') or source['url'])
    source['preview_kind'] = 'original_excerpt'
    try:
        records = directory_records(db, source)
    except (ValueError, TypeError, KeyError):
        source.update(preview_kind='parse_error', preview='目录解析失败；保留原记录待修复。')
        return source
    if records is not None:
        source['preview_kind'] = 'directory'
        source['record_count'] = len(records)
        source['preview'] = '；'.join(r['title'] for r in records[:3])[:280]
        dates = sorted(r['published_at'] for r in records if r['published_at'])
        source['record_date_range'] = [dates[0], dates[-1]] if dates else None
    else:
        row = db.execute('SELECT body FROM passages WHERE source_id=? ORDER BY rowid LIMIT 1', (source['id'],)).fetchone()
        body = row['body'] if row else ''
        if body.lstrip().startswith(('{','[')) and not body.startswith('[PDF'):
            source['preview_kind'] = 'structured_data'
            source['preview'] = '来源结构化记录；在数据视图查看指标、期间与出处。'
        else:
            source['preview'] = ' '.join(body.split())[:260]
    return source


def material_view(db, source, *, offset=0, limit=20):
    rows = directory_records(db, source)
    if rows is None:
        return None
    return {'kind': 'directory', 'items': rows[offset:offset+limit], 'total': len(rows),
        'next_offset': offset+limit if offset+limit < len(rows) else None,
        'notice': '新闻条目是检索线索，不是新闻正文。创建、更新和抓取时间不替代发布日期。'}
