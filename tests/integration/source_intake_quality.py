"""Opt-in frozen retrieval replay through the actual organization navigator.

Labels are used only for scoring. This driver never constructs candidates from
gold, replaces a provider response, retries a request, or measures Agent quality.
"""
from contextvars import ContextVar
from hashlib import sha256
import json
from pathlib import Path
import re
from time import perf_counter


provider_network = ContextVar('qualification_provider_network', default=False)


class PaidCallBudget:
    """Allow external I/O only inside explicitly counted provider methods."""
    def __init__(self, limit, save):
        self.limit, self.save = limit, save
        self.calls = {'embedding': 0, 'rerank': 0}
        self.failed = False

    def wrap(self, operation, method):
        def call(*args, **kwargs):
            if self.failed or self.calls[operation] >= self.limit:
                raise RuntimeError('service_quality_budget_or_failed_request_stop')
            self.calls[operation] += 1
            self.save('service-quality-provider-budget', self.record('submitted'))
            token = provider_network.set(True)
            try:
                result = method(*args, **kwargs)
            except BaseException:
                self.failed = True
                self.save('service-quality-provider-budget', self.record('failed_usage_unknown'))
                raise
            finally:
                provider_network.reset(token)
            self.save('service-quality-provider-budget', self.record('completed'))
            return result
        return call

    def record(self, status):
        return {'status': status, 'calls': dict(self.calls), 'failed': self.failed,
                'per_operation_limit': self.limit, 'automatic_retries': 0}


def load_frozen_quality(directory, expected_sha256, bundles):
    root = Path(directory)
    raw = (root/'dataset.json').read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('service_quality_dataset_digest_mismatch')
    data = json.loads(raw)
    plan = json.loads((root/'plan.json').read_text(encoding='utf8'))
    summary = json.loads((root/'summary.json').read_text(encoding='utf8'))
    questions = data['questions']
    policy = data['freeze']['ranking_policy']
    if (plan['dataset_sha256'] != expected_sha256 or data['freeze']['status'] != 'frozen'
            or summary.get('batch_quality_passed') is not True
            or summary.get('execution_status') != 'completed'
            or summary['executed'] != len(questions) or summary['expected'] != len(questions)
            or {r['id'] for r in summary['rows']} != {q['id'] for q in questions}
            or len({q['id'] for q in questions}) != len(questions)
            or not 1 <= len(questions) <= 100):
        raise ValueError('service_quality_requires_completed_frozen_batch')
    if plan['sources'] != len(bundles):
        raise ValueError('service_quality_incomplete_source_scope')
    if policy != {'candidate_policy': 'needs_window.v4', 'query_planning': 'conservative.v5',
                  'metadata_policy': 'sec_cover.v2', 'reranker': 'qwen3.7-text-rerank',
                  'returned_limit': 20}:
        raise ValueError('service_quality_policy_not_supported')
    from scripts.engineering.retrieval_evidence_spans import cover_reviewed_span
    for q in questions:
        if (not re.fullmatch(r'[a-zA-Z0-9_-]{1,160}', q['id'])
                or q['question_kind'] not in {'positive_fact_request', 'false_premise_corrective_evidence'}):
            raise ValueError('service_quality_question_contract_invalid')
        if not q['reviewed_spans']:
            raise ValueError('service_quality_missing_reviewed_spans')
        for span in q['reviewed_spans']:
            bundle = bundles[span['source_id']]
            if span['source_digest'] != bundle['source']['digest']:
                raise ValueError('service_quality_source_version_mismatch')
            cover_reviewed_span(bundle, span['start'], span['end'])
    return data, {'dataset_sha256': expected_sha256,
                  'plan_sha256': sha256((root/'plan.json').read_bytes()).hexdigest(),
                  'summary_sha256': sha256((root/'summary.json').read_bytes()).hexdigest()}


def score_original_spans(question, items, bundles):
    from scripts.engineering.retrieval_evidence_spans import retrieved_span_covered
    grouped = {}
    for item in items[:10]:
        origin = item['original_source']
        bundle = bundles[origin['source_id']]
        if bundle['source']['digest'] != origin['source_digest']:
            raise ValueError('service_quality_result_source_version_mismatch')
        chunk = next((c for c in bundle['chunks'] if c['id'] == origin['id']), None)
        if chunk is None or item['content_sha256'] != chunk['digest']:
            raise ValueError('service_quality_result_chunk_mismatch')
        grouped.setdefault(origin['source_id'], []).append(origin['id'])
    hits = [retrieved_span_covered(bundles[s['source_id']], s['start'], s['end'],
                                  grouped.get(s['source_id'], []))
            for s in question['reviewed_spans']]
    return {'complete10': all(hits), 'span_recall10': sum(hits)/len(hits), 'span_hits': hits}


