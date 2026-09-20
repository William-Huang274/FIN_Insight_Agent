"""Import reviewed PDF statement-page/column plans; no inferred currency or period.

Original issuer line labels and signs are retained. Unknown lines use a source
label identity, never an invented cross-company accounting equivalence.
"""
import json,re,sqlite3
from contextlib import closing
from decimal import Decimal
from hashlib import sha256
from sec_agent.research_foundation.material_presentation import archived_text
from sec_agent.research_foundation.financial_accounts import LABELS

NUMBER=r'(?:\(?-?\d[\d,]*(?:\.\d+)?\)?|[–—−-])'
def extract_rows(section,columns,initial_path,headings,path_after_labels=None):
    path=initial_path;pending='';last_heading='';out=[]
    for raw in section.splitlines():
        line=' '.join(raw.split())
        original=line
        if re.search(r'Annual Report|Universal Registration Document|^Chapter \d|^Notes? (?:RMB|USD|US\$)|^Note(?:s)?$|^Year ended|^For the year',line,re.I):
            pending='';continue
        # Some issuer EPS rows are presented in US cents, not statement thousands.
        line=re.sub(r'US(?=\d)', '',line)
        line=re.sub(r'(?<=\d) cents\b','',line)
        line=re.sub(r'(?:[.�]\s*){3,}',' ',line)
        line=re.sub(r'[¥$€£](?=\s*\(?\d)','',line)
        line=' '.join(line.split())
        if not line:continue
        if line.casefold() in headings:
            path=headings[line.casefold()];last_heading=line;pending='';continue
        match=re.search(r'((?:'+NUMBER+r'\s+){'+str(columns-1)+r'}'+NUMBER+r')\s*$',line)
        if not match:
            if line.endswith(':'):pending='';continue
            if re.search('[A-Za-z\u4e00-\u9fff]',line) and not re.search(r'\d,\d|Note|notes|For the|ended|Annual Report|Million|thousand|USD|RMB|US\$|202[0-9]|Consolidated|CONSOLIDATED',line):pending=(pending+' '+line).strip()
            else:pending=''
            continue
        prefix=line[:match.start()].strip()
        if re.fullmatch(r'[\d\s]+',match[0]) and not prefix and not last_heading:continue
        label=re.sub(r'\s+\d+(?:\([a-z0-9]+\))*(?:,\s*\d+)*$','',prefix).strip()
        if not re.search('[A-Za-z\u4e00-\u9fff]',label):
            if not last_heading:pending='';continue
            label=last_heading+' — subtotal'
        elif pending:label=pending+' '+label
        pending=''
        values=re.findall(NUMBER,match[1])
        if len(values)!=columns:continue
        rowpath=path
        low=label.casefold()
        if path.startswith('income'):
            rowpath='income'
            if re.search(r'^(revenue|revenues|net sales|value-added services|marketing services|fintech and business services|others)( — subtotal)?$',low):rowpath='income/revenue/sales'
            elif low.startswith('cost of'):rowpath='income/revenue/cost'
            elif low=='gross profit':rowpath='income/revenue/gross'
            elif re.search(r'^(selling|administrative|research and development|general and administrative)',low):rowpath='income/expenses/operating'
            elif low in {'operating profit','operating income (loss)'}:rowpath='income/profit/operating'
            elif 'before' in low and ('tax' in low or 'taxation' in low):rowpath='income/profit/pretax'
            elif low in {'income tax expense','income taxes','income tax expenses'}:rowpath='income/expenses/tax'
            elif 'per share' in low or low in {'– basic','– diluted','basic','diluted'}:rowpath='income/profit/eps'
            elif re.search(r'^(profit for|loss for|net income|equity holders|owners of|non-controlling)',low):rowpath='income/profit/net'
        if low=='total assets':rowpath='balance/assets/total'
        elif low=='total liabilities':rowpath='balance/liabilities/total'
        elif low in {'total equity','total equity and liabilities','total liabilities and equity'}:rowpath='balance/equity/total'
        if path.startswith('cashflow') and 'net cash' in low:
            for kind in ['operating','investing','financing']:
                if kind+' activities' in low:rowpath=f'cashflow/{kind}/net'
        out.append({'label':label,'values':values,'line':original,'account_path':rowpath})
        path=(path_after_labels or {}).get(label,path)
    return out

