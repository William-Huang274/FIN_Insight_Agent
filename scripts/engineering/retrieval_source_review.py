"""Validate source-first review evidence before a retrieval evaluation freeze.

This validates identity and exact coordinates, not the financial correctness of
the reviewed answer or the equivalence of translated questions.
"""
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json


def validate_source_review(questions, source_files):
    """source_files maps document ID to the exact bytes of its reviewed snapshot."""
    if not questions:
        raise ValueError('review_questions_required')
    sources = {}
    for document, raw in source_files.items():
        source = json.loads(raw)
        if source['source']['document_id'] != document:
            raise ValueError('source_document_identity_mismatch')
        nodes = {}
        for node in source['nodes']:
            identity = node['node_id']
            if identity in nodes:
                raise ValueError('duplicate_original_node')
            if sha256(node['content'].encode()).hexdigest() != node['content_sha256']:
                raise ValueError('original_body_digest_mismatch')
            nodes[identity] = node
        sources[document] = (sha256(raw).hexdigest(), nodes)
    seen_ids = set()
    seen_queries = set()
    families = defaultdict(list)
    proof_count = 0
    for question in questions:
        identity = question['id']
        query = question['query']
        if not isinstance(query, str) or not query.strip():
            raise ValueError('empty_review_query')
        if identity in seen_ids or query in seen_queries:
            raise ValueError('duplicate_review_question')
        seen_ids.add(identity)
        seen_queries.add(query)
        document = question['source_document_id']
        if document not in sources:
            raise ValueError('review_source_missing')
        digest, nodes = sources[document]
        if digest != question['source_review_file_sha256']:
            raise ValueError('source_review_file_changed')
        answerability = question['answerability']
        if answerability not in {'answerable', 'answerable_with_counterevidence'}:
            raise ValueError('absence_requires_separate_bounded_source_audit')
        if question.get('negative_case_kind') == 'false_premise_not_unanswerable' and answerability != 'answerable_with_counterevidence':
            raise ValueError('false_premise_requires_counterevidence')
        evidence = question['required_evidence']
        if not evidence:
            raise ValueError('answer_requires_original_evidence')
        for proof in evidence:
            node = nodes.get(proof['node_id'])
            if node is None:
                raise ValueError('proof_outside_reviewed_source')
            if node['content_sha256'] != proof['body_sha256']:
                raise ValueError('proof_body_digest_mismatch')
            original = node['original_source']
            for field in ('source_id', 'source_digest'):
                if not original.get(field) or original[field] != proof[field]:
                    raise ValueError('proof_original_identity_mismatch')
            original_id = original.get('original_node_id', original.get('id'))
            if not original_id or original_id != proof['original_node_id']:
                raise ValueError('proof_original_node_mismatch')
            offset = original.get('source_char_start', original.get('char_start'))
            start, end = proof['source_char_start'], proof['source_char_end']
            if any(type(n) is not int for n in (offset, start, end)):
                raise ValueError('proof_coordinates_required')
            lo, hi = start - offset, end - offset
            if not 0 <= lo < hi <= len(node['content']):
                raise ValueError('proof_outside_original_interval')
            if node['content'][lo:hi] != proof['quote']:
                raise ValueError('proof_quote_coordinate_mismatch')
            proof_count += 1
        families[question['family']].append(question)
    for siblings in families.values():
        if len(siblings) != 2 or {q['language'] for q in siblings} != {'en', 'zh'}:
            raise ValueError('review_requires_bilingual_pair')
        for field in ('source_document_id', 'required_evidence', 'answerability'):
            if siblings[0][field] != siblings[1][field]:
                raise ValueError('bilingual_evidence_mismatch')
    return {'questions': len(questions), 'families': len(families),
            'reviewed_sources': len({q['source_document_id'] for q in questions}),
            'verified_proof_occurrences': proof_count,
            'financial_correctness_automatically_verified': False,
            'retrieval_executed': False}