def run_quality(data, binding, *, nav, bundles, save, budget):
    """Navigator is the production instance with actual Java authority reader."""
    rows = []
    basis = {'purpose': 'Replay a frozen quality batch through current organization authorization',
        'input_scale': {'queries': len(data['questions']), 'sources': len(bundles)},
        'required_output': 'Ranked original IDs, live readbacks, source-span scores and provider receipts',
        'quality_risk': 'Correlated queries; service parity is not a new independent test or capacity metric',
        'reasoning_profile': 'Qwen embedding and rerank only; no generated answer or Agent',
        'limits': {'embedding_requests': budget.limit, 'rerank_requests': budget.limit,
                   'concurrency': 1, 'automatic_retries': 0},
        'stop_behavior': 'Stop at first execution failure; retain failed and unknown usage, never resubmit'}
    report = {'status': 'running', 'binding': binding, 'rows': rows, 'TokenBudgetBasis': basis,
              'capacity_assessed': False, 'Agent_answer_quality_assessed': False, 'S2_passed': False}
    save('service-quality', report)
    try:
        for q in data['questions']:
            before, manifest, _ = nav.reader._grant()
            if manifest['research_as_of'] != q['as_of']:
                raise ValueError('service_quality_asof_mismatch')
            nav.reader._after(before)
            request = {'source_space': 'organization', 'operation': 'search', 'query': q['query'],
                       'limit': 20, 'organization_metadata_policy': 'sec_cover.v2',
                       'organization_query_planning': 'conservative.v5'}
            started = perf_counter()
            result = nav.navigate(request)
            elapsed = perf_counter()-started
            if result.items:
                receipt = result.items[0]['retrieval']
                if (receipt.get('candidate_policy') != 'needs_window.v4'
                        or receipt.get('rerank') != 'qwen3.7-text-rerank'
                        or receipt.get('index_digest') != manifest['retrieval_index']['index_digest']):
                    raise ValueError('service_quality_executed_policy_or_index_mismatch')
            # Read all returned top-ten originals, never just labelled answers.
            originals = []
            for item in result.items[:10]:
                read = nav.navigate({'source_space': 'organization', 'operation': 'read',
                    'document_id': item['document_id'], 'node_id': item['node_id'],
                    'max_characters': 16000})
                if (len(read.items) != 1 or read.items[0].get('truncated')
                        or read.items[0]['original_source'] != item['original_source']
                        or read.items[0].get('result_state') != 'source_bound_passage'):
                    raise ValueError('service_quality_original_readback_mismatch')
                originals.append(read.items[0])
            rows.append({'id': q['id'], 'family': q['family'], 'kind': q['question_kind'],
                         'search_seconds': elapsed, 'request': request,
                         **score_original_spans(q, originals, bundles)})
            save('service-quality-question-'+q['id'], {
                'search': result.model_dump(mode='json'), 'originals': originals})
            save('service-quality', report)
        groups = {}
        for kind in {r['kind'] for r in rows}:
            selected = [r for r in rows if r['kind'] == kind]
            families = {}
            for row in selected:
                families.setdefault(row['family'], []).append(row)
            groups[kind] = {'questions': len(selected),
                'complete10': sum(r['complete10'] for r in selected),
                'family_macro_complete10': sum(sum(r['complete10'] for r in f)/len(f)
                                               for f in families.values())/len(families),
                'family_macro_span_recall10': sum(sum(r['span_recall10'] for r in f)/len(f)
                                                  for f in families.values())/len(families)}
        gates = data['freeze']['acceptance']
        passed = all(g['family_macro_complete10'] >= gates[
            'positive_complete_evidence_at10' if k == 'positive_fact_request'
            else 'counterclaim_corrective_evidence_at10']
            and g['family_macro_span_recall10'] >= gates['known_group_recall_at10']
            for k, g in groups.items())
        report.update(status='completed', by_kind=groups, batch_quality_passed=passed)
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        report['provider_budget'] = budget.record('failed' if budget.failed else 'observed')
        save('service-quality', report)
    if not passed:
        raise AssertionError('service_quality_frozen_batch_gate_failed')
    return [r['request'] for r in rows]
