"""Metered public search. Provider output is discovery material, never a source receipt."""
import asyncio
import hashlib
import json
from datetime import timedelta
import httpx

from sec_agent.adapters.model_dispatch_store import DispatchBlocked
from sec_agent.research_foundation.external_sources import ExternalSourceError, ProviderHit


class DeepSeekWeb:
    provider_id = 'deepseek_search'
    unit_micros = 750  # USD per nonempty Search / Fetch response.

    def __init__(self, *, api_key, budget, thread_id, guard, transport=None,
                 run_id=None, recovery_authorized=False):
        self.key, self.budget, self.thread, self.guard = api_key, budget, thread_id, guard
        self.transport = transport
        self.scope = 'deepseek-web:' + thread_id + (':' + run_id if run_id else '')
        self.recovery_authorized = bool(run_id and recovery_authorized)
        self.blocked = set()
        # The shared budget gate forbids another dispatch while a request is
        # unresolved. Queue this client's parallel date/fetch checks; don't
        # misreport an in-flight sibling as a failed remote search.
        self._dispatch_lock = asyncio.Lock()

    async def _post(self, action, payload):
        async with self._dispatch_lock:
            return await self._dispatch(action, payload)

    async def _dispatch(self, action, payload):
        b = self.budget
        wire = json.dumps([self.thread, action, payload], sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(wire.encode()).hexdigest()
        key = 'deepseek-web-v1:' + digest
        scope = self.scope
        policy = {'provider':'deepseek', 'tool':action, 'harness_execution_scope':scope,
                  'request':payload}
        try:
            old = await asyncio.to_thread(b.store.lookup, b.owner, b.budget, key)
            # Successful queries remain task-wide cache entries. An admitted
            # recovery can branch an unresolved request, never erase its hold.
            # Follow prior retry receipts before deciding to spend again.
            while old is not None and old['status'] != 'received':
                retry_key = key + ':retry:' + str(old['call_id'])
                retry = await asyncio.to_thread(b.store.lookup, b.owner, b.budget, retry_key)
                if retry is not None:
                    key, old = retry_key, retry
                    continue
                if (not self.recovery_authorized
                        or old.get('basis', {}).get('harness_execution_scope') == scope):
                    raise ExternalSourceError('deepseek_web_prior_call_unresolved')
                policy.update(retry_of=str(old['call_id']), recovery_execution_scope=scope)
                key, old = retry_key, None
            if old is not None:
                if old['status'] != 'received':
                    raise ExternalSourceError('deepseek_web_prior_call_unresolved')
                receipt = old['response']
            else:
                if action in self.blocked:
                    raise ExternalSourceError('deepseek_web_route_unavailable')
                reservation = await asyncio.to_thread(b.store.reserve, b.owner, b.budget, key, digest,
                    self.unit_micros, policy, currency='USD', execution_scope=scope)
                if reservation['status'] == 'received':
                    receipt = reservation['response']
                else:
                    receipt = await self._send(action, payload, key)
        except DispatchBlocked as exc:
            raise ExternalSourceError('deepseek_web_dispatch_blocked') from exc
        if receipt.get('error'):
            raise ExternalSourceError(receipt['error'])
        return receipt['data']

    async def _send(self, action, payload, key):
        b = self.budget
        try:
            async with httpx.AsyncClient(timeout=20, transport=self.transport) as client:
                response = await client.post('https://api.deepseek.com/v1/tools/' + action,
                    json=payload, headers={'Authorization':'Bearer ' + self.key})
            if response.status_code != 200:
                if response.status_code in (401, 402, 429):
                    self.blocked.add(action)
                receipt, cost = {'error':f'deepseek_{action}_http_{response.status_code}'}, 0
            else:
                obj = response.json()
                if action == 'search':
                    rows = obj['results']
                    if not isinstance(rows, list):
                        raise ValueError('invalid_search_schema')
                    # Keep ranked locators, not provider summaries or page bodies.
                    data = [{k:r.get(k) for k in ('url','title','date')} for r in rows]
                else:
                    content = obj['content']
                    if not isinstance(content, str):
                        raise ValueError('invalid_fetch_schema')
                    data = content[:200000]
                receipt, cost = {'data':data}, self.unit_micros if data else 0
            await asyncio.to_thread(b.store.received, b.owner, b.budget, key, receipt, cost)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
            await asyncio.to_thread(b.store.unknown, b.owner, b.budget, key)
            raise ExternalSourceError('deepseek_web_response_unconfirmed') from exc
        return receipt

    async def search(self, request):
        query = request.query.strip()
        if len(query) > 128:
            raise ExternalSourceError('deepseek_query_exceeds_128_characters')
        if request.end_published_date:
            dated = f"{query} before:{request.end_published_date + timedelta(days=1)}"
            if len(dated) <= 128:
                query = dated
        rows = await self._post('search', {'query':query, 'count':min(50,request.max_results),
                                          'need_content':False})
        return [ProviderHit(title=row['title'] or row['url'],url=row['url'],published_at=row['date'])
                for row in rows if isinstance(row.get('url'),str)]

    async def fetch_markdown(self, url):
        canonical = await asyncio.to_thread(self.guard.validate, url)
        return await self._post('fetch', {'url':canonical})