def import_plan(path,plan):
    accepted=[];audit=[]
    with closing(sqlite3.connect(path)) as db,db:
        db.row_factory=sqlite3.Row
        state=db.execute("SELECT value FROM snapshot_metadata WHERE key='state'").fetchone()
        if state and state[0]=='published_public_library.v1':raise ValueError('immutable_release_requires_build')
        for spec in plan['statements']:
            source=db.execute("SELECT * FROM sources WHERE id=? AND access_state='readable'",(spec['source_id'],)).fetchone()
            if not source:raise ValueError('source_not_readable')
            if not db.execute('SELECT 1 FROM entity_sources WHERE entity_id=? AND source_id=?',(spec['entity_id'],source['id'])).fetchone():raise ValueError('source_entity_mismatch')
            body=archived_text(db,source['id']);meta=json.loads(source['metadata'])
            known=source['published_at'] or (meta.get('known_at') or meta.get('captured_at',''))[:10]
            if not known:raise ValueError('known_date_required')
            for page in spec['pages']:
                section=body.split(f'[PDF page {page}]',1)[1].split('[PDF page ',1)[0]
                for quote in spec['context_quotes']:
                    if ' '.join(quote.split()) not in ' '.join(section.split()):raise ValueError(f'context_missing:{source["id"]}:{page}:{quote}')
                rows=extract_rows(section,spec['column_count'],spec['account_path'],spec.get('headings',{}),spec.get('path_after_labels',{}))
                for row in rows:
                    if row['account_path'] not in LABELS:raise ValueError('invalid_account_path')
                    mapping=spec.get('line_overrides',{}).get(row['label'],{})
                    concept=mapping.get('concept') or 'StatementLine_'+sha256((row['account_path']+'|'+row['label']).encode()).hexdigest()[:16]
                    for col in spec['columns']:
                        raw=row['values'][col['index']]
                        # A dash is a presentation symbol, not automatically a measured zero.
                        if raw in {'–','—','−','-'}:continue
                        unit=mapping.get('unit',spec['unit']);scale=mapping.get('scale',spec['scale'])
                        if row['account_path']=='income/profit/eps':
                            unit=spec['unit']+'/shares';scale=0.01 if 'cents' in row['line'] and spec['unit']=='USD' else 1
                        value=Decimal(raw.replace(',','').replace('(','-').replace(')',''))*Decimal(str(scale))
                        payload={'normalization':'reviewed_statement_page_and_column','pdf_page':page,'evidence_row':row['line'],
                            'source_value':raw,'scale':scale,'original_label':row['label'],'account_path':row['account_path'],
                            'date_basis':'source_publication' if source['published_at'] else 'known_at_capture_not_publication',
                            'accounting_basis':spec['accounting_basis'],'reporting_period':{'fiscal_year':col['year'],'period':col['period'],'basis':col['basis']},
                            'statement_context':spec['context_quotes'],'reviewed_at':plan['reviewed_at']}
                        identity=sha256(json.dumps([source['id'],concept,col,payload],sort_keys=True).encode()).hexdigest()
                        accepted.append((identity,spec['entity_id'],'issuer-reported',concept,mapping.get('label',row['label']),str(value),unit,col.get('start'),col['end'],known,None,col['period'],spec['form'],'',source['id'],json.dumps(payload,ensure_ascii=False)))
                audit.append({'entity_id':spec['entity_id'],'source_id':source['id'],'page':page,'rows':rows})
        db.executemany('INSERT OR IGNORE INTO financial_points VALUES('+','.join('?'*16)+')',accepted)
    return {'cells':len(accepted),'pages':audit}
