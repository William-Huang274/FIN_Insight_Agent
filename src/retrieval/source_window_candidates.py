"""Bounded original-coordinate neighbors of semantic seeds, before reranking.

No query terms, labels, amounts or company-specific rules. The caller supplies
verified coordinates and the CURRENT filtered/authorized candidate population.
"""
from collections import defaultdict

POLICY = 'source_window.v2'


def adjacent_nodes(locations):
    """Locations are (immutable coordinate-space identity, start, end, node)."""
    groups = defaultdict(list)
    seen = set()
    for space, start, end, node in locations:
        if (not space or not node or node in seen or type(start) is not int
                or type(end) is not int or not 0 <= start < end):
            raise ValueError('source_window_invalid_location')
        seen.add(node)
        groups[space].append((start, end, node))
    neighbors = {}
    for items in groups.values():
        items.sort()
        for i, (start, end, node) in enumerate(items):
            neighbors[node] = []
            for j in (i - 1, i + 1):
                if 0 <= j < len(items):
                    lo, hi, other = items[j]
                    # Overlap or exact continuity only. A coordinate gap does
                    # not prove whitespace and must not bridge missing text.
                    if max(start, lo) <= min(end, hi):
                        neighbors[node].append(other)
    return neighbors


def expand_candidates(ordered, dense, neighbors, documents):
    """Keep all independent candidates; use only spare slots for seed windows.

    documents maps only current eligible node IDs to immutable document IDs.
    An unavailable neighbor is skipped, never loaded to decide its relevance.
    """
    if (len(ordered) > 48 or len(set(ordered)) != len(ordered)
            or len(set(dense)) != len(dense)
            or not set(ordered) <= documents.keys() or not set(dense) <= set(ordered)):
        raise ValueError('source_window_unverified_population')
    extra, links = [], []
    keep = ordered
    for seed in dense[:6]:
        adjacent = neighbors.get(seed, [])
        if len(adjacent) > 2 or len(set(adjacent)) != len(adjacent):
            raise ValueError('source_window_invalid_neighbors')
        for node in adjacent:
            if node not in documents:
                continue
            if documents[node] != documents[seed] or node == seed:
                raise ValueError('source_window_cross_document')
            links.append({'seed':seed, 'neighbor':node})
            if node not in keep and node not in extra:
                extra.append(node)
    selected = [*keep, *extra[:48-len(keep)]]
    links = [link for link in links if link['neighbor'] in selected]
    return selected, {'policy':POLICY, 'seed_limit':6, 'neighbor_limit':12,
                      'candidate_limit':48, 'seed_node_ids':dense[:6],
                      'links':links, 'added_node_ids':[n for n in selected if n not in ordered],
                      'displaced_node_ids':[n for n in ordered if n not in selected]}


def order_source_windows(rows, expansion):
    """Describe verified companions without changing primary result order."""
    by_id={r['node_id']:r for r in rows}
    if len(by_id)!=len(rows) or len(rows)>48 or expansion.get('policy')!=POLICY:
        raise ValueError('source_window_invalid_ranked_population')
    linked=defaultdict(list)
    links=expansion.get('links', [])
    if len(links)>12:
        raise ValueError('source_window_too_many_companions')
    for link in links:
        seed,node=link['seed'],link['neighbor']
        if (seed not in by_id or node not in by_id or seed==node
                or by_id[seed]['parent_document_id']!=by_id[node]['parent_document_id']):
            raise ValueError('source_window_unverified_companion')
        linked[seed].append(node)
        if len(linked[seed])>2:
            raise ValueError('source_window_too_many_companions')
    result=[];seen=set();windows=[]
    for row in rows:
        seed=row['node_id']
        if seed not in seen:
            result.append(row);seen.add(seed)
        added=[]
        for node in linked.get(seed,[]):
            if node not in seen:
                result.append(by_id[node]);seen.add(node);added.append(node)
        if added:windows.append({'anchor':seed,'companions':added})
    # References may be displayed or read separately. Adjacency is not a
    # relevance score and must not change either ranking or top-K membership.
    return rows,windows
