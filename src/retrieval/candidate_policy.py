"""Bounded candidate allocations shared by serving and offline evaluation."""
POLICIES = ('balanced.v1', 'dense_expanded.v1', 'needs_balanced.v1', 'needs_window.v2', 'needs_window.v3', 'needs_window.v4')


def candidate_limits(policy='balanced.v1', *, has_graph=False, lexical_policy=None):
    if policy not in POLICIES:
        raise ValueError('organization_candidate_policy_invalid')
    if policy in {'needs_balanced.v1', 'needs_window.v2', 'needs_window.v3', 'needs_window.v4'}:
        # Same 48-node maximum, with explicit capacity for several evidence
        # needs. This is an opt-in tradeoff, not an unbounded top-K increase.
        if lexical_policy == 'organization-financial-needs.v2':
            return {'dense':12 if has_graph else 24, 'lexical':24, 'graph':12 if has_graph else 0}
        return {'dense':24 if has_graph else 36, 'lexical':12, 'graph':12 if has_graph else 0}
    # Keep the original graph quota. Without an explicit graph query, spend
    # that capacity on dense candidates rather than exceeding the 48-node cap.
    return {'dense': 36 if policy == 'dense_expanded.v1' and not has_graph else 24,
            'lexical': 12, 'graph': 12 if has_graph else 0}
