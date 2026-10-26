"""Require source-bound, clause-level review before exposing independent labels.

This validates review evidence, not financial correctness or exhaustive qrels.
The source validator must separately verify each original body and cutoff.
"""


def validate_heldout_label_reviews(dataset, split):
    if split!='heldout' or dataset.get('evaluation_role')=='historical_regression':
        return
    rows=[q for q in dataset['questions'] if q['split']=='heldout']
    if not rows:
        raise ValueError('heldout_review_population_missing')
    for row in rows:
        if row.get('answerability','answerable')!='answerable':
            raise ValueError('heldout_negative_requires_separate_scope_review')
        review=row.get('label_review',{})
        if (review.get('status')!='reviewed' or not review.get('reviewer')
                or review.get('coverage_attestation')!='all_question_requirements_checked_against_originals'):
            raise ValueError('heldout_clause_review_incomplete:'+row['id'])
        requirements=review.get('requirements',[])
        ids=[r.get('id') for r in requirements]
        if not ids or not all(ids) or len(ids)!=len(set(ids)):
            raise ValueError('heldout_review_requirements_invalid')
        anchors={(e['source_id'],e['chunk_id']):e for e in row['evidence']}
        used=set()
        for requirement in requirements:
            if not requirement.get('description','').strip() or not requirement.get('citations'):
                raise ValueError('heldout_requirement_missing_evidence')
            for citation in requirement['citations']:
                key=(citation.get('source_id'),citation.get('chunk_id'))
                anchor=anchors.get(key)
                quote=citation.get('quote','')
                if (not anchor or citation.get('body_sha256')!=anchor['body_sha256']
                        or not quote.strip() or quote not in anchor['quote']):
                    raise ValueError('heldout_requirement_not_bound_to_label')
                used.add(key)
        if used!=set(anchors):
            raise ValueError('heldout_label_has_unreviewed_evidence')
