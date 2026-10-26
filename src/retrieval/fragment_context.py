"""Non-destructive views of incomplete original fragments and their neighbors."""
import re


def needs_context(body):
    text = body.strip()
    return (len(text) < 320 or text.startswith('[/TABLE]')
            or bool(re.match(r'^[a-z]', text))
            or (bool(text) and text[-1].isalpha() and not text.endswith(('.', '。'))))


def attach_context(row, neighbors):
    from hashlib import sha256
    result = dict(row)
    result['context_status'] = 'adjacent_originals_available' if neighbors else 'context_unresolved'
    refs = []
    for neighbor in neighbors:
        if neighbor['parent_document_id'] != row['parent_document_id']:
            raise ValueError('fragment_context_cross_document')
        if sha256(neighbor['content'].encode()).hexdigest() != neighbor['content_sha256']:
            raise ValueError('fragment_context_body_mismatch')
        refs.append({'node_id':neighbor['node_id'], 'document_id':neighbor['parent_document_id'],
                     'content_sha256':neighbor['content_sha256'],
                     'readback':{'source_space':'organization', 'operation':'read',
                                 'document_id':neighbor['parent_document_id'], 'node_id':neighbor['node_id']}})
    result['context_readbacks'] = refs
    # Reader and citation use the exact original; no fabricated concatenation,
    # unit propagation, or new embedding is assigned to this fragment.
    return result
