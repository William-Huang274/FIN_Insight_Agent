"""Read-only offline counterpart of published source-coordinate verification.

Loads navigation for seed documents, never chooses documents from gold labels.
Serving uses its already-verified source-generation locations instead.
"""
from contextlib import closing
from hashlib import sha256
import json
import sqlite3
import zlib
from retrieval.source_window_candidates import adjacent_nodes


def verified_neighbors(directory, recordmap, seeds):
    documents = list(dict.fromkeys(recordmap[n]['document_id'] for n in seeds[:6]))
    locations = []
    with closing(sqlite3.connect((directory/'navigation.sqlite').resolve().as_uri()+'?mode=ro', uri=True)) as db:
        for document in documents:
            if not document.startswith('ORGDOC::'):
                raise ValueError('source_window_unknown_document_identity')
            prefix='ORGSECTION::'+document[len('ORGDOC::'):]+':'
            for node, compressed in db.execute('SELECT node_id,payload FROM nodes WHERE node_id>=? AND node_id<?',
                                                (prefix,prefix+'\uffff')):
                raw=zlib.decompress(compressed)
                if node not in recordmap or sha256(raw).hexdigest()!=recordmap[node]['navigation_sha256']:
                    raise ValueError('source_window_navigation_identity_mismatch')
                row=json.loads(raw)
                if (row['parent_document_id']!=document or recordmap[node]['document_id']!=document
                        or row['node_id']!=node):
                    raise ValueError('source_window_document_mismatch')
                origin=row['original_source']
                start=origin.get('source_char_start',origin.get('char_start'))
                end=origin.get('source_char_end',origin.get('char_end'))
                parent=origin.get('original_node_id') if 'source_char_start' not in origin else document
                if type(start) is int and type(end) is int and parent and 0<=start<end:
                    locations.append((parent,start,end,node))
    return adjacent_nodes(locations)
