"""Project-owned SEC snapshots using the existing capture adapter and SQLite.

The browser reads original observations; this does not normalize or admit S2 facts.
Manual refresh creates an immutable version. Failed refreshes retain prior versions.
"""
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from uuid import UUID

from dotenv import dotenv_values

from financial_facts.sec_snapshot import (
    SEC_SNAPSHOT_INPUT_SCHEMA_VERSION, SecSnapshotCompany, SecSnapshotInputManifest,
    SecSnapshotRequestPolicy, SecSnapshotError, capture_sec_companyfacts_snapshot,
)


class ProjectSecSources:
    def __init__(self, library):
        self.library = library
        self.root = library.documents.root / 'sec-snapshots'
        with library.documents.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS project_sec_versions '
                       '(scope TEXT NOT NULL, version TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(scope,version))')

    def versions(self, owner, project):
        scope = self.library.scope(owner, project)
        with self.library.documents.connect() as db:
            rows = db.execute('SELECT body FROM project_sec_versions WHERE scope=? ORDER BY rowid DESC', (scope,)).fetchall()
        return {'items': [json.loads(r['body']) for r in rows]}

    def capture(self, owner, project, version, ticker, cik):
        scope = self.library.scope(owner, project)
        version = str(UUID(str(version)))
        company = SecSnapshotCompany(ticker=ticker, cik=cik, legal_name=ticker)
        body = {'version': version, 'ticker': ticker, 'cik': cik, 'status': 'running',
                'requested_at': datetime.now(timezone.utc).isoformat(), 'sources': [],
                'numeric_fact_authority': False}
        with self.library.documents.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT body FROM project_sec_versions WHERE scope=? AND version=?', (scope, version)).fetchone()
            if prior:
                saved = json.loads(prior['body'])
                if saved['ticker'] != ticker or saved['cik'] != cik:
                    raise ValueError('该更新标识已用于另一家公司，请重新载入。')
                return saved  # A repeated HTTP submission never repeats a remote fetch.
            count = db.execute('SELECT COUNT(*) FROM project_sec_versions WHERE scope=?', (scope,)).fetchone()[0]
            if count >= 12:
                raise ValueError('本地试用每项目最多保留12次数据更新；已有版本保留。')
            db.execute('INSERT INTO project_sec_versions VALUES(?,?,?)', (scope, version, json.dumps(body)))
        output = self.root / scope / version
        try:
            result = capture_sec_companyfacts_snapshot(
                SecSnapshotInputManifest(schema_version=SEC_SNAPSHOT_INPUT_SCHEMA_VERSION,
                                         attempt_id=version, companies=(company,)),
                output_root=output,
                request_policy=SecSnapshotRequestPolicy(timeout_seconds=30, requests_per_second=1.0,
                    maximum_companies=1, maximum_response_bytes=32*1024*1024, per_source_attempts=1),
                environment={**dotenv_values('.env'), **os.environ})
            submissions = json.loads((output / result.artifacts[1].raw_ref).read_text(encoding='utf-8'))
            if ticker not in submissions.get('tickers', []):
                raise ValueError('ticker_cik_mismatch')
            body.update(status='complete', captured_at=result.captured_at_utc,
                        company_name=result.builder_source_bindings[0].legal_name,
                        sources=[{'kind': a.source_kind, 'url': a.source_url,
                                  'sha256': a.raw_response_sha256, 'bytes': a.raw_response_bytes}
                                 for a in result.artifacts])
        except Exception as exc:
            # No exception text, credentials, or local paths in the product response.
            code = exc.code if isinstance(exc, SecSnapshotError) else (
                'ticker_cik_mismatch' if isinstance(exc, ValueError) and str(exc)=='ticker_cik_mismatch'
                else 'sec_snapshot_processing_failed')
            body.update(status='failed', failure_code=code)
        with self.library.documents.connect() as db:
            db.execute('UPDATE project_sec_versions SET body=? WHERE scope=? AND version=?',
                       (json.dumps(body), scope, version))
        return body

    def _saved(self, owner, project, version):
        scope = self.library.scope(owner, project)
        version = str(UUID(str(version)))
        with self.library.documents.connect() as db:
            row = db.execute('SELECT body FROM project_sec_versions WHERE scope=? AND version=?', (scope, version)).fetchone()
        if not row: raise KeyError('数据版本不存在')
        body = json.loads(row['body'])
        if body['status'] != 'complete': raise ValueError('该版本尚未完成，不能作为可用数据读取。')
        return body, self.root / scope / version

    def raw(self, owner, project, version, kind):
        body, root = self._saved(owner, project, version)
        source = next((s for s in body['sources'] if s['kind'] == kind), None)
        if source is None: raise KeyError('数据原件不存在')
        raw = (root / 'raw' / body['ticker'] / (kind + '.json')).read_bytes()
        if sha256(raw).hexdigest() != source['sha256']:
            raise ValueError('保存的数据校验失败，请保留该版本并重新同步。')
        return raw, source

    def observations(self, owner, project, version, taxonomy='', tag='', as_of='', offset=0):
        raw, source = self.raw(owner, project, version, 'sec_companyfacts')
        payload = json.loads(raw, parse_float=Decimal)
        facts = payload['facts']
        concepts = [{'taxonomy': ns, 'tag': name, 'label': value.get('label', name)}
                    for ns, tags in facts.items() for name, value in tags.items()]
        if not taxonomy or not tag:
            return {'concepts': concepts, 'items': [], 'total': 0, 'source': source, 'numeric_fact_authority': False}
        concept = facts.get(taxonomy, {}).get(tag)
        if concept is None: raise KeyError('该版本中没有此指标；不代表公司未披露。')
        rows = []
        for unit, values in concept['units'].items():
            for position, value in enumerate(values):
                filed = value.get('filed', '')
                # Date filtering is explicitly filing-date-only, not intraday PIT.
                if as_of and (not filed or filed > as_of): continue
                rows.append({**value, 'val': str(value['val']), 'unit': unit, 'locator': {'taxonomy': taxonomy, 'tag': tag,
                             'unit': unit, 'observation_index': position}})
        rows.sort(key=lambda r: (r.get('filed', ''), r.get('end', ''), r.get('start', ''), r.get('accn', '')), reverse=True)
        return {'concepts': [], 'items': rows[offset:offset+50], 'total': len(rows), 'offset': offset,
                'next_offset': offset+50 if offset+50<len(rows) else None,
                'source': source, 'as_of': as_of, 'time_filter': 'SEC_filed_date_inclusive_only',
                'numeric_fact_authority': False,
                'notice': 'SEC原始观测，未归一化或裁定事实权限。保留重复/修订及原始单位；fy/fp是披露所属财年标签，期间以start/end为准。日期筛选仅按filed，不是盘中历史时点核验。'}
