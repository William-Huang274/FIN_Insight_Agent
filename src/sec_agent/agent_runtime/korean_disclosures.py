"""Official OpenDART disclosure discovery, with filing-date boundaries."""
from datetime import date, datetime, timezone
import json
import os
import re
from typing import Literal

import httpx
from langchain_core.tools import tool
from .conversation_agent import GrantedTool


def korean_disclosure_tool(*, research_as_of=None, transport=None):
    key = os.environ.get('OPENDART_API_KEY', '')
    if not key and transport is None:
        return None

    @tool(response_format='content_and_artifact')
    async def search_korean_disclosures(start_date: str, end_date: str,
                                       corporation_code: str = '',
                                       language: Literal['ko', 'en'] = 'ko',
                                       page: int = 1, limit: int = 20):
        """Search official Korean OpenDART filings by publication dates YYYY-MM-DD.
        With no corporation_code search at most three months; returned corp_code
        identifies the issuer (not its stock ticker). ko/en select official Korean
        or English catalogs; their coverage can differ. All revisions are retained.
        Returns filing IDs and original viewer links for read_public_source, not
        stock quotes, complete financial tables or proof of having read the filing.
        """
        out = dict(provider='opendart', research_as_of=research_as_of,
                   captured_at=datetime.now(timezone.utc).isoformat(), writer_citable=False)
        try:
            start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
            cutoff = date.fromisoformat(str(research_as_of)[:10]) if research_as_of else datetime.now(timezone.utc).date()
            if start > end or end > cutoff or not 1 <= limit <= 100 or page < 1:
                raise ValueError('date_or_pagination')
            if corporation_code and not re.fullmatch(r'\d{8}', corporation_code):
                raise ValueError('corporation_code')
            if not corporation_code and (end-start).days > 90:
                raise ValueError('limit_to_90_days_without_corporation_code')
        except ValueError:
            out.update(status='invalid_parameters', detail='Use valid YYYY-MM-DD dates <= cutoff, '
                       'start<=end, <=90 days without 8-digit corporation_code, page>=1 and limit=1..100.')
            return json.dumps(out), out
        base = 'https://engopendart.fss.or.kr/engapi' if language == 'en' else 'https://opendart.fss.or.kr/api'
        params = dict(crtfc_key=key, bgn_de=start.strftime('%Y%m%d'), end_de=end.strftime('%Y%m%d'),
                      page_no=page, page_count=limit, last_reprt_at='N', sort='date', sort_mth='desc')
        if corporation_code:
            params['corp_code'] = corporation_code
        try:
            async with httpx.AsyncClient(timeout=25, trust_env=False, transport=transport) as client:
                response = await client.get(base+'/list.json', params=params)
            out['source_url'] = base+'/list.json'  # never persist credential-bearing request URL
            if response.status_code != 200:
                out.update(status='provider_error', http_status=response.status_code)
            else:
                data = response.json()
                code = data.get('status')
                rows = data.get('list', []) if code == '000' else []
                visible = []
                for row in rows:
                    day = str(row.get('rcept_dt', ''))
                    receipt = str(row.get('rcept_no', ''))
                    if not re.fullmatch(r'\d{14}', receipt) or not (start.strftime('%Y%m%d') <= day <= end.strftime('%Y%m%d')):
                        continue
                    url = ('https://englishdart.fss.or.kr/dsbh001/main.do?rcpNo=' if language == 'en'
                           else 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=') + receipt
                    visible.append({**row, 'original_url': url})
                out.update(status='ok' if code in {'000', '013'} else 'provider_error',
                           provider_status=code, message=data.get('message'), rows=visible,
                           page=page, total_page=data.get('total_page'), total_count=data.get('total_count'),
                           coverage='Official filing catalog only; read the identified version before citing contents.')
        except Exception as exc:
            out.update(status='provider_unavailable', error_type=type(exc).__name__,
                       detail='OpenDART request failed; no automatic retry. This is not absence of filings.')
        return json.dumps(out, ensure_ascii=False), out

    return GrantedTool(search_korean_disclosures, 'read', '韩国官方 OpenDART 中英公告目录、申报日期及原件定位')
