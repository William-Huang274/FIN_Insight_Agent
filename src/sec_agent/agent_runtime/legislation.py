"""Official legislative navigation under the existing public-web grant."""
import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from langchain_core.tools import tool, ToolException
from .conversation_agent import GrantedTool
from .market_prices import task_cutoff
from sec_agent.research_foundation.congress_api import CongressAPI, bill_identity, congress_rendition_package
from sec_agent.research_foundation.external_sources import ExternalSourceError, StaticHTTPPageFetcher, PublicURLGuard
from sec_agent.research_foundation.government_publications import mods_bill_record
from sec_agent.research_foundation.dated_web_discovery import SearchReadOrigin


def legislation_tool(*, thread_id, cache_root, research_as_of=None, api=None, origin=None):
    root = Path(cache_root) / str(UUID(thread_id))
    client = api or CongressAPI()
    fetcher = SearchReadOrigin(origin or StaticHTTPPageFetcher(guard=PublicURLGuard()))
    cutoff = task_cutoff(research_as_of) or datetime.now(timezone.utc)
    cutoff_day = (cutoff - timedelta(microseconds=1)).date()
    lock = asyncio.Lock()

    async def cached(identity, section, offset, limit):
        from sec_agent.adapters.local_records import LocalRecords
        key = sha256(json.dumps([identity,section,offset,limit]).encode()).hexdigest()
        async with lock:
            with LocalRecords(str(root), size_limit=16*1024*1024) as cache:
                saved = cache.get(key)
            if saved is not None:
                return saved
            saved = await client.read(identity, section, offset, limit)
            with LocalRecords(str(root), size_limit=16*1024*1024) as cache:
                cache.set(key, saved, expire=3600)
            return saved

    @tool(response_format='content_and_artifact')
    async def read_legislation(query: str, operation: Literal['record','texts','actions']='record',
                               offset: int=0, limit: int=20):
        """Read Congress.gov official bill metadata, text versions or dated actions.
        query is a Congress.gov bill URL (overview or /text), or explicit
        congress/type/number, e.g. 119/hr/1. Never guess Congress from a bare number.
        For a topic, first use read_public_source search to identify a bill.
        record identifies the bill; texts lists versions and exact read_public_source
        calls for verified GovInfo renditions; actions reads procedural records.
        API metadata is not bill full text or proof of enactment. Choose versions,
        read their actual text and assess policy status. Paginate using next_offset;
        a returned page is not the full history. Current metadata is not a historic
        vintage; post-cutoff updated record fields are withheld. No API key argument.
        """
        try:
            if not 0 <= offset <= 100000 or not 1 <= limit <= 50:
                raise ValueError('congress_page_invalid; offset>=0, limit=1..50')
            identity = bill_identity(query)
            record = await cached(identity, 'record', 0, 20)
            bill = record['bill']
            introduced = bill.get('introducedDate', '')
            if not introduced or introduced > cutoff_day.isoformat():
                raise ValueError('bill_not_visible_at_task_cutoff')
            result = await cached(identity, operation, offset, limit) if operation != 'record' else record
            visible = {'operation':operation,'identity':dict(zip(('congress','type','number'), identity)),
                       'source_url':result['source_url'],'captured_at':result['captured_at'],
                       'research_as_of':research_as_of, 'cutoff_exclusive':cutoff.isoformat(),
                       'next_offset':result['next_offset'],
                       'availability':'current_api_response; not an archived as-of snapshot',
                       'writer_citable':False, 'full_text_read':False}
            if operation == 'record':
                updated = bill.get('updateDateIncludingText') or bill.get('updateDate')
                if not updated or datetime.fromisoformat(updated.replace('Z','+00:00')) >= cutoff:
                    visible.update(record={'introducedDate':introduced},
                        record_fields_withheld='Current record updated after cutoff or update time unknown; use dated actions and verified text versions.')
                else:
                    visible['record'] = bill
                visible['next_calls'] = [{'tool':'read_legislation','arguments':{'query':query,'operation':s}} for s in ('texts','actions')]
            elif operation == 'actions':
                visible['actions'] = [a for a in result['actions'] if a.get('actionDate') and a['actionDate'] <= cutoff_day.isoformat()]
                visible['omitted_date_count'] = len(result['actions'])-len(visible['actions'])
                visible['status_note'] = 'Action dates are filtered; publication/first availability of historical API rows is not established.'
            else:
                versions = []
                for row in result['textVersions']:
                    stamp = row.get('date')
                    if not stamp or stamp[:10] > cutoff_day.isoformat():
                        continue
                    version = {'type':row.get('type'), 'legislative_date':stamp, 'formats':row.get('formats',[]),
                               'full_text_read':False, 'read_options':[]}
                    packages = sorted({p for f in row.get('formats',[]) if (p := congress_rendition_package(f.get('url',''), identity))})
                    for package in packages:
                        metadata = f'https://www.govinfo.gov/metadata/pkg/{package}/mods.xml'
                        try:
                            page = await fetcher.fetch(metadata, timeout_seconds=15)
                            if page.final_url != metadata:
                                raise ExternalSourceError('govinfo_metadata_redirect')
                            target, issued, title = mods_bill_record(page.html, package, 'https://www.govinfo.gov/app/details/'+package)
                            if issued > cutoff_day:
                                continue
                            version['read_options'].append({'package_id':package,'publication_date':issued.isoformat(),
                                'source_url':target,'metadata_url':metadata,'title':title,
                                'read_call':{'tool':'read_public_source','arguments':{'operation':'search','query':target}}})
                        except ExternalSourceError as e:
                            version.setdefault('read_failures',[]).append({'package_id':package,'code':e.code})
                    versions.append(version)
                visible['text_versions'] = versions
                visible['omitted_date_count'] = len(result['textVersions'])-len(versions)
                visible['next_step'] = 'Choose a read_option, call read_public_source search then read its returned WEB ID. Version listing is not full-text reading.'
            artifact = json.loads(json.dumps(visible))
            artifact['snapshot_sha256'] = sha256(json.dumps(visible,sort_keys=True).encode()).hexdigest()
            return json.dumps(visible,ensure_ascii=False), artifact
        except (ValueError, ExternalSourceError) as e:
            raise ToolException('官方法案读取未完成，不代表没有法案：'+str(e)) from None
    read_legislation.handle_tool_error = True
    return GrantedTool(read_legislation, 'read', 'Congress.gov 官方法案、程序动作和文本版本；正文沿现有来源读取')
