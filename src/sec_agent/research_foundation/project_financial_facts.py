"""Bind one selected SEC version to the existing financial kernel for a task.

Raw files and the derived SQLite mart are copied into the task's own namespace.
Only a persisted, ready binding can replace that task's default financial reader.
"""
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID

from financial_facts import CompanyFactMartPolicy, CompanySourceBinding, MetricDefinition
from financial_facts.mart import build_company_fact_mart
from .task_attachments import TaskAttachmentStore
from .project_asset_access import bind_project_store, origin_access, require_active


MAPPING_ID = 'sec_us_gaap_income_usd_v1'
METRICS = (
    MetricDefinition('revenue', 'currency', (('us-gaap', 'RevenueFromContractWithCustomerExcludingAssessedTax'),), ('USD',)),
    MetricDefinition('operating_income', 'currency', (('us-gaap', 'OperatingIncomeLoss'),), ('USD',)),
)


def prepare_task_financial_snapshot(sec, owner, project, version, task_root, thread):
    body, source_root = sec._saved(owner, project, version)
    # Verify both original bytes before a task is given a financial binding.
    originals = {kind: sec.raw(owner, project, version, kind)[0]
                 for kind in ('sec_companyfacts', 'sec_submissions')}
    store = TaskAttachmentStore(task_root)
    thread = str(UUID(str(thread)))
    info = {'status': 'preparing', 'mapping_id': MAPPING_ID,
            'project_origin': {'project_id': str(project), 'source_scope': sec.library.scope(owner, project), 'sec_version': str(version),
                               'ticker': body['ticker'], 'cik': body['cik']},
            'source_capture_at': body['captured_at'], 'raw_sources': body['sources']}
    with store.connect() as db:
        bind_project_store(db, thread, sec.library.documents.path)
        db.execute('CREATE TABLE IF NOT EXISTS task_financial_snapshots(thread TEXT PRIMARY KEY, body TEXT NOT NULL)')
        db.execute('INSERT INTO task_financial_snapshots VALUES(?,?)', (thread, json.dumps(info)))
    target = store.root / 'financial-snapshots' / thread
    try:
        target.mkdir(parents=True, exist_ok=False)
        metadata = {}
        for kind, raw in originals.items():
            (target / f'{kind}.json').write_bytes(raw)
            meta = json.loads((source_root / 'raw' / body['ticker'] / f'{kind}.metadata.json').read_text(encoding='utf-8'))
            (target / f'{kind}.metadata.json').write_text(json.dumps(meta), encoding='utf-8')
            metadata[kind] = meta
        source = CompanySourceBinding(ticker=body['ticker'], cik=body['cik'], legal_name=body['company_name'],
            companyfacts_ref='sec_companyfacts.json', companyfacts_metadata_ref='sec_companyfacts.metadata.json',
            companyfacts_sha256=metadata['sec_companyfacts']['canonical_json_sha256'],
            submissions_ref='sec_submissions.json', submissions_metadata_ref='sec_submissions.metadata.json',
            submissions_sha256=metadata['sec_submissions']['canonical_json_sha256'])
        policy = CompanyFactMartPolicy(recorded_at=datetime.now(timezone.utc).isoformat(),
            research_as_of=body['captured_at'][:10], minimum_period_end='1990-01-01',
            allowed_forms=('10-K','10-Q'), sources=(source,), metrics=METRICS,
            acceptance_qrels=(), authority={'raw_capture_digest_required': True, 'accepted_at_required': True,
                'preserve_all_vintages': True, 'fact_signal_context_mixed_table_forbidden': True,
                'typed_conflict_fails_closed': True})
        result = build_company_fact_mart(policy, repository_root=target, sqlite_path=target/'facts.sqlite')
        (target/'build-result.json').write_text(json.dumps(result), encoding='utf-8')
        info.update(status='ready', mart_sha256=result['storage']['sqlite_sha256'],
                    counts=result['counts'], source_summary=result['source_summary'],
                    metric_definitions=[asdict(m) for m in METRICS],
                    boundary='Two mapped USD income metrics; all other tags remain raw. Missing filing identity/unsupported period is a capture or mapping boundary, not proved non-disclosure. Derived values use existing kernel contracts; raw observations are not automatically NumericFacts.')
    except Exception:
        info['status'] = 'failed'
        raise
    finally:
        with store.connect() as db:
            db.execute('UPDATE task_financial_snapshots SET body=? WHERE thread=?', (json.dumps(info), thread))
    return info


def task_financial_snapshot(task_root, thread):
    store = TaskAttachmentStore(task_root)
    thread = str(UUID(str(thread)))
    with store.connect() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='task_financial_snapshots'").fetchone():
            return None
        row = db.execute('SELECT body FROM task_financial_snapshots WHERE thread=?', (thread,)).fetchone()
    if row is None: return None
    info = json.loads(row['body'])
    if info['status'] != 'ready': raise ValueError('task_financial_snapshot_not_ready')
    require_active(origin_access(store, thread, info['project_origin'], 'sec'))
    target = store.root / 'financial-snapshots' / thread
    mart = target/'facts.sqlite'
    if not mart.is_file() or sha256(mart.read_bytes()).hexdigest() != info['mart_sha256']:
        raise ValueError('task_financial_snapshot_digest_mismatch')
    for source in info['raw_sources']:
        raw = target / (source['kind'] + '.json')
        if not raw.is_file() or sha256(raw.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('task_financial_original_digest_mismatch')
    return mart, info


def query_task_financial_snapshot(task_root, thread, query, research_as_of):
    from .data_ports import ExistingS2FinancialFactReader
    from .contracts import bind_research_method, load_research_graph_foundation
    selected = task_financial_snapshot(task_root, thread)
    if selected is None: raise ValueError('task_has_no_selected_financial_snapshot')
    path, info = selected
    scope = bind_research_method(load_research_graph_foundation(), ('Q1_ISSUER_TRUTH',),
        research_as_of=datetime.fromisoformat(research_as_of.replace('Z', '+00:00')),
        data_snapshot_id=info['mart_sha256'], execution_attempt_id='project-facts-'+str(thread)).run_scope
    result = ExistingS2FinancialFactReader(path, expected_sha256=info['mart_sha256'])(
        request=query, branch_id='Q1_ISSUER_TRUTH', run_scope=scope)
    return {'project_binding': info, 'query_result': result.model_dump(mode='json')}
