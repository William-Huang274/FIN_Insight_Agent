"""Source-first labels and production-response scoring for organization retrieval.

This module never supplies permission grants or substitutes a retrieval engine.
The caller owns real service setup, frozen releases, successful query receipts,
and current authorization. Large datasets and results stay outside Git.
"""
from collections import defaultdict
from hashlib import sha256
import json
from time import perf_counter

from scripts.engineering.qualify_retrieval_recall import ranking_metrics
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_source_projection import chunk_node_id, validate_source_cutoff
from scripts.engineering.retrieval_evaluation_freeze import LEGACY_POLICY, strategy_from_policy

POLICY = LEGACY_POLICY


def verify_equivalent_quote(anchor, original, alternative, candidate):
    """Conservative label equivalence, never inferred from retrieval ranks.

    Require the same exact nonempty original URL, publication/availability,
    snapshot, and full quoted text (only whitespace may differ). Matching facts
    in another quarter's report or a later revision do not satisfy this rule.
    """
    left, right = original['source'], candidate['source']
    if (not left['url'] or left['url'] != right['url']
            or original['library_sha256'] != candidate['library_sha256']
            or any(left[k] != right[k] for k in ('published_at', 'vintage'))
            or json.loads(left['metadata']).get('known_at') != json.loads(right['metadata']).get('known_at')):
        raise ValueError('equivalent_evidence_source_version_mismatch')
    quote = ' '.join(anchor['quote'].split())
    if not quote:
        raise ValueError('equivalent_evidence_empty_quote')
    for label, bundle in ((anchor, original), (alternative, candidate)):
        if label['source_id'] != bundle['source']['id']:
            raise ValueError('equivalent_evidence_source_identity_mismatch')
        chunks = [c for c in bundle['chunks'] if c['id'] == label['chunk_id']]
        if len(chunks) != 1:
            raise ValueError('equivalent_evidence_chunk_missing')
        chunk = chunks[0]
        actual = sha256(chunk['body'].encode()).hexdigest()
        if actual != label['body_sha256'] or actual != chunk['digest']:
            raise ValueError('equivalent_evidence_body_changed')
        if quote not in ' '.join(chunk['body'].split()):
            raise ValueError('equivalent_evidence_quote_not_identical')


def evidence_group_metrics(ranked, groups, ks=(5, 10, 20, 40)):
    """OR within verified equivalent copies, AND across required evidence units."""
    if not groups or any(not group for group in groups):
        raise ValueError('positive_evidence_groups_required')
    positions = {node: rank for rank, node in enumerate(dict.fromkeys(ranked), 1)}
    ranks = [min((positions[node] for node in set(group) if node in positions), default=None) for group in groups]
    hits = [rank for rank in ranks if rank is not None]
    return {**{f'known_recall@{k}': sum(rank <= k for rank in hits)/len(groups) for k in ks},
            **{f'known_hit@{k}': float(any(rank <= k for rank in hits)) for k in ks},
            **{f'all_known_hit@{k}': float(sum(rank <= k for rank in hits) == len(groups)) for k in ks},
            'mrr@40': 1/min(hits) if hits and min(hits) <= 40 else 0.}


def validate_questions(dataset, bundles):
    """Check originals before retrieval; never infer labels from ranked results."""
    rows = dataset['questions']
    role = dataset['evaluation_role']
    if role not in {'historical_regression', 'independent_source_first'}:
        raise ValueError('unknown_evaluation_role')
    if role == 'independent_source_first':
        if not dataset.get('policy'):
            raise ValueError('frozen_evaluation_policy_mismatch')
        try:strategy_from_policy(dataset['policy'])
        except ValueError:raise ValueError('frozen_evaluation_policy_mismatch') from None
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
            for alternative in label.get('equivalents', []):
                other = alternative['source_id']
                if role == 'independent_source_first' and sources.setdefault(other, split) != split:
                    raise ValueError('source_crosses_independent_splits')
                verify_equivalent_quote(label, bundle, alternative, bundles[alternative['source_id']])
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


def bind_label_groups(rows, manifest, resources, index):
    """Bind reviewed exact-quote copies as OR; separate required labels as AND.

    validate_questions must verify each alternative against original source
    versions first. This maps identities, it never discovers equivalence.
    """
    expanded_rows, lengths = [], {}
    for row in rows:
        expanded, sizes = [], []
        for label in row['evidence']:
            copies = [label, *label.get('equivalents', [])]
            expanded.extend(copies); sizes.append(len(copies))
        expanded_rows.append({**row, 'evidence': expanded})
        lengths[row['id']] = sizes
    mapped = bind_labels(expanded_rows, manifest, resources, index)
    groups = {}
    for key, sizes in lengths.items():
        groups[key] = []; offset = 0
        for size in sizes:
            groups[key].append(list(dict.fromkeys(mapped[key][offset:offset+size])))
            offset += size
    return groups


