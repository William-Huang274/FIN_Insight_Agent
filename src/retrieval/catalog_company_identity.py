"""Catalog-wide name compatibility; no test-company overrides or issuer merges."""
from collections import defaultdict
import re
import unicodedata


def name_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def cover_names(text):
    """Only explicit registrant-name captions, never body mentions or filenames."""
    names = []
    for match in re.finditer(r'\(\s*Exact name of registrant as specified in its charter\s*\)', text[:24000], re.I):
        lines = [s.strip(' _\t\r') for s in text[max(0,match.start()-400):match.start()].splitlines()]
        lines = [s for s in lines if s]
        # Text adapters can split a legal suffix across inline elements:
        # "CORP\nORATION". Rejoin only a recognized complete legal word,
        # never concatenate arbitrary neighboring text into a company name.
        if len(lines)>1:
            previous = lines[-2].rsplit(' ',1)
            combined = previous[-1]+lines[-1]
            if len(previous)==2 and combined.casefold() in {'corporation','incorporated','limited'}:
                lines[-1] = previous[0]+' '+combined
        if lines and 3 <= len(lines[-1]) <= 180 and re.search(r'[A-Za-z\u3400-\u9fff]', lines[-1]):
            name = lines[-1]
            if not any(c in name for c in '|[]<>') and name not in names:
                names.append(name)
    # Some SEC covers place the explicit registrant caption in a column
    # header. Use that exact column only when the original rows have a
    # consistent cell count; never guess through merged/misaligned cells.
    for table in re.finditer(r'\[TABLE:[^\n]*\]\n(.*?)\[/TABLE\]', text[:24000], re.S):
        rows = [line.split('|') for line in table[1].splitlines() if '|' in line]
        for i, cells in enumerate(rows):
            columns = [j for j,cell in enumerate(cells)
                       if re.search(r'Exact name of registrant(?:s)? as specified in (?:its|their) charter',cell,re.I)]
            if len(columns)!=1:
                continue
            column=columns[0]
            for row in rows[i+1:]:
                if len(row)!=len(cells):
                    break
                name=row[column].strip()
                if (3 <= len(name) <= 180 and re.search(r'\b(?:INC\.?|CORPORATION|CORP\.?|COMPANY|LIMITED|LTD\.?|PLC|LLC)\s*$',name,re.I)
                        and not any(c in name for c in '[]<>') and name not in names):
                    names.append(name)
    return names


def aliases_for(row):
    declared = [row.get('company_name'), *(row.get('verified_company_names') or [])]
    tail = (row.get('issuer_id') or '').split('::')[-1].replace('_', ' ').strip()
    if len(tail) >= 3:
        declared.append(tail)
    # Preserve the legal name. A shortened legal suffix is merely another
    # lookup alias; collisions remain explicit and never merge identities.
    result = set()
    for name in declared:
        if not isinstance(name, str) or not name.strip():
            continue
        name = unicodedata.normalize('NFKC', name).strip()
        result.add(name)
        short = re.sub(r'(?:[,\s]+(?:incorporated|corporation|limited|inc\.?|corp\.?|ltd\.?|plc|llc))+$', '', name, flags=re.I).strip()
        if len(name_key(short)) >= 3:
            result.add(short)
    return sorted(result)


def audit_catalog(metadata):
    names, filings, missing, collisions = defaultdict(set), defaultdict(set), [], []
    from .filing_document_identity import original_filing_key
    declared = defaultdict(set)
    for row in metadata.values():
        if row.get('issuer_id'):
            for alias in aliases_for(row):declared[name_key(alias)].add(row['issuer_id'])
    for document, row in metadata.items():
        issuer = row.get('issuer_id')
        if not row.get('company_name'):
            missing.append(document)
        for alias in aliases_for(row):
            names[name_key(alias)].update(owners_for_row(row, declared))
        key = original_filing_key(row.get('original_filing_key'))
        if key and issuer:
            filings[key].add(issuer)
    for alias, owners in sorted(names.items()):
        if len(owners) > 1:
            collisions.append({'normalized_alias':alias, 'issuer_ids':sorted(owners),
                               'resolution':'ambiguous_no_global_merge'})
    return {'documents':len(metadata), 'missing_company_name':missing,
        'alias_collisions':collisions, 'same_document_multiple_ids':[
            {'original_filing_key':k, 'issuer_ids':sorted(v)} for k,v in sorted(filings.items()) if len(v)>1],
        'identity_mutations':0, 'scope':'all_supplied_catalog_rows_not_only_evaluation_companies'}


def owners_for_row(row, declared_alias_owners):
    """Resolve name-only rows through all compatible names, retaining collisions."""
    if row.get('issuer_id'):
        return {row['issuer_id']}
    aliases = aliases_for(row)
    owners = set().union(*(declared_alias_owners.get(name_key(a), set()) for a in aliases)) if aliases else set()
    if owners:
        return owners
    name = row.get('company_name') or next(iter(row.get('verified_company_names') or []), None)
    return {'name:'+name.casefold()} if name else set()
