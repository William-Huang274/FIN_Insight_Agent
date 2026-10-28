"""A measured result boundary, separate from relative reranker ordering.

Calibration is fitted only to explicitly graded query/body pairs. A threshold
is not a probability or an authorization grant. Unknown labels, incompatible
pipelines and unsupported query families cannot silently acquire confidence.
"""
from hashlib import sha256
import json
import math

FORMAT='graded-relevance-boundary.v1'


def _score(value):
    # bool is an int subclass but is never a provider relevance score.
    return type(value) in (float,int) and 0<=value<=1 and math.isfinite(value)


def _requirements_valid(precision,results,questions):
    return (_score(precision) and 0<precision<1
            and type(results) is int and results>=1
            and type(questions) is int and questions>=2)


def _check_calibration_values(calibration):
    fitted=calibration.get('fit');requirements=calibration.get('requirements')
    if (not isinstance(fitted,dict) or not _score(fitted.get('threshold'))
            or not isinstance(requirements,dict)
            or not _requirements_valid(requirements.get('minimum_precision_lower_bound'),
                requirements.get('minimum_results'),requirements.get('minimum_questions'))):
        raise ValueError('relevance_calibration_invalid_contract')


def _digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _wilson_lower(correct,total,z=1.96):
    if not total:return 0.0
    p=correct/total;denominator=1+z*z/total
    return (p+z*z/(2*total)-z*math.sqrt(p*(1-p)/total+z*z/(4*total*total)))/denominator


def _reviewed_rows(samples):
    unique={}
    for row in samples:
        if (type(row.get('grade')) is not int or not 0<=row['grade']<=3
                or not _score(row.get('score')) or not row.get('review_reason')
                or any(not isinstance(row.get(k),str) or len(row[k])!=64
                       or any(c not in '0123456789abcdef' for c in row[k])
                       for k in ('query_sha256','content_sha256','source_document_sha256'))):
            raise ValueError('relevance_calibration_requires_complete_review')
        key=row['query_sha256'],row['content_sha256']
        value={k:row[k] for k in ('query_sha256','content_sha256','source_document_sha256','grade')}
        value['score']=float(row['score'])
        if key in unique and unique[key]!=value:raise ValueError('relevance_calibration_conflicting_pair')
        unique[key]=value
    return sorted(unique.values(),key=lambda r:(-r['score'],r['query_sha256'],r['content_sha256']))


def fit(samples,*,pipeline,minimum_precision,minimum_results,minimum_questions):
    """Choose maximal retained coverage satisfying a predeclared lower bound.

    Each sample is one independently reviewed question and original body.
    Repeated appearances of that pair must have identical score/grade and are
    counted once. No company, question ID or expected-answer string is learned.
    The caller must freeze a disjoint validation set before enabling a fit.
    """
    if not pipeline or not _requirements_valid(minimum_precision,minimum_results,minimum_questions):
        raise ValueError('relevance_calibration_invalid_contract')
    rows=_reviewed_rows(samples)
    eligible=[];accepted=[];correct=0;queries=set()
    for i,row in enumerate(rows):
        accepted.append(row);correct+=row['grade']>=2;queries.add(row['query_sha256'])
        if i+1<len(rows) and rows[i+1]['score']==row['score']:continue
        lower=_wilson_lower(correct,len(accepted))
        if len(accepted)>=minimum_results and len(queries)>=minimum_questions and lower>=minimum_precision:
            eligible.append({'threshold':row['score'],'accepted':len(accepted),'relevant':correct,
                'precision':correct/len(accepted),'nominal_wilson_lower':lower,'questions':len(queries)})
    if not eligible:raise ValueError('relevance_calibration_no_supported_boundary')
    chosen=max(eligible,key=lambda c:c['accepted'])
    return {'format':FORMAT,'pipeline':pipeline,'fit':chosen,
        'requirements':{'minimum_precision_lower_bound':minimum_precision,
            'minimum_results':minimum_results,'minimum_questions':minimum_questions},
        'reviewed_pairs':len(rows),'review_sha256':_digest(sorted(rows,key=lambda r:(r['query_sha256'],r['content_sha256']))),
        'reviewed_query_sha256':sorted({r['query_sha256'] for r in rows}),
        'reviewed_source_document_sha256':sorted({r['source_document_sha256'] for r in rows}),
        'independent_validation':None,'scope':'reviewed_pool_not_exhaustive_recall',
        'score_semantics':'ranking_signal_not_correctness_probability',
        'bound_semantics':'nominal_pair_bound_not_cluster_independent_production_guarantee'}


