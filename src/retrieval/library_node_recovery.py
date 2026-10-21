"""Recover indexed node sets without pretending they are linear full text."""
from hashlib import sha256
import json
from pathlib import Path
import re

from retrieval.library_source_bundle import text_digest

RECEIPT = 'library-indexed-node-recovery.v1'
CATALOG = 'library-indexed-node-catalog.v1'
FORMAT = 'library-indexed-node-bundle.v1'
COMPACT = 'library-indexed-node-references.v1'


def canonical_digest(value):
    return text_digest(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')))


def node_body(node):
    return node.get('content') or node.get('model_text') or ''


def directory(nodes):
    lines = ['已导入节点目录（不是完整原文）；按 node_id 读取正文、表格和章节。']
    for n in nodes:
        lines.append(json.dumps({k:n.get(k) for k in ('node_id','node_kind','parent_section_id',
                           'section_path','page_start','page_end')},ensure_ascii=False))
    return '\n'.join(lines)


def validate_nodes(source, parents, nodes):
    by_id={n['node_id']:n for n in nodes}
    if (source['access_state']!='readable' or not nodes or len(by_id)!=len(nodes)
            or len(parents)!=len(nodes) or {p['id'] for p in parents}!=set(by_id)):
        raise ValueError('indexed_node_coverage_mismatch')
    for p in parents:
        n=by_id[p['id']]; body=node_body(n)
        if (n['parent_document_id']!=source['id'] or p['source_id']!=source['id']
                or (n.get('raw_body_sha256') or n.get('content_sha256'))!=source['digest']
                or n.get('stable_url')!=source['url'] or not body
                or text_digest(body)!=n['content_sha256'] or p['body']!=body
                or p['digest']!=text_digest(body)
                or p['locator']!=str(n['section_path'])+' / '+str(n.get('page_start'))):
            raise ValueError('indexed_node_original_mismatch')
        parent=by_id.get(n['parent_section_id'])
        if (parent is None or parent['node_kind']!='section'
                or (n['node_kind']=='section' and parent['node_id']!=n['node_id'])):
            raise ValueError('indexed_node_section_relation_invalid')
    return by_id


class NodeRecoveryCatalog:
    def __init__(self,path,expected_sha256):
        self.root=Path(path).resolve().parent
        raw=Path(path).read_bytes()
        if not re.fullmatch('[a-f0-9]{64}',expected_sha256 or '') or sha256(raw).hexdigest()!=expected_sha256:
            raise ValueError('node_catalog_digest_mismatch')
        self.manifest=json.loads(raw);self.sha256=expected_sha256
        if self.manifest['format']!=CATALOG or self.manifest['status']!='verified':
            raise ValueError('node_catalog_not_verified')

    def recover(self,source,parents,library_sha256):
        if self.manifest['library_sha256']!=library_sha256:
            raise ValueError('node_catalog_library_mismatch')
        record=self.manifest['sources'].get(source['id'])
        if not record:raise ValueError('node_receipt_missing')
        digest=record['sha256']
        if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('node_receipt_digest_invalid')
        path=(self.root/(digest+'.json')).resolve()
        if not path.is_relative_to(self.root):raise ValueError('node_receipt_path_invalid')
        raw=path.read_bytes()
        if sha256(raw).hexdigest()!=digest:raise ValueError('node_receipt_digest_mismatch')
        receipt=json.loads(raw)
        if (receipt['format']!=RECEIPT or receipt['source_id']!=source['id']
                or receipt['library_sha256']!=library_sha256 or receipt['source_digest']!=source['digest']):
            raise ValueError('node_receipt_identity_mismatch')
        nodes=receipt['nodes']
        validate_nodes(source,parents,nodes)
        return dict(nodes=nodes, node_set_sha256=canonical_digest(nodes),
                    catalog_sha256=self.sha256,receipt_sha256=digest,
                    original_node_file_sha256=receipt['original_node_file_sha256'],
                    scope='complete imported node set; original document completeness not established')


def validate_bundle(bundle):
    recovery=bundle['node_recovery']
    if (canonical_digest(recovery['nodes'])!=recovery['node_set_sha256']
            or directory(recovery['nodes'])!=bundle['text']):
        raise ValueError('indexed_node_set_digest_mismatch')
    by_id=validate_nodes(bundle['source'],bundle['parents'],recovery['nodes'])
    parents={p['id']:p for p in bundle['parents']}
    for c in bundle['chunks']:
        p=parents.get(c['parent_id'])
        if (p is None or c['source_id']!=bundle['source']['id']
                or type(c['char_start']) is not int or type(c['char_end']) is not int
                or not 0<=c['char_start']<c['char_end']<=len(p['body'])
                or c['body']!=p['body'][c['char_start']:c['char_end']]
                or text_digest(c['body'])!=c['digest']):
            raise ValueError('indexed_chunk_original_mismatch')
    return by_id


def compact_bundle(bundle):
    validate_bundle(bundle)
    return {**bundle,'format':COMPACT,
            **{table:[{k:v for k,v in row.items() if k!='body'} for row in bundle[table]]
               for table in ('parents','chunks')}}


def expand_bundle(bundle):
    nodes={n['node_id']:n for n in bundle['node_recovery']['nodes']}
    if any('body' in r for table in ('parents','chunks') for r in bundle[table]):
        raise ValueError('indexed_compact_duplicate_body')
    parents=[{**p,'body':node_body(nodes[p['id']])} for p in bundle['parents']]
    by_id={p['id']:p for p in parents}
    chunks=[{**c,'body':by_id[c['parent_id']]['body'][c['char_start']:c['char_end']]} for c in bundle['chunks']]
    result={**bundle,'format':FORMAT,'parents':parents,'chunks':chunks}
    validate_bundle(result)
    return result


def configured_node_catalog():
    import os
    path=os.getenv('FINSIGHT_LIBRARY_NODE_CATALOG');digest=os.getenv('FINSIGHT_LIBRARY_NODE_SHA256')
    if not path and not digest:return None
    if not path or not digest:raise ValueError('node_catalog_configuration_incomplete')
    return NodeRecoveryCatalog(path,digest)
