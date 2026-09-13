"""Personal research bookmarks in native Store; originals stay in checkpoints."""
from hashlib import sha256
import json
from typing import Literal
from langchain_core.tools import tool, ToolException


async def remember_research(sdk, thread_id, owner):
    thread=await sdk.threads.get(thread_id)
    if thread.get('metadata',{}).get('owner_id','local-pilot') != owner:
        raise ValueError('研究不属于当前用户')
    state=await sdk.threads.get_state(thread_id)
    values=state.get('values',{})
    if thread.get('status') in {'busy','error'} or values.get('phase') not in {'human_completed','human_reviewed_not_released'}:
        raise ValueError('仅保存已人工确认完成的研究；未完成结果仍在原窗口')
    checkpoint=state['checkpoint']['checkpoint_id']
    from .user_context import current_user_context
    context=current_user_context(owner,thread_id)
    key=sha256(json.dumps([thread_id,checkpoint,context['version']],ensure_ascii=False).encode()).hexdigest()
    value={'source_thread':thread_id,'checkpoint_id':checkpoint,'title':values['report']['title'],
        'report_version':values['report_version'],'human_edit_count':len(values.get('human_edits',[])),
        'task_requirements':context['body'],'requirements_version':context['version'],
        'scope':'Only this research; not automatically a global user preference',
        'authority':'Human-reviewed research, not verified source facts'}
    await sdk.store.put_item(['finsight-research-memory',owner],key,value,index=False)
    return {'memory_id':key,**value}


def research_memory_tools(sdk,owner):
    from .conversation_agent import GrantedTool
    namespace=['finsight-research-memory',owner]

    @tool
    async def list_research_memory(query: str = '', offset: int = 0):
        """Find completed research across this user's windows by title/company, or browse.

        Returns versioned pointers, not facts. Browse pages when title search
        misses; select a region with read_research_memory. Never mix requirements
        with observed numbers or silently treat past plans as current requests.
        """
        if offset<0:raise ToolException('offset必须为非负整数')
        result=await sdk.store.search_items(namespace,limit=50,offset=offset)
        rows=result['items']
        return {'items':[{'memory_id':r['key'],**r['value']} for r in rows if not query or query.casefold() in r['value']['title'].casefold()],
            'next_offset':offset+50 if len(rows)==50 else None,'notice':'目录按标题检索；无匹配不代表没有资料。可留空浏览。'}

    @tool
    async def read_research_memory(memory_id: str, region: Literal['report','papers','numbers','requirements']='report', offset: int=0):
        """Read one fixed-version research memory region; paginate without summarizing.

        Report/papers are fallible research prose; numbers are original citation
        objects, requirements belong to that task only. Current user corrections
        override prior plans. Follow source bindings before using numbers.
        """
        if offset<0:raise ToolException('offset必须为非负整数')
        row=await sdk.store.get_item(namespace,memory_id)
        if not row:raise ToolException('当前用户没有这份研究记忆')
        ref=row['value'];thread=await sdk.threads.get(ref['source_thread'])
        if thread.get('metadata',{}).get('owner_id','local-pilot')!=owner:raise ToolException('原研究权限已变化')
        state=await sdk.threads.get_state(ref['source_thread'],checkpoint={'checkpoint_id':ref['checkpoint_id'],'checkpoint_ns':''})
        values=state.get('values',{})
        if region=='numbers':
            entries=list((values.get('report') or {}).get('citations',{}).items())
            selected=entries[offset:offset+4]
            return {'citation_bindings':dict(selected),'next_offset':offset+4 if offset+4<len(entries) else None,
                'notice':'原始引用对象，包含来源、期间与单位；研究判断不是数字事实。'}
        if region=='requirements':text=ref.get('task_requirements','')
        elif region=='report':text=(values.get('report') or {}).get('narrative_markdown','')
        else:
            from .research_session import current_task_artifacts
            artifacts=current_task_artifacts(values)
            corrected={p['paper_id']:p['after'] for h in values.get('human_edits',[]) for p in h['papers']}
            text='\n\n'.join(p['branch_id']+' — '+p['thesis']+'\n'+corrected.get(p['paper_id'],artifacts.read_paper(p['paper_id'])['narrative_markdown']) for p in artifacts.catalog()['papers'])
        return {'region':region,'body':text[offset:offset+8000],'next_offset':offset+8000 if offset+8000<len(text) else None,
            'source_thread':ref['source_thread'],'report_version':ref['report_version'],'notice':ref['authority']+'; '+ref['scope']}

    result=[GrantedTool(list_research_memory,'read','同用户已完成研究目录'),GrantedTool(read_research_memory,'read','固定版本的分区研究记忆')]
    for g in result:g.tool.handle_tool_error=True
    return result
