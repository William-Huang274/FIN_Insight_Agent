"""Identify bounded context references without promoting adjacent originals."""
from .source_window_candidates import order_source_windows


def select_context_companions(rows, expansion):
    # Validate the same verified-document linkage contract, without using the
    # legacy ordering that inserted every adjacent block.
    order_source_windows(rows, expansion)
    position = {row['node_id']:i for i,row in enumerate(rows)}
    by_id = {row['node_id']:row for row in rows}
    core = set(position) if len(rows) <= 8 else {row['node_id'] for row in rows[:8]}
    linked = {}
    for link in expansion['links']:
        linked.setdefault(link['seed'], []).append(link['neighbor'])
    promotions = {}
    promoted = set()
    for row in rows[:8]:
        seed = row['node_id']
        neighbors = linked.get(seed, [])
        if not neighbors:
            continue
        best = min(neighbors, key=position.__getitem__)
        # A window already represented in the core needs no extra slot.
        # Never substitute its weaker adjacent paragraph just to fill a quota.
        if best in core or best in promoted:
            continue
        if len(promoted) == 2:
            break
        promotions[seed] = best
        promoted.add(best)
    return rows, {'policy':'supplemental-context.v2', 'top_k_unchanged':True,
        'promotion_limit':0, 'promotions':[],
        'companions':[{'anchor':k,'companion':v} for k,v in promotions.items()]}
