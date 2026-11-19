"""Thin navigation over the TWSE's published OpenAPI, not a local scraper."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal
from uuid import UUID

import httpx
from langchain_core.tools import tool
from .conversation_agent import GrantedTool

TWSE_PATHS = {'issuers': 't187ap03_L', 'announcements': 't187ap04_L'}


def regional_disclosure_tool(*, thread_id, cache_root, research_as_of=None, transport=None):
    root = Path(cache_root) / str(UUID(thread_id))
    lock = asyncio.Lock()

    @tool(response_format='content_and_artifact')
    async def read_regional_disclosures(operation: Literal['issuers', 'announcements'],
                                        query: str = '', offset: int = 0, limit: int = 10):
        """Read Taiwan TWSE official company directory or current material announcements.
        query filters exact substrings such as an issuer code, Traditional Chinese
        company name or topic. offset/limit paginate the matched current snapshot.
        This is a current official catalog, NOT full historical MOPS search or a
        complete filings archive. Historical tasks receive issuer identity and
        website navigation only; current announcement bodies are withheld unless
        the snapshot is available by the task cutoff. Follow dated originals with
        read_public_source. The catalog is saved for read_saved_result, not promoted
        automatically to a financial citation. Japan/Korea keys and HK feeds are
        separate services, not implicit coverage of this tool.
        """
        if offset < 0 or not 1 <= limit <= 50 or len(query) > 200:
            data = {'status': 'invalid_parameters', 'detail': 'offset>=0, limit=1..50, query<=200 characters'}
            return json.dumps(data), data
        url = 'https://openapi.twse.com.tw/v1/opendata/' + TWSE_PATHS[operation]
        try:
            from sec_agent.adapters.local_records import LocalRecords
            async with lock:
                with LocalRecords(str(root), size_limit=16*1024*1024) as cache:
                    snapshot = cache.get(operation)
                if snapshot is None:
                    async with httpx.AsyncClient(timeout=20, transport=transport, follow_redirects=False) as client:
                        r = await client.get(url)
                    if r.status_code != 200:
                        data = {'status': 'provider_error', 'http_status': r.status_code, 'source_url': url}
                        return json.dumps(data), data
                    rows = r.json()
                    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                        raise ValueError('twse_response_schema_invalid')
                    snapshot = {'captured_at': datetime.now(timezone.utc).isoformat(), 'rows': rows}
                    with LocalRecords(str(root), size_limit=16*1024*1024) as cache:
                        cache.set(operation, snapshot, expire=600)
            historical = bool(research_as_of and str(research_as_of)[:10] < snapshot['captured_at'][:10])
            data = {'status': 'ok', 'source_url': url, 'captured_at': snapshot['captured_at'],
                    'research_as_of': research_as_of, 'writer_citable': False,
                    'availability': 'current TWSE snapshot; not a complete historical archive'}
            rows = snapshot['rows']
            if historical and operation == 'announcements':
                data.update(status='historical_vintage_unverified', rows=[],
                            detail='Current announcement snapshot withheld. Use dated publisher originals; this is not a no-disclosure result.')
                return json.dumps(data, ensure_ascii=False), data
            if historical:
                # Navigation only: do not expose current capital/management as
                # historical facts. Company naming can itself change over time.
                rows = [{k: v for k, v in row.items() if k in {'公司代號', '公司名稱', '公司簡稱', '網址'}} for row in rows]
                data['availability'] = 'current issuer identity/navigation only; names not established as historical'
            rows = [r for r in rows if not query or query.casefold() in json.dumps(r, ensure_ascii=False).casefold()]
            data.update(total_matches=len(rows), offset=offset, rows=rows[offset:offset+limit],
                        next_offset=offset+limit if offset+limit < len(rows) else None)
        except Exception as exc:
            data = {'status': 'provider_unavailable', 'source_url': url, 'error_type': type(exc).__name__,
                    'detail': 'Official catalog request failed; no automatic retry and no inference of absent disclosures.'}
        return json.dumps(data, ensure_ascii=False), data

    return GrantedTool(read_regional_disclosures, 'read', '台湾证交所官方目录和当前重大讯息；明确历史版本边界')