def score_response(result, gold, *, index_digest, graph=False, strategy=None):
    """Candidate recall is not Agent-visible recall; keep both rankings intact."""
    if not result.items:
        raise ValueError('empty_response_requires_explicit_execution_diagnosis')
    receipt = result.items[0]['retrieval']
    strategy = strategy_from_policy(strategy)
    if receipt['index_digest'] != index_digest:
        raise ValueError('response_index_mismatch')
    mode = 'organization-cosine-bm25-graph-rrf.v1' if graph else 'organization-cosine-bm25-rrf.v1'
    if strategy['reranker']:
        mode = mode.replace('-rrf.v1','-qwen-rerank.v1')
        if receipt.get('rerank_response',{}).get('model') != strategy['reranker']:
            raise ValueError('response_rerank_model_mismatch')
    if receipt['mode'] != mode:
        raise ValueError('response_policy_mismatch')
    if receipt.get('candidate_policy','balanced.v1') != strategy['candidate_policy']:
        raise ValueError('response_candidate_policy_mismatch')
    actual_plan = getattr(result,'organization_query_plan',None)
    if (actual_plan or {}).get('policy') != strategy['query_planning']:
        raise ValueError('response_query_plan_mismatch')
    if actual_plan and actual_plan.get('metadata_policy') != strategy['metadata_policy']:
        raise ValueError('response_metadata_policy_mismatch')
    rankings = {name: list(receipt[field]) for name, field in (
        ('dense_candidates', 'dense_node_ids'), ('lexical_candidates', 'lexical_node_ids'),
        ('fused_candidates', 'candidate_node_ids'))}
    if graph:
        rankings['graph_candidates'] = list(receipt['graph_node_ids'])
    rankings['returned'] = [item['node_id'] for item in result.items]
    from retrieval.candidate_policy import candidate_limits
    limits = candidate_limits(strategy['candidate_policy'],has_graph=graph)
    for channel, maximum in (('dense_candidates', limits['dense']), ('lexical_candidates', limits['lexical']),
                             ('graph_candidates', limits['graph']), ('returned', strategy['returned_limit'])):
        if len(rankings.get(channel, [])) > maximum:
            raise ValueError('response_policy_quota_mismatch')
    if any(len(ids) != len(set(ids)) for ids in rankings.values()):
        raise ValueError('duplicate_ranked_node')
    candidates = set(rankings['fused_candidates'])
    if len(candidates)>sum(limits.values()):
        raise ValueError('response_policy_quota_mismatch')
    if strategy['reranker']:
        ranked = receipt.get('reranked_node_ids',[])
        if len(ranked)!=len(set(ranked)) or set(ranked)!=candidates:
            raise ValueError('reranked_candidates_differ_from_union')
        rankings['reranked_candidates'] = list(ranked)
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


def evaluate(rows, labels, navigation, *, index_digest, save, graph=False, strategy=None):
    """Real authorized navigator; fixed full-corpus search, explicit limit=20.

    Optional frozen query planning uses the serving path. No label-derived
    filter, retry, or provider fallback. Persist each request including failure.
    """
    strategy = strategy_from_policy(strategy)
    samples = []
    expected = [r['id'] for r in rows]
    for row in rows:
        sample = {k: row[k] for k in ('id', 'family', 'split', 'query')}
        request = {'source_space': 'organization', 'operation': 'search', 'query': row['query'], 'limit': 20}
        if strategy['query_planning']:
            request['organization_query_planning'] = strategy['query_planning']
            request['organization_metadata_policy'] = strategy['metadata_policy']
        if graph:
            request['entity_id'] = row['entity_id']
        sample['request'] = request
        started = perf_counter()
        try:
            sample.update(score_response(navigation.navigate(request), labels[row['id']],
                                         index_digest=index_digest, graph=graph,
                                         strategy=strategy), status='completed')
        except Exception as exc:
            sample.update(status='failed', error_type=type(exc).__name__)
            raise
        finally:
            sample['elapsed_seconds'] = perf_counter() - started
            samples.append(sample)
            save('semantic-' + ('graph' if graph else 'hybrid'), {'samples': samples,
                'summary': summarize(samples, expected), 'labels_are_exhaustive': False,
                'strategy': strategy,
                'financial_answer_quality_assessed': False})
    return samples
