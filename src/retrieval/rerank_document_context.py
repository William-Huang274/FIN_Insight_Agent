"""Document-level catalog context; never substitutes for a fact's period."""
from datetime import date
import json


def with_document_context(rows, metadata):
    """metadata must come from the verified, immutable source catalog."""
    from .same_original_metadata import resolve
    metadata = resolve(metadata)
    result = []
    for row in rows:
        source = metadata.get(row['parent_document_id'], {})
        context = {}
        for field in ('issuer', 'form', 'period_end'):
            value = source.get(field)
            if field == 'issuer' and value is None:
                names = source.get('verified_company_names') or []
                value = source.get('company_name') or (names[0] if len(names)==1 else None) or source.get('issuer_id')
            if value is None:
                continue
            if not isinstance(value, str) or not value or len(value) > 256:
                raise ValueError('rerank_invalid_document_metadata')
            if field == 'period_end' and date.fromisoformat(value).isoformat() != value:
                raise ValueError('rerank_invalid_document_period')
            context[field] = value
        result.append({**row, 'rerank_document_metadata': context})
    return result


def document_context_text(context):
    if not isinstance(context, dict) or set(context) - {'issuer', 'form', 'period_end'}:
        raise ValueError('rerank_invalid_document_metadata')
    # Revalidate even when another caller constructs the optional context.
    with_document_context([{'parent_document_id': 'document'}], {'document': context})
    if not context:
        return ''
    return ('Verified document catalog (period_end is the document reporting period, '
            'NOT the period of every fact in the excerpt):\n'
            + json.dumps(context, sort_keys=True, ensure_ascii=False))
