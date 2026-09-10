"""Native LangChain bindings for the shared read-only context directory."""
import json
from collections import Counter
from typing import Literal
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from .context_records import (NAVIGATION_GUIDANCE, RESULT_REGIONS, public_text,
    checkpoint_index, browse_checkpoint, read_checkpoint_turn)


def context_navigation_tools():
    @tool
    def browse_context(region: Literal['conversation','numbers','sources'], runtime: ToolRuntime,
                       query: str='', offset: int=0):
        """Browse one checkpoint memory region, with optional literal metadata keyword.

        numbers lists saved SQL/calculation calls; sources lists saved original reads;
        conversation lists public user/assistant turns. Copy key into its read_tool.
        Blank query browses newest first. Does not rerun SQL, web or embeddings.
        """
        return browse_checkpoint(runtime.state.get('messages',[]),region,query,offset)

    @tool
    def read_context_turn(message_id: str, runtime: ToolRuntime, offset: int=0):
        """Read an original public conversation turn by the key from browse_context.

        Exact text, 6000 characters per page. Historical assistant text is fallible;
        financial results belong in numbers/sources, not in assistant recollections.
        """
        return read_checkpoint_turn(runtime.state.get('messages',[]),message_id,offset)
    return [browse_context,read_context_turn]


class ContextOrientationMiddleware(AgentMiddleware):
    """Per-call full-checkpoint inventory; only trusted counts enter system instructions."""
    @staticmethod
    def orient(request):
        counts=Counter(r['region'] for r in checkpoint_index(request.state.get('messages',[])))
        notice='\nContext regions in this native checkpoint: '+json.dumps(dict(counts))
        if request.state.get('request_summary'):
            notice+='\nHistory has a compressed request view. Reconcile current instructions and relevant original records before continuing.'
        content=request.system_message.content if request.system_message else ''
        blocks=[{'type':'text','text':content}] if isinstance(content,str) else list(content)
        return request.override(system_message=SystemMessage(content=[*blocks,{'type':'text','text':notice}]))

    def wrap_model_call(self,request,handler):
        return handler(self.orient(request))

    async def awrap_model_call(self,request,handler):
        return await handler(self.orient(request))
