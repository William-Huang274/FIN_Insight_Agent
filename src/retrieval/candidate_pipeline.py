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
    full_lexical=list(lexical)
    lexical = lexical[:limits['lexical']]
    result = {'ordered':reciprocal_rank_fusion([dense, lexical] + ([graph] if graph is not None else [])),
              'dense':dense, 'lexical':lexical}
    if graph is not None:
        result['graph'] = graph
    if policy=='needs_units.v1':
        # Repeated parents shared by channels do not consume distinct union
        # slots. Fill the spare capacity with independently ranked candidates
        # before considering any adjacency. Keep primary quotas auditable.
        seen=set(result['ordered']);extra_dense=[];extra_lexical=[]
        depth={'dense':limits['dense'],'lexical':limits['lexical']}
        dense_tail=[ids[i] for i in order[limits['dense']:]]
        lexical_tail=full_lexical[limits['lexical']:]
        for offset in range(max(len(dense_tail),len(lexical_tail))):
            for name,channel,output in (('dense',dense_tail,extra_dense),('lexical',lexical_tail,extra_lexical)):
                if len(seen)>=48:break
                if offset<len(channel):
                    depth[name]=limits[name]+offset+1
                    if channel[offset] not in seen:
                        output.append(channel[offset]);seen.add(channel[offset])
            if len(seen)>=48:break
        result['ordered']=[n for n in reciprocal_rank_fusion([[ids[i] for i in order[:depth['dense']]],
            full_lexical[:depth['lexical']]]+([graph] if graph is not None else [])) if n in seen]
        result['independent_backfill']={'dense':extra_dense,'lexical':extra_lexical,
            'max_unique_candidates':48,'examined_channel_prefixes':depth,'adjacent_only_candidates':[]}
    return result, order, limits


def expand_population(ordered, dense, rows, neighbors, *, policy):
    if policy not in {'needs_window.v2', 'needs_window.v3', 'needs_window.v4'}:
        return list(ordered), None
    from .source_window_candidates import expand_candidates
    return expand_candidates(ordered, dense, neighbors,
                             {r['node_id']:r['parent_document_id'] for r in rows})
