"""Reviewed answer requirements: OR of complete AND-sets of original passages.

Labels stay separate from retrieval. The reviewer supplies actual quotes and
why each alternative covers the SAME requirement; code checks custody, not
semantic truth. No automatic label relaxation from search output.
"""
from hashlib import sha256


def validate_requirements(requirements, originals):
    if not requirements or len({r['id'] for r in requirements})!=len(requirements):
        raise ValueError('unique_nonempty_requirements_required')
    for requirement in requirements:
        if not requirement.get('statement') or not requirement.get('review_basis'):
            raise ValueError('explicit_semantic_review_required')
        alternatives=requirement.get('alternatives',[])
        if not alternatives:raise ValueError('nonempty_alternative_required')
        source_version=None
        for alternative in alternatives:
            if not alternative or len({r['node_id'] for r in alternative})!=len(alternative):
                raise ValueError('unique_nonempty_passage_set_required')
            for label in alternative:
                original=originals[label['node_id']]
                identity=(original['parent_document_id'],original['raw_body_sha256'])
                if source_version is None:source_version=identity
                if source_version!=identity:raise ValueError('alternative_source_revision_mismatch')
                if sha256(original['content'].encode()).hexdigest()!=label['content_sha256']:
                    raise ValueError('alternative_original_changed')
                if not label.get('quote') or label['quote'] not in original['content']:
                    raise ValueError('alternative_quote_missing')
    return requirements


def requirement_metrics(ranked, requirements, ks=(5,10,20,40)):
    positions={n:i+1 for i,n in enumerate(dict.fromkeys(ranked))}
    completion=[]
    for requirement in requirements:
        alternatives=[]
        for group in requirement['alternatives']:
            ranks=[positions.get(label['node_id']) for label in group]
            if ranks and all(r is not None for r in ranks):alternatives.append(max(ranks))
        completion.append(min(alternatives) if alternatives else None)
    if not completion:raise ValueError('nonempty_requirements_required')
    return {f'all_requirements@{k}':all(r is not None and r<=k for r in completion) for k in ks} | {
        'completion_ranks':completion,'semantics':'reviewed_passage_requirements_not_generated_answer_accuracy'}
