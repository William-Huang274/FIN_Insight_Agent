"""Collapse duplicate projections of the same original span, not equal numbers.

Body equality alone is unsafe across years, table rows, units or revisions.
Every alternate identity must already be in the authorized scored population.
"""
import json
from hashlib import sha256
from .source_coordinates import VERIFIED,verified_bounds


def collapse_original_duplicates(rows):
    result=[];groups={};aliases=[]
    for row in rows:
        origin=row.get('original_source',{})
        structure=row.get('source_structure',{})
        if structure.get('status') not in VERIFIED or not all(origin.get(k) for k in
                ('source_id','source_digest','library_sha256')):
            result.append(row);continue
        if sha256(row['content'].encode()).hexdigest()!=row['content_sha256']:
            raise ValueError('result_group_original_mismatch')
        space,start,end=verified_bounds(row)
        identity=[origin['source_id'],origin['source_digest'],origin['library_sha256'],space,start,end,
            row['content_sha256'],row.get('embedding_input_sha256'),row.get('scoring_view'),
            structure.get('period_evidence'),structure.get('evidence_scopes')]
        key=json.dumps(identity,sort_keys=True,ensure_ascii=False,separators=(',',':'))
        if key not in groups:
            groups[key]=row['node_id'];result.append(row)
        else:
            aliases.append({'selected_node_id':groups[key],'alternate_node_id':row['node_id'],
                'alternate_document_id':row['parent_document_id'],'content_sha256':row['content_sha256'],
                'basis':'same_verified_original_revision_and_coordinate_span'})
    return result,{'policy':'exact-original-span.v1','removed_rank_slots':len(aliases),
        'aliases':aliases,'equal_body_alone_is_not_equivalence':True}
