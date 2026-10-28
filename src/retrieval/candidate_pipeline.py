"""Candidate population operations shared by serving and offline evaluation.

Inputs must already be authorized and business-scoped by the caller. This
module cannot widen that population or grant access to a neighboring source.
"""
from .candidate_policy import candidate_limits
from .rank_fusion import reciprocal_rank_fusion


def fuse_channels(rows, dense_scores, lexical, *, policy, lexical_policy=None, graph=None):
    import math
    ids = [r['node_id'] for r in rows]
    population = set(ids)
    if len(population) != len(ids) or len(dense_scores) != len(ids):
        raise ValueError('candidate_pipeline_invalid_population')
    if any(not math.isfinite(float(s)) for s in dense_scores):
        raise ValueError('candidate_pipeline_nonfinite_score')
    for channel in (lexical, *([graph] if graph is not None else [])):
        if len(set(channel)) != len(channel) or not set(channel) <= population:
            raise ValueError('candidate_pipeline_channel_outside_scope')
    limits = candidate_limits(policy, has_graph=bool(graph), lexical_policy=lexical_policy)
    if graph is not None and len(graph) > limits['graph']:
        raise ValueError('candidate_pipeline_graph_outside_quota')
    order = sorted(range(len(rows)), key=lambda i: (-float(dense_scores[i]), ids[i]))
    dense = [ids[i] for i in order[:limits['dense']]]
    lexical = lexical[:limits['lexical']]
    result = {'ordered':reciprocal_rank_fusion([dense, lexical] + ([graph] if graph is not None else [])),
              'dense':dense, 'lexical':lexical}
    if graph is not None:
        result['graph'] = graph
    return result, order, limits


def expand_population(ordered, dense, rows, neighbors, *, policy):
    if policy not in {'needs_window.v2', 'needs_window.v3', 'needs_window.v4'}:
        return list(ordered), None
    from .source_window_candidates import expand_candidates
    return expand_candidates(ordered, dense, neighbors,
                             {r['node_id']:r['parent_document_id'] for r in rows})
