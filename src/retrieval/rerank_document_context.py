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
        joint=source.get('joint_registrants') or source.get('joint_registrant_names')
        if joint is not None:
            if (not isinstance(joint,list) or not 2<=len(joint)<=32
                    or any(not isinstance(n,str) or not n.strip() or len(n)>256 for n in joint)):
                raise ValueError('rerank_invalid_joint_registrants')
            context['joint_registrants']=joint
        for field in ('issuer', 'form', 'period_end', 'fiscal_report_year'):
            if field=='issuer' and joint:continue
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
            if field == 'fiscal_report_year' and (
                    len(value) != 4 or not value.isascii() or not value.isdigit() or not 1900 <= int(value) <= 2099):
                raise ValueError('rerank_invalid_fiscal_report_year')
            context[field] = value
        result.append({**row, 'rerank_document_metadata': context})
    return result


def document_context_text(context):
    if not isinstance(context, dict) or set(context) - {'issuer', 'form', 'period_end','joint_registrants','fiscal_report_year'}:
        raise ValueError('rerank_invalid_document_metadata')
    # Revalidate even when another caller constructs the optional context.
    with_document_context([{'parent_document_id': 'document'}], {'document': context})
    if not context:
        return ''
    fiscal_note = ('fiscal_report_year is the original report heading, NOT every fact\'s fiscal year; '
                   if 'fiscal_report_year' in context else '')
    return ('Verified document catalog (' + fiscal_note + 'period_end is the document reporting period, '
            'NOT the period of every fact in the excerpt; joint_registrants locate the same filing, '
            'NOT interchangeable statement owners):\n'
            + json.dumps(context, sort_keys=True, ensure_ascii=False))
