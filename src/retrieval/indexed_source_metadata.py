"""Preserve declared document metadata from a bound imported node set.

These fields describe a source, not the owner of every financial fact in it.
Ticker/legacy issuer IDs are preserved without inventing canonical entity IDs.
"""

FIELDS = ('company', 'issuer_id', 'ticker', 'source_role')


def node_metadata(source, nodes):
    values = {key: set() for key in FIELDS}
    missing = {key: 0 for key in FIELDS}
    count = 0
    for node in nodes:
        if (node.get('parent_document_id') != source['id']
                or node.get('stable_url') != source['url']
                or (node.get('raw_body_sha256') or node.get('content_sha256')) != source['digest']):
            raise ValueError('indexed_source_metadata_binding_mismatch')
        count += 1
        for key in FIELDS:
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                values[key].add(value.strip())
            else:
                missing[key] += 1
    # Missing fields are not guessed from a title, URL, or a single child.
    return {'basis': 'bound_imported_node_fields.v1', 'node_count': count,
            'values': {key: sorted(items)[0] for key, items in values.items()
                       if len(items) == 1 and not missing[key]},
            'conflicts': {key: sorted(items) for key, items in values.items() if len(items) > 1},
            'incomplete': [key for key in FIELDS if missing[key]]}


def merge_metadata(metadata, evidence):
    result = dict(metadata)
    result['indexed_source_metadata'] = evidence
    declared = evidence['values'].get('company')
    existing = result.get('company')
    conflicts = list(evidence['conflicts'])
    if declared and isinstance(existing, str) and existing.strip() and existing.strip() != declared:
        conflicts.append('company')
    if 'company' in conflicts:
        # Retain both original claims in evidence; neither becomes a filter.
        result['indexed_company_conflict'] = {'source_company': existing,
            'node_companies': evidence['conflicts'].get('company', [declared])}
        result.pop('company', None)
    elif declared:
        result['company'] = declared
    return result