def freeze_source_questions(questions, source_files, selection_raw, exposure_raw):
    """Freeze reviewed questions separately from answers, before any ranking.

    This verifies the recorded exposure audit, not an omniscient guarantee that
    a source has never been seen. A later execution freeze must still bind the
    complete serving configuration and the result-pool review protocol.
    """
    review = validate_source_review(questions, source_files)
    selection, exposure = json.loads(selection_raw), json.loads(exposure_raw)
    if selection['source_exposure_audit_sha256'] != sha256(exposure_raw).hexdigest():
        raise ValueError('source_exposure_audit_changed')
    audited = {}
    for row in exposure['documents']:
        identity = row['document_id']
        if identity in audited:
            raise ValueError('duplicate_exposure_document')
        audited[identity] = row
    selected = {}
    excluded_identities = {tuple(identity)
        for row in audited.values() if row['excluded_reasons']
        for identity in row['source_identities']}
    for row in selection['sources']:
        document = row['document_id']
        if document in selected:
            raise ValueError('duplicate_selected_document')
        selected[document] = row
        prior = audited.get(document)
        if prior is None or prior['excluded_reasons']:
            raise ValueError('selected_source_not_eligible')
        identities = {tuple(identity) for identity in prior['source_identities']}
        if not identities or identities & excluded_identities:
            raise ValueError('selected_original_was_exposed')
        if {tuple(identity) for identity in row['source_identities']} != identities:
            raise ValueError('selected_original_identity_changed')
        if document not in source_files:
            raise ValueError('selected_snapshot_missing')
        raw = source_files[document]
        if sha256(raw).hexdigest() != row['review_file_sha256']:
            raise ValueError('selected_snapshot_changed')
        snapshot = json.loads(raw)
        if len(snapshot['nodes']) != prior['nodes'] or len(snapshot['nodes']) != row['nodes']:
            raise ValueError('selected_snapshot_incomplete')
        for node in snapshot['nodes']:
            original = node['original_source']
            for field in ('source_id', 'source_digest'):
                if (field, original.get(field)) not in identities:
                    raise ValueError('snapshot_original_outside_exposure_audit')
    documents = {q['source_document_id'] for q in questions}
    if documents != set(selected) or documents != set(source_files):
        raise ValueError('question_selection_scope_mismatch')
    # An allowlist, not exclusion of today's known answer keys: new private
    # review fields must never silently become retrieval-provider inputs.
    public = {'questions': [{'id': q['id'], 'query': q['query']} for q in questions]}
    private = {'questions': deepcopy(questions)}
    for question in private['questions']:
        question['status'] = 'source_questions_frozen_before_ranking'
        question['split'] = 'source_disjoint_prospective_holdout'
    def encode(value):
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
    query_bytes, review_bytes = encode(public), encode(private)
    manifest = {
        'format': 'source-first-retrieval-questions.v1',
        'selection_sha256': sha256(selection_raw).hexdigest(),
        'exposure_audit_sha256': sha256(exposure_raw).hexdigest(),
        'query_file_sha256': sha256(query_bytes).hexdigest(),
        'review_file_sha256': sha256(review_bytes).hexdigest(),
        'source_files_sha256': {d: sha256(raw).hexdigest() for d, raw in sorted(source_files.items())},
        'proof_audit': review,
        'independence_scope': 'Recorded source identities absent from the frozen exposure audit exclusions',
        'execution_config_frozen': False,
        'retrieval_executed': False,
        'full_corpus_equivalent_evidence_reviewed': False,
        'label_protocol': {
            '0': 'Wrong scope or unrelated evidence',
            '1': 'Context/navigation or insufficient direct evidence',
            '2': 'Direct evidence for a required component',
            '3': 'Complete direct evidence for the requested answer',
            'unreviewed': 'Unknown; never automatically grade zero',
            'counterevidence': 'Relevant when checking a false premise; not an empty-result negative',
            'metric_scope': 'Fixed-K Precision; graded nDCG and recall require complete frozen pool review',
            'translation': 'Bilingual pairs are paired cases, not independent statistical samples',
        },
    }
    return {'queries.json': query_bytes, 'source-review.private.json': review_bytes,
            'manifest.json': encode(manifest)}
