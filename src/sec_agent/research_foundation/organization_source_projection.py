"""Versioned original chunk projection; resource identity and ACL stay outside."""
from datetime import date
from hashlib import sha256
import json

PROJECTION = 'organization-library-chunks.v1'


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
    nodes = []
    for chunk in bundle['chunks']:
        identifier = document_id.replace('ORGDOC::', 'ORGSECTION::') + ':chunk-' + sha256(chunk['id'].encode()).hexdigest()[:32]
        text = chunk['body']
        embedding_text = chunk['context'] + '\n' + text
        if (bundle['text'][chunk['source_char_start']:chunk['source_char_end']] != text
                or sha256(text.encode()).hexdigest() != chunk['digest']
                or sha256(embedding_text.encode()).hexdigest() != chunk['embedding_input_sha256']):
            raise ValueError('complete_source_chunk_projection_mismatch')
        origin = {key: chunk[key] for key in ('id','parent_id','locator','char_start','char_end',
                  'source_char_start','source_char_end','embedding_input_sha256')}
        origin.update(source_id=source['id'], source_digest=source['digest'],
                      library_sha256=bundle['library_sha256'], source_url=source['url'])
        row = dict(node_id=identifier, parent_document_id=document_id, parent_section_id=document_id,
                   title=item['title'], section_path=[chunk['locator']], document_kind='document',
                   source_role='organization_complete_parsed_source', company=metadata.get('entity_id'),
                   publication_date=source['published_at'], fiscal_period=metadata.get('fiscal_period') or metadata.get('period_end'),
                   content=text, content_sha256=chunk['digest'], raw_body_sha256=item['ref']['digest'],
                   stable_url=url, embedding_content=embedding_text,
                   embedding_input_sha256=chunk['embedding_input_sha256'], original_source=origin)
        nodes.extend([{**row,'node_kind':'section'}, {**row,'node_kind':'text','node_id':identifier+':leaf'}])
    return nodes
