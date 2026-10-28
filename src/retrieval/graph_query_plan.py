"""Conservative graph seeds from resolved query identities, never fuzzy joins."""
import re


def graph_seeds(request,plan):
    if request.entity_id:
        return [request.entity_id], 'explicit_entity'
    if request.organization_query_planning!='conservative.v5':
        return [],'not_requested'
    from .query_requirements import positive_view
    positive,_=positive_view(request.query)
    # Graph evidence is useful for relationship questions. A numeric statement
    # question must not reserve capacity for unrelated issuer adjacency.
    if not re.search(r'供应商|客户|合作伙伴|持股|持有|收购|交易对手|关系|'
                     r'\b(?:suppliers?|customers?|partners?|holdings?|owns?|ownership|acqui\w*|counterpart\w*|relationships?)\b',
                     positive,re.I):
        return [],'no_relationship_requirement'
    constraint=(plan or {}).get('constraint',{})
    identities=constraint.get('issuer_union') or [constraint]
    seeds=list(dict.fromkeys(item['issuer_id'] for item in identities if item.get('issuer_id')))
    return seeds[:8], 'resolved_query_issuers' if seeds else 'unresolved_identity_no_graph_seed'
