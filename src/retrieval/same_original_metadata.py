"""Recover navigation fields only across the exact same authorized original.

No issuer merge, accession-level join, title inference or financial fact join.
An exhibit and the filing that links it have different document keys.
"""
from collections import defaultdict
from .filing_document_identity import original_filing_key

FIELDS = ('form', 'period_end', 'publication_date', 'calendar_annual_year')
DERIVED = 'same_original_metadata_resolution'


def resolve(metadata):
    groups = defaultdict(list)
    for document, row in metadata.items():
        key = original_filing_key(row.get('original_filing_key'))
        if key and row.get('evidence_role') != 'discovery_metadata_only':
            groups[key].append((document, row))
    output = {document:{k:v for k,v in row.items() if k != DERIVED} for document,row in metadata.items()}
    for key, entries in groups.items():
        for field in FIELDS:
            # Conflicting cover metadata must remain unresolved in every parse
            # of that same original, not be filled from a convenient neighbor.
            conflict = any(field in row.get('metadata_conflicts', []) for _,row in entries)
            values = {row[field] for _,row in entries if row.get(field)}
            if conflict or len(values)>1:
                for document,_ in entries:
                    output[document].setdefault(DERIVED,{})[field] = {'state':'conflict','original_filing_key':key}
                    output[document][field] = None
                continue
            if len(values)!=1:
                continue
            value = next(iter(values))
            sources = sorted(document for document,row in entries if row.get(field)==value)
            for document,row in entries:
                if row.get(field):
                    continue
                output[document][field] = value
                output[document].setdefault(DERIVED,{})[field] = {
                    'state':'resolved_from_exact_original','original_filing_key':key,
                    'source_documents':sources,'value':value}
    return output
