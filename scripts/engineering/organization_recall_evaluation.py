"""Source-first labels and production-response scoring for organization retrieval.

This module never supplies permission grants or substitutes a retrieval engine.
The caller owns real service setup, frozen releases, successful query receipts,
and current authorization. Large datasets and results stay outside Git.
"""
from collections import defaultdict
from hashlib import sha256
from time import perf_counter

from scripts.engineering.qualify_retrieval_recall import ranking_metrics
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_source_projection import chunk_node_id, validate_source_cutoff

POLICY = {'dense_candidates': 24, 'lexical_candidates': 12, 'graph_candidates': 12,
          'fusion': 'rrf_k60', 'returned_limit': 20}


def validate_questions(dataset, bundles):
    """Check originals before retrieval; never infer labels from ranked results."""
    rows = dataset['questions']
    role = dataset['evaluation_role']
    if role not in {'historical_regression', 'independent_source_first'}:
        raise ValueError('unknown_evaluation_role')
    if role == 'independent_source_first' and dataset.get('policy') != POLICY:
        raise ValueError('frozen_evaluation_policy_mismatch')
    if not rows or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('empty_or_duplicate_questions')
    families, sources = {}, {}
    for row in rows:
        split = row['split']
        if split not in {'development', 'heldout'} or not row['family']:
            raise ValueError('invalid_split_or_family')
        if not 0 < len(row['query'].encode('utf8')) <= 8192 or not row['query'].strip():
            raise ValueError('invalid_query')
        if families.setdefault(row['family'], split) != split:
            raise ValueError('family_crosses_splits')
        evidence = row['evidence']
        identities = {(e['source_id'], e['chunk_id']) for e in evidence}
        if not evidence or len(identities) != len(evidence):
            raise ValueError('positive_unique_evidence_required')
        if row.get('entity_id') and (not row.get('entity_alias') or
                row['entity_alias'].casefold() not in row['query'].casefold()):
            raise ValueError('graph_entity_must_be_explicit_in_question')
        for label in evidence:
            sid = label['source_id']
            if role == 'independent_source_first' and sources.setdefault(sid, split) != split:
                raise ValueError('source_crosses_independent_splits')
            bundle = bundles[sid]
            if bundle['source']['id'] != sid or bundle['library_sha256'] != dataset['library_sha256']:
                raise ValueError('label_source_snapshot_mismatch')
            validate_source_cutoff(bundle, row['as_of'])
            matches = [c for c in bundle['chunks'] if c['id'] == label['chunk_id']]
            if len(matches) != 1:
                raise ValueError('label_chunk_missing_or_ambiguous')
            chunk = matches[0]
            digest = sha256(chunk['body'].encode('utf8')).hexdigest()
            if digest != label['body_sha256'] or digest != chunk['digest']:
                raise ValueError('label_body_digest_mismatch')
            if not label['quote'].strip() or label['quote'] not in chunk['body']:
                raise ValueError('label_quote_not_in_original')
            if row.get('entity_id'):
                # A question's explicit entity must have a source-bound edge
                # in its gold document, not an unrelated graph plumbing probe.
                edges = {e['id'] for e in bundle['edges'] if row['entity_id'] in
                         (e['subject'], e['object']) and e['status'] != 'needs_semantic_review'}
                if not any(link['edge_id'] in edges for link in bundle['edge_chunk_links']):
                    raise ValueError('graph_entity_has_no_bound_source_edge')
    return rows


def bind_labels(rows, manifest, resources, index):
    """Map source/chunk identities to the exact frozen organization publication."""
    documents = {item['resource_id']: OrganizationSourceNavigation._identity(item)
                 for item in manifest['inputs']}
    records = {r['node_id']: r for r in index['records']}
    if len(records) != len(index['records']):
        raise ValueError('duplicate_index_node')
    mapped = {}
    for row in rows:
        if row['as_of'] != manifest['research_as_of']:
            raise ValueError('evaluation_cutoff_must_match_frozen_research')
        labels = []
        for label in row['evidence']:
            document = documents[resources[label['source_id']]]
            node = chunk_node_id(document, label['chunk_id']) + ':leaf'
            record = records.get(node)
            if record is None or record['document_id'] != document or record['content_sha256'] != label['body_sha256']:
                raise ValueError('label_not_in_frozen_index')
            labels.append(node)
        mapped[row['id']] = labels
    return mapped