def validate(calibration,samples,*,pipeline):
    _check_calibration_values(calibration)
    rows=_reviewed_rows(samples)
    queries={r['query_sha256'] for r in rows};documents={r['source_document_sha256'] for r in rows}
    if (calibration.get('format')!=FORMAT or calibration.get('pipeline')!=pipeline
            or queries & set(calibration['reviewed_query_sha256'])
            or documents & set(calibration['reviewed_source_document_sha256'])):
        raise ValueError('relevance_validation_requires_disjoint_queries_and_sources')
    accepted=[r for r in rows if r['score']>=calibration['fit']['threshold']]
    relevant=sum(r['grade']>=2 for r in accepted);requirements=calibration['requirements']
    lower=_wilson_lower(relevant,len(accepted))
    passed=(len(accepted)>=requirements['minimum_results']
        and len({r['query_sha256'] for r in accepted})>=requirements['minimum_questions']
        and lower>=requirements['minimum_precision_lower_bound'])
    return {'status':'passed' if passed else 'failed','calibration_sha256':_digest(calibration),
        'query_sha256':sorted(queries),'source_document_sha256':sorted(documents),
        'review_sha256':_digest(rows),'accepted':len(accepted),'relevant':relevant,
        'precision':relevant/len(accepted) if accepted else None,'nominal_wilson_lower':lower,
        'pooled_recall':relevant/sum(r['grade']>=2 for r in rows) if any(r['grade']>=2 for r in rows) else None}


def partition(rows,scores,calibration,*,pipeline,validation,limit):
    """Keep order, expose uncertain IDs separately, never fill to K blindly.

    Validation evidence is a deployment-owned artifact bound to this exact
    fit. Current access and source checks remain the service's responsibility.
    """
    _check_calibration_values(calibration)
    if (type(limit) is not int or limit<1
            or calibration.get('format')!=FORMAT or calibration.get('pipeline')!=pipeline
            or validation.get('calibration_sha256')!=_digest(calibration)
            or validation.get('status')!='passed'
            or not validation.get('query_sha256')
            or set(validation['query_sha256']) & set(calibration['reviewed_query_sha256'])
            or not validation.get('source_document_sha256')
            or set(validation['source_document_sha256']) & set(calibration['reviewed_source_document_sha256'])):
        raise ValueError('relevance_boundary_requires_compatible_independent_validation')
    accepted=[];uncertain=[];seen=set();threshold=calibration['fit']['threshold']
    for row in rows:
        key=row['node_id']
        if key in seen:raise ValueError('relevance_boundary_duplicate_candidate')
        seen.add(key);score=scores.get(key)
        if not _score(score):
            raise ValueError('relevance_boundary_missing_valid_score')
        (accepted if score>=threshold else uncertain).append(row)
    return accepted,{'policy':FORMAT,'calibration_sha256':_digest(calibration),
        'threshold':threshold,'accepted_count':len(accepted),'requested_limit':limit,
        'result_state':'fewer_supported_candidates_than_requested' if len(accepted)<limit else 'ranked_candidates_available',
        'uncertain_candidate_ids':[r['node_id'] for r in uncertain],
        'unknown_or_absent_disclosure':False,'answer_sufficiency':'requires_original_readback',
        'precision_denominator':'evaluation_keeps_fixed_k_empty_slots_not_relabelled_correct'}
