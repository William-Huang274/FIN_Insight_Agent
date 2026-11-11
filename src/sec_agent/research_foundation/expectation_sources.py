"""Source-bound public prediction snapshots; provider data is not a forecast truth."""
from hashlib import sha256
import json
from datetime import datetime
from urllib.parse import parse_qs, urlsplit


def valid_prediction_snapshot_identity(item):
    """Validate the native provider receipt, including older saved snapshots.

    These are JSON observations, not HTML captures. Their content-addressed
    document includes the capture time and provider metadata. Never fabricate a
    web capture receipt or refresh the observation while restoring its identity.
    The caller must already have authenticated the task-owned receipt stream.
    """
    try:
        text = item['passage']
        lines = text.splitlines()
        metadata = json.loads(lines[0])
        rows = [json.loads(line) for line in lines[1:]]
        locator = item['source_locator']
        captured = metadata['captured_at']
        url = urlsplit(item['source_url'])
        function = {'estimates': 'EARNINGS_ESTIMATES', 'earnings_history': 'EARNINGS'}[metadata['dataset']]
        canonical = expectation_passage(rows=rows, metadata=metadata,
            source_url=item['source_url'], title=item.get('title'), readback=item.get('readback'))
        return (item.get('source_read_method') == 'provider_prediction_snapshot'
            and item.get('source_kind') == 'market_expectations'
            and metadata['provider'] == 'alpha_vantage_official_mcp'
            and datetime.fromisoformat(captured).utcoffset() is not None
            and locator['captured_at'] == captured
            and url.scheme == 'https' and url.netloc == 'www.alphavantage.co' and url.path == '/query'
            and parse_qs(url.query) == {'function': [function], 'symbol': [metadata['symbol']]}
            and bool(rows) and all(isinstance(row, dict) for row in rows)
            and all(item[key] == canonical[key] for key in
                ('document_id', 'passage_id', 'passage', 'content_sha256', 'source_locator')))
    except (KeyError, ValueError, TypeError, AttributeError, IndexError):
        return False


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
