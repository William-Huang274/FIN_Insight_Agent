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
                lines[-2:] = [previous[0]+' '+combined]
        if lines and 3 <= len(lines[-1]) <= 180 and re.search(r'[A-Za-z\u3400-\u9fff]', lines[-1]):
            name = lines[-1]
            if not any(c in name for c in '|[]<>') and name not in names:
                # A joint cover can list consecutive legal names under ONE
                # (even singular) caption. Taking only the last line invents
                # a unique registrant and falsely attaches the archive CIK.
                joint=[]
                for line in reversed(lines):
                    if (not 3<=len(line)<=180 or any(c in line for c in '|[]<>()')
                            or not re.search(r'\b(?:INC\.?|INCORPORATED|CORPORATION|CORP\.?|COMPANY|LIMITED|LTD\.?|PLC|LLC|L\.?P\.?)\s*$',line,re.I)):
                        break
                    joint.append(line)
                for value in reversed(joint or [name]):
                    if value not in names:names.append(value)
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
                if (3 <= len(name) <= 180 and re.search(r'\b(?:INC\.?|CORPORATION|CORP\.?|COMPANY|LIMITED|LTD\.?|PLC|LLC|L\.?P\.?)\s*$',name,re.I)
                        and not any(c in name for c in '[]<>') and name not in names):
                    names.append(name)
    return names


def aliases_for(row):
    declared = [row.get('company_name'), *(row.get('verified_company_names') or []),
                *(row.get('joint_registrant_names') or [])]
    tail = (row.get('issuer_id') or '').split('::')[-1].replace('_', ' ').strip()
    # A legacy ID spelling is only a fallback. Once the original cover gives
    # an explicit registrant, an unrelated ID tail must not become a second
    # company alias (nor shorten a name merely because it shares a prefix).
    if len(tail) >= 3 and not row.get('verified_company_names') and not row.get('joint_registrant_names'):
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


def document_names(row):
    """Original names that locate a filing; joint names are NOT fact owners."""
    return list(dict.fromkeys(n for n in [row.get('company_name'),
        *(row.get('verified_company_names') or []), *(row.get('joint_registrant_names') or [])]
        if isinstance(n,str) and n.strip()))


def joint_reporting_targets(query, metadata):
    """Only an explicit complete legal name disambiguates joint registrants.

    A shared short name or the archive CIK does not identify the requested
    statement owner. Return an empty target for unresolved joint issuers so
    consumers cannot silently fall back to the document lookup aliases.
    """
    joint=defaultdict(dict)
    for row in metadata.values():
        if row.get('issuer_id'):
            for name in row.get('joint_registrant_names') or []:
                joint[row['issuer_id']].setdefault(name_key(name),name)
    result={}
    for issuer,names in joint.items():
        hits=legal_name_mentions(query,names.values())
        result[issuer]=sorted({h[2] for h in hits})
    return result


def legal_name_mentions(query,names):
    hits=[]
    for name in names:
        pattern=r'(?<![A-Za-z0-9_])'+r'[\W_]*'.join(re.escape(c) for c in name_key(name))+r'(?![A-Za-z0-9_])'
        for m in re.finditer(pattern,query,re.I):hits.append((m.start(),m.end(),name))
    return sorted(h for h in hits if not any(a<=h[0] and b>=h[1] and b-a>h[1]-h[0] for a,b,_ in hits))


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


def verified_issuer_groups(metadata):
    """Lookup compatibility from unique original CIKs, never identity mutation.

    Each participating parse ID needs a single registrant cover and exactly one
    consistent CIK across its observed rows. Joint registrants, conflicting CIKs
    and name-only homonyms cannot establish a group.
    """
    identifiers=defaultdict(set);covered=set();ambiguous=set();cover_aliases=defaultdict(set)
    for row in metadata.values():
        issuer=row.get('issuer_id')
        if not issuer:continue
        if row.get('company_name_resolution') in {'joint_registrants_not_a_unique_owner','original_cover_url_cik_conflict'}:ambiguous.add(issuer)
        names=row.get('verified_company_names') or []
        if len(names)==1:
            covered.add(issuer)
            cover_aliases[issuer].update(name_key(a) for a in aliases_for({'company_name':names[0]}))
        elif len(names)>1:ambiguous.add(issuer)
        for value in row.get('fact_entity_identifiers',[]):
            scheme=(value.get('scheme') or '').rstrip('/').casefold();identifier=value.get('identifier')
            if (scheme in {'http://www.sec.gov/cik','https://www.sec.gov/cik'}
                    and isinstance(identifier,str) and identifier.isascii() and identifier.isdigit()
                    and 0<int(identifier)<10**10):
                identifiers[issuer].add(str(int(identifier)))
    for row in metadata.values():
        issuer=row.get('issuer_id');name=row.get('company_name')
        # A reused local issuer ID with a different unverified name is not a
        # safe cross-document alias, even if another row has a valid cover.
        if issuer in covered and name and not row.get('verified_company_names'):
            declared={name_key(a) for a in aliases_for({'company_name':name})}
            if not declared & cover_aliases[issuer]:ambiguous.add(issuer)
    groups=defaultdict(set)
    for issuer,values in identifiers.items():
        if issuer in covered and issuer not in ambiguous and len(values)==1:
            groups[next(iter(values))].add(issuer)
    return [{'scheme':'http://www.sec.gov/CIK','identifier':cik,'issuer_ids':sorted(owners),
        'basis':'single_original_registrant_and_consistent_catalog_cik'}
        for cik,owners in sorted(groups.items()) if len(owners)>1]


def with_original_registrant_identity(row):
    """A unique original SEC cover plus its exact filing URL supplies a CIK.

    The URL alone is not a company-name oracle. Conflicting original metadata
    is reported and cannot establish an automatic identity compatibility group.
    """
    from .filing_document_identity import original_filing_key
    key=original_filing_key(row.get('original_filing_key'))
    result=dict(row)
    if (not key or len(row.get('verified_company_names') or [])!=1
            or row.get('company_name_resolution')=='joint_registrants_not_a_unique_owner'):return result
    cik=str(int(key.split('/data/')[1].split('/')[0]))
    if not 0<int(cik)<10**10:return result
    prior={str(int(v['identifier'])) for v in row.get('fact_entity_identifiers',[])
        if (v.get('scheme') or '').rstrip('/').casefold() in {'http://www.sec.gov/cik','https://www.sec.gov/cik'}
        and isinstance(v.get('identifier'),str) and v['identifier'].isascii() and v['identifier'].isdigit()}
    if prior and prior!={cik}:
        result['company_name_resolution']='original_cover_url_cik_conflict'
        return result
    if not prior:result['fact_entity_identifiers']=[{'scheme':'http://www.sec.gov/CIK','identifier':cik,
        'basis':'unique_original_registrant_cover_and_sec_archive_identity'}]
    return result
