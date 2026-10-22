"""Versioned original chunk projection; resource identity and ACL stay outside."""
from datetime import date
from collections.abc import Mapping
from hashlib import sha256
import json
import zlib
from types import MappingProxyType

PROJECTION = 'organization-library-chunks.v1'


class _SourceNode(Mapping):
    """Internal read-only view; decode one exact body only while consuming it.

    A section and its search leaf share metadata and lossless UTF-8 bytes. No decoded
    body cache: retaining it would recreate the corpus-sized string heap.
    Public tool responses still materialize ordinary dictionaries/strings.
    """
    __slots__ = ('_metadata', '_body', '_compressed', '_kind')

    def __init__(self, metadata, body, compressed, kind):
        self._metadata, self._body, self._compressed, self._kind = metadata, body, compressed, kind

    def __getitem__(self, key):
        if key == 'content':
            return (zlib.decompress(self._body) if self._compressed else self._body).decode('utf-8')
        if key == 'node_kind':
            return self._kind
        if key == 'node_id' and self._kind == 'text':
            return self._metadata[key] + ':leaf'
        return self._metadata[key]

    def __iter__(self):
        yield from self._metadata
        yield 'content'
        yield 'node_kind'

    def __len__(self):
        return len(self._metadata) + 2


def validate_source_cutoff(bundle, as_of):
    source = bundle['source']
    metadata = json.loads(source['metadata'])
    vintage = source['vintage']
    available = (metadata.get('known_at') or source['published_at']) if vintage == 'known_as_of' else source['published_at']
    # Match the public library's strict, day-granular source contract. A capture
    # timestamp does not make an unknown/current-revised source historical.
    if (vintage not in {'dated_original','known_as_of'} or not available
            or date.fromisoformat(str(available)[:10]) > date.fromisoformat(as_of)):
        raise ValueError('complete_source_not_available_at_research_cutoff')


def source_nodes(bundle, document_id, item, url):
    """Body is evidence; embedding context stays a separate navigation field."""
    source = bundle['source']
    metadata = json.loads(source['metadata'])
    indexed = 'node_recovery' in bundle
    originals = {}
    if indexed:
        from retrieval.library_node_recovery import validate_bundle
        originals=validate_bundle(bundle)
    nodes = []
    for chunk in bundle['chunks']:
        identifier = document_id.replace('ORGDOC::', 'ORGSECTION::') + ':chunk-' + sha256(chunk['id'].encode()).hexdigest()[:32]
        text = chunk['body']
        embedding_text = chunk['context'] + '\n' + text
        if ((not indexed and bundle['text'][chunk['source_char_start']:chunk['source_char_end']] != text)
                or sha256(text.encode()).hexdigest() != chunk['digest']
                or sha256(embedding_text.encode()).hexdigest() != chunk['embedding_input_sha256']):
            raise ValueError('complete_source_chunk_projection_mismatch')
        keys=('id','parent_id','locator','char_start','char_end','embedding_input_sha256')
        if not indexed:keys+=('source_char_start','source_char_end')
        origin = {key: chunk[key] for key in keys}
        origin.update(source_id=source['id'], source_digest=source['digest'],
                      library_sha256=bundle['library_sha256'], source_url=source['url'])
        if 'archive_recovery' in bundle:
            origin.update(original_page=chunk['original_page'],
                          parsed_text_sha256=bundle['archive_recovery']['parsed_text_sha256'],
                          parser=bundle['archive_recovery']['parser'])
        if indexed:
            original=originals[chunk['parent_id']]
            origin.update(original_node_id=original['node_id'],original_node_kind=original['node_kind'],
                          original_parent_section_id=original['parent_section_id'],
                          original_section_path=original['section_path'],
                          original_page_start=original.get('page_start'),original_page_end=original.get('page_end'),
                          position_basis='original_indexed_node_characters',
                          node_set_sha256=bundle['node_recovery']['node_set_sha256'],complete_original_document=False)
        row = dict(node_id=identifier, parent_document_id=document_id, parent_section_id=document_id,
                   title=item['title'], section_path=[chunk['locator']], document_kind='document',
                   source_role='organization_indexed_node_set' if indexed else 'organization_complete_parsed_source', company=metadata.get('entity_id'),
                   publication_date=source['published_at'], fiscal_period=metadata.get('fiscal_period') or metadata.get('period_end'),
                   content_sha256=chunk['digest'], raw_body_sha256=item['ref']['digest'],
                   stable_url=url, embedding_context=chunk['context'],
                   embedding_input_sha256=chunk['embedding_input_sha256'], original_source=origin)
        row_metadata = MappingProxyType(row)
        body = text.encode('utf-8')
        packed = zlib.compress(body, level=1)
        compressed = len(packed) < len(body)
        stored = packed if compressed else body
        nodes.extend([_SourceNode(row_metadata, stored, compressed, 'section'),
                      _SourceNode(row_metadata, stored, compressed, 'text')])
    return nodes
