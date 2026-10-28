"""Validate source-first review evidence before a retrieval evaluation freeze.

This validates identity and exact coordinates, not the financial correctness of
the reviewed answer or the equivalence of translated questions.
"""
from collections import defaultdict
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
