"""Apply source-anchored semantic reviews without replacing original facts."""
from contextlib import closing
import json
import sqlite3

from sec_agent.research_foundation.material_presentation import archived_text


def apply_reviews(path,manifest):
    with closing(sqlite3.connect(path)) as db,db:
        db.row_factory=sqlite3.Row
        state=db.execute("SELECT value FROM snapshot_metadata WHERE key='state'").fetchone()
        if state and state[0]=='published_public_library.v1':raise ValueError('immutable_release_requires_build')
        texts={};count=0
        for item in manifest['rows']:
            row=db.execute('SELECT * FROM financial_points WHERE id=?',(item['existing_fact_id'],)).fetchone()
            if not row or (row['entity_id'],row['source_id'],row['value'])!=(item['entity_id'],item['source_id'],item['raw_value']):
                raise ValueError('reviewed_fact_identity_changed')
            sid=row['source_id']
            if sid not in texts:texts[sid]=' '.join(archived_text(db,sid).split())
            quote=' '.join(item['evidence_row'].split())
            if not quote or quote not in texts[sid]:raise ValueError('reviewed_evidence_not_found')
            review=item.get('derived_operand_review',item.get('payload',{}).get('derived_operand_review',{}))
            concept=review.get('concept') or item['canonical_concept']
            multiplier=review.get('sign_multiplier',1)
            if multiplier not in {1,-1}:raise ValueError('invalid_sign_multiplier')
            payload=json.loads(row['payload'])
            payload['derived_operand_review']={**review,'concept':concept,'sign_multiplier':multiplier,
                'reviewed_at':manifest['reviewed_at'],'evidence_row':item['evidence_row'],
                'accounting_basis':item.get('accounting_basis'),'source_id':sid,'original_concept':row['concept']}
            db.execute('UPDATE financial_points SET payload=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),row['id']));count+=1
    return count
