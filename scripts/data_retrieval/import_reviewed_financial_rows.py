"""Import explicitly reviewed source-table cells, retaining original scale and dates.

This is a bounded bridge for non-XBRL reports, not an automatic semantic mapper.
The manifest identifies each row, column, period and reporting basis. Missing
source text or ambiguous rows are rejected before any write.
"""
import json
import re
import sqlite3
from contextlib import closing
from decimal import Decimal
from hashlib import sha256
from sec_agent.research_foundation.material_presentation import archived_text


def import_rows(path, manifest):
    rows=[]
    with closing(sqlite3.connect(path)) as db, db:
        db.row_factory=sqlite3.Row
        state=db.execute("SELECT value FROM snapshot_metadata WHERE key='state'").fetchone()
        if state and state[0]=='published_public_library.v1':raise ValueError('immutable_release_requires_build')
        for item in manifest['rows']:
            source=db.execute("SELECT * FROM sources WHERE id=? AND access_state='readable'",(item['source_id'],)).fetchone()
            if not source:raise ValueError('source_not_readable')
            if not db.execute('SELECT 1 FROM entity_sources WHERE entity_id=? AND source_id=?',(item['entity_id'],source['id'])).fetchone():raise ValueError('source_entity_mismatch')
            body=archived_text(db,source['id'])
            if item.get('locator_scope')=='archived_document':
                if item.get('pdf_page') is not None or not item.get('context_quotes'):
                    raise ValueError('document_locator_requires_context_without_invented_page')
                section=body
            else:
                page=item['pdf_page']
                markers=re.split(r'(\[PDF page \d+\]|--- PDF PAGE \d+ ---)',body)
                section=next((markers[i+1] for i in range(1,len(markers)-1,2)
                              if markers[i] in {f'[PDF page {page}]',f'--- PDF PAGE {page} ---'}),None)
                if section is None:raise ValueError('pdf_page_not_found')
            for context in item.get('context_quotes',[]):
                if ' '.join(context.split()) not in ' '.join(section.split()):raise ValueError('table_context_not_found')
            line=' '.join(item['evidence_row'].split())
            if line not in ' '.join(section.split()):raise ValueError('reviewed_row_not_found')
            raw=item['source_value']; token=raw.replace(',','')
            if not re.search(r'(?<![\d.,])'+re.escape(raw)+r'(?![\d.,])',line):raise ValueError('reviewed_value_not_found')
            if not item.get('period_basis') or not item.get('accounting_basis'):raise ValueError('period_and_basis_required')
            value=Decimal(re.sub(r'\s+','',token).replace('(','-').replace(')',''))*Decimal(str(item['scale']))
            meta=json.loads(source['metadata']);date=source['published_at'] or (meta.get('known_at') or meta.get('captured_at',''))[:10]
            if not date:raise ValueError('available_date_required')
            payload={**item,'date_basis':'source_publication' if source['published_at'] else 'known_at_capture_not_publication',
                'normalization':'reviewed_source_cell_with_explicit_scale','reviewed_at':manifest['reviewed_at']}
            identity=sha256(json.dumps([source['id'],item],sort_keys=True).encode()).hexdigest()
            rows.append((identity,item['entity_id'],'issuer-reported',item['concept'],item['label'],str(value),item['unit'],
                item.get('period_start'),item['period_end'],date,None,item['period_basis'],item['form'],'',source['id'],json.dumps(payload,ensure_ascii=False)))
        db.executemany('INSERT OR IGNORE INTO financial_points VALUES('+','.join('?'*16)+')',rows)
    return len(rows)
