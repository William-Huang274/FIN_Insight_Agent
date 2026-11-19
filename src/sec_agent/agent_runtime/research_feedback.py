"""Source-bound research questions and user opinions, never published graph edits."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .research_graph_contracts import canonical_sha256


class ResearchIssue(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    issue_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,60}$')
    kind: Literal['relation_scope', 'identity', 'direction', 'time_status', 'insufficient_evidence',
                  'conflicting_evidence', 'new_relation', 'external_evidence']
    summary: str = Field(min_length=8, max_length=1600)
    read_refs: tuple[str, ...] = Field(min_length=1, max_length=8)
    edge_ids: tuple[str, ...] = Field(default=(), max_length=8)
    impact: Literal['not_used', 'independent_search', 'plan_changed', 'no_current_impact']
    next_check: str = Field(min_length=5, max_length=1600)


class ReportResearchIssuesAction(BaseModel):
    """Save a few concrete evidence doubts, new relation candidates or external-source needs. Nonblocking; never edit the graph. Cite observed O references; unread originals are allowed but not disproved."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    context_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    issues: tuple[ResearchIssue, ...] = Field(min_length=1, max_length=4)


def _edge_ids(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'edge_id', 'relation_id'} and isinstance(item, str):
                yield item
            if key == 'id' and isinstance(item, str) and ('predicate' in value or item.startswith(('EDGE::', 'RELATION::'))):
                yield item
            yield from _edge_ids(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _edge_ids(item)


def bind_issues(action, observations, *, run_id, snapshot_id, library_sha256=None):
    observed = {row.get('read_ref'): row for row in observations}
    records = []
    if len({i.issue_id for i in action.issues}) != len(action.issues):
        raise ValueError('feedback_issue_ids_must_be_unique')
    for issue in action.issues:
        if not set(issue.read_refs).issubset(observed):
            raise ValueError('feedback_requires_observed_read_refs')
        refs = {ref: observed[ref] for ref in issue.read_refs}
        if not set(issue.edge_ids).issubset(set(_edge_ids(list(refs.values())))):
            raise ValueError('feedback_edge_not_in_referenced_results')
        evidence = {ref: {'selection': row['selection'], 'result_digest': canonical_sha256(row['result']),
            'preview': [{key: str(item[key])[:1200] for key in
                ('title', 'passage', 'snippet', 'predicate', 'subject', 'object', 'document_id', 'passage_id')
                if item.get(key) is not None} for item in row['result'].get('items', [])[:4]],
            'original_read': row['selection'].get('operation') == 'read'
                and row['result'].get('status') == 'success'
                and any(r.get('result_state') == 'source_bound_passage' and r.get('passage')
                        for r in row['result'].get('items', []))}
            for ref, row in refs.items()}
        body = {**issue.model_dump(mode='json'), 'run_id': run_id, 'snapshot_id': snapshot_id,
                'library_sha256': library_sha256,
                'evidence': evidence, 'status': 'pending_review', 'changes_published_graph': False}
        body['record_id'] = canonical_sha256({'run_id': run_id, 'issue_id': issue.issue_id})
        body['content_digest'] = canonical_sha256(body)
        records.append(body)
    return records


class FeedbackChoice(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    submission_id: str = Field(pattern=r'^[A-Za-z0-9_-]{8,100}$')
    content_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    choice: Literal['keep_pending', 'avoid_inference', 'request_check']
    comment: str = Field(default='', max_length=3000)


class ResearchFeedbackStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS research_feedback (
                    owner TEXT NOT NULL, thread TEXT NOT NULL, record_id TEXT NOT NULL,
                    run_id TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(owner,thread,record_id));
                CREATE TABLE IF NOT EXISTS research_feedback_opinions (
                    owner TEXT NOT NULL, thread TEXT NOT NULL, submission_id TEXT NOT NULL,
                    record_id TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(owner,thread,submission_id));
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, owner, thread, records):
        with self.connect() as db:
            for record in records:
                body = json.dumps(record, ensure_ascii=False, sort_keys=True)
                prior = db.execute('SELECT body FROM research_feedback WHERE owner=? AND thread=? AND record_id=?',
                                   (owner, thread, record['record_id'])).fetchone()
                if prior and prior['body'] != body:
                    raise ValueError('feedback_id_already_used_for_different_content')
                if not prior:
                    db.execute('INSERT INTO research_feedback VALUES (?,?,?,?,?)',
                               (owner, thread, record['record_id'], record['run_id'], body))
        return records

    def list(self, owner, thread, run_id=None):
        with self.connect() as db:
            rows = db.execute('SELECT body FROM research_feedback WHERE owner=? AND thread=?'
                              + (' AND run_id=?' if run_id else '') + ' ORDER BY rowid',
                              (owner, thread, run_id) if run_id else (owner, thread)).fetchall()
            opinions = db.execute('SELECT record_id,body FROM research_feedback_opinions WHERE owner=? AND thread=? ORDER BY rowid',
                                  (owner, thread)).fetchall()
        latest = {r['record_id']: json.loads(r['body']) for r in opinions}
        return [{**json.loads(r['body']), 'user_opinion': latest.get(json.loads(r['body'])['record_id'])} for r in rows]

    def choose(self, owner, thread, record_id, choice):
        payload = choice.model_dump(mode='json')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM research_feedback WHERE owner=? AND thread=? AND record_id=?',
                             (owner, thread, record_id)).fetchone()
            if not row:
                raise KeyError('feedback_not_found')
            if json.loads(row['body'])['content_digest'] != choice.content_digest:
                raise ValueError('feedback_version_mismatch')
            prior = db.execute('SELECT record_id,body FROM research_feedback_opinions WHERE owner=? AND thread=? AND submission_id=?',
                               (owner, thread, choice.submission_id)).fetchone()
            if prior:
                saved = json.loads(prior['body'])
                if prior['record_id'] != record_id or any(saved[k] != v for k, v in payload.items()):
                    raise ValueError('feedback_submission_id_conflict')
                return saved
            payload.update(recorded_at=datetime.now(timezone.utc).isoformat(), execution_status='recorded_not_executed')
            db.execute('INSERT INTO research_feedback_opinions VALUES (?,?,?,?,?)',
                       (owner, thread, choice.submission_id, record_id, json.dumps(payload, ensure_ascii=False)))
        return payload
