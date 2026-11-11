"""Source-bound public prediction snapshots; provider data is not a forecast truth."""
from hashlib import sha256
import json


def expectation_passage(*, rows, metadata, source_url, title, readback):
    text = json.dumps(metadata, ensure_ascii=False, sort_keys=True) + '\n' + '\n'.join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    digest = sha256(text.encode()).hexdigest()
    doc = 'WEB::EXPECTATIONS::' + digest
    return dict(result_state='source_bound_passage', passage_id=f'PASSAGE::{doc}::0::{digest[:16]}',
        document_id=doc, passage=text, content_sha256=digest, source_url=source_url, title=title,
        source_kind='market_expectations', source_role='external_public_source_unverified',
        source_read_method='provider_prediction_snapshot', writer_citable=True, numeric_fact_authority=False,
        source_locator=dict(source_url=source_url, captured_at=metadata['captured_at'],
            document_id=doc, content_sha256=digest, character_start=0, character_end=len(text)),
        readback=readback)


def alpha_response(result):
    """A 200/MCP success with an Information/Note payload is not financial data."""
    data = result.structured_content
    if data is None:
        texts = [b.text for b in result.content if getattr(b, 'type', '') == 'text']
        try:
            data = json.loads(texts[0]) if len(texts) == 1 else None
        except (ValueError, TypeError):
            data = None
    if isinstance(data, dict) and set(data) == {'result'}:
        data = data['result']
    if not isinstance(data, dict):
        return {'status': 'provider_invalid_response'}
    message = data.get('Information') or data.get('Note') or data.get('Error Message')
    if message or result.is_error:
        limited = any(w in str(message).lower() for w in ('rate limit', 'requests per', 'frequency', 'call volume'))
        return {'status': 'provider_rate_limited' if limited else 'provider_error', 'provider_message': message}
    return {'status': 'ok', 'data': data}