def score_response(result, gold, *, index_digest, graph=False):
    """Candidate recall is not Agent-visible recall; keep both rankings intact."""
    if not result.items:
        raise ValueError('empty_response_requires_explicit_execution_diagnosis')
    receipt = result.items[0]['retrieval']
    if receipt['index_digest'] != index_digest:
        raise ValueError('response_index_mismatch')
    mode = 'organization-cosine-bm25-graph-rrf.v1' if graph else 'organization-cosine-bm25-rrf.v1'
    if receipt['mode'] != mode:
        raise ValueError('response_policy_mismatch')
    rankings = {name: list(receipt[field]) for name, field in (
        ('dense_candidates', 'dense_node_ids'), ('lexical_candidates', 'lexical_node_ids'),
        ('fused_candidates', 'candidate_node_ids'))}
    if graph:
        rankings['graph_candidates'] = list(receipt['graph_node_ids'])
    rankings['returned'] = [item['node_id'] for item in result.items]
    for channel, maximum in (('dense_candidates', 24), ('lexical_candidates', 12),
                             ('graph_candidates', 12), ('returned', 20)):
        if len(rankings.get(channel, [])) > maximum:
            raise ValueError('response_policy_quota_mismatch')
    if any(len(ids) != len(set(ids)) for ids in rankings.values()):
        raise ValueError('duplicate_ranked_node')
    candidates = set(rankings['fused_candidates'])
    if not set(rankings['returned']) <= candidates:
        raise ValueError('returned_node_outside_frozen_candidates')
    return {'rankings': rankings, 'metrics': {name: ranking_metrics(ids, gold,
        ks=(5, 8, 10, 20) if name == 'returned' else (5, 10, 20, 40))
        for name, ids in rankings.items()}, 'receipt': receipt}


def summarize(samples, expected_ids):
    """Keep errors in the denominator and do not publish partial-run recall."""
    if len({s['id'] for s in samples}) != len(samples) or not {s['id'] for s in samples} <= set(expected_ids):
        raise ValueError('unexpected_or_duplicate_samples')
    complete = len(samples) == len(expected_ids) and all(s['status'] == 'completed' for s in samples)
    out = {'status': 'completed' if complete else 'incomplete', 'expected': len(expected_ids),
           'completed': sum(s['status'] == 'completed' for s in samples),
           'failed': sum(s['status'] == 'failed' for s in samples), 'metrics': None}
    if not complete:
        return out
    # Mean per family prevents correlated paraphrases dominating the headline.
    grouped = defaultdict(list)
    for sample in samples:
        grouped[sample['family']].append(sample)
    channels = set(samples[0]['metrics'])
    if any(set(s['metrics']) != channels for s in samples):
        raise ValueError('mixed_route_metrics_require_separate_cohorts')
    out['families'] = len(grouped)
    out['metrics'] = {channel: {metric: {
        'question_mean': sum(s['metrics'][channel][metric] for s in samples) / len(samples),
        'family_mean': sum(sum(s['metrics'][channel][metric] for s in family) / len(family)
                           for family in grouped.values()) / len(grouped)}
        for metric in samples[0]['metrics'][channel]} for channel in sorted(channels)}
    return out


def evaluate(rows, labels, navigation, *, index_digest, save, graph=False):
    """Real authorized navigator; fixed full-corpus search, explicit limit=20.

    No query rewrite, document prefilter, retry, or provider fallback. Persist
    each request including failure before returning control to the harness.
    """
    samples = []
    expected = [r['id'] for r in rows]
    for row in rows:
        sample = {k: row[k] for k in ('id', 'family', 'split', 'query')}
        request = {'source_space': 'organization', 'operation': 'search', 'query': row['query'], 'limit': 20}
        if graph:
            request['entity_id'] = row['entity_id']
        sample['request'] = request
        started = perf_counter()
        try:
            sample.update(score_response(navigation.navigate(request), labels[row['id']],
                                         index_digest=index_digest, graph=graph), status='completed')
        except Exception as exc:
            sample.update(status='failed', error_type=type(exc).__name__)
            raise
        finally:
            sample['elapsed_seconds'] = perf_counter() - started
            samples.append(sample)
            save('semantic-' + ('graph' if graph else 'hybrid'), {'samples': samples,
                'summary': summarize(samples, expected), 'labels_are_exhaustive': False,
                'financial_answer_quality_assessed': False})
    return samples
