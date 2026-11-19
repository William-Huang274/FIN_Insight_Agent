"""Deterministic local RRF shared by organization navigation and evaluation."""


def reciprocal_rank_fusion(channels, *, limit=None):
    scores = {}
    for ids in channels:
        for rank, identifier in enumerate(dict.fromkeys(ids), 1):
            scores[identifier] = scores.get(identifier, 0.) + 1/(60+rank)
    ordered = sorted(scores, key=lambda identifier: (-scores[identifier], identifier))
    return ordered if limit is None else ordered[:limit]
