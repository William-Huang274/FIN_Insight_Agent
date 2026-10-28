"""Content-only ready-to-restore metadata; never a permission or generation lease."""
from base64 import b64encode, b64decode
import json
import zlib

FORMAT = 'prepared-source-metadata.v1'


def prepare(value):
    from retrieval.source_window_candidates import adjacent_nodes
    from retrieval.fact_scope import compact_evidence
    ordered = sorted(value.get('locations', []))
    neighbors = {}
    for position, (parent, start, end, node) in enumerate(ordered):
        adjacent = []
        for other in (position - 1, position + 1):
            if 0 <= other < len(ordered):
                p, a, b, identifier = ordered[other]
                if p == parent and max(start, a) - min(end, b) <= 4:
                    adjacent.append(identifier)
        neighbors[node] = adjacent
    def packed(item):
        return b64encode(zlib.compress(json.dumps(item, ensure_ascii=False,
            separators=(',', ':'), allow_nan=False).encode(), 1)).decode('ascii')
    return {**{k: v for k, v in value.items() if k not in {'structures', 'locations'}},
        'evidence_scopes':{n:s.get('evidence_scopes', []) for n,s in value['structures'].items()
                           if s.get('evidence_scopes')},
        'evidence_scope_complete':[n for n,s in value['structures'].items() if s.get('evidence_scope_complete')],
        'period_evidence':{n:compact_evidence(s['period_evidence']) for n,s in value['structures'].items() if s.get('period_evidence')},
        'source_intervals':{n:[a,b] for _,a,b,n in ordered},
        'prepared_navigation': {'format': FORMAT, 'structures': packed(value['structures']),
            'locations': packed(ordered), 'neighbors': neighbors,
            'window_neighbors': adjacent_nodes(ordered)}}


def restore(value):
    packed = value['prepared_navigation']
    if packed['format'] != FORMAT:
        raise ValueError('organization_prepared_source_metadata_format')
    # The entire receipt (including these bytes) was digest checked by the
    # caller. Decode JSON structures only when a candidate needs them.
    return (b64decode(packed['structures'], validate=True),
            b64decode(packed['locations'], validate=True),
            packed['neighbors'], packed['window_neighbors'])
