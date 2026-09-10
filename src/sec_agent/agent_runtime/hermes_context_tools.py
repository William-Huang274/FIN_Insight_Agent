"""Read-only views over the pinned Hermes SessionDB, with host-bound session scope.

Hermes owns history and IDs. FIN only filters public turns into the shared reader;
no parallel transcript database and no model-provided session identifier.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from langchain_core.messages import AIMessage, HumanMessage
from .context_records import browse_checkpoint, read_checkpoint_turn


class BrowseContext(BaseModel):
    """Find original public messages in this session; blank query browses newest first.

    Working papers have their own SearchWorkingNotes/ReadWorkingNote tools.
    This Hermes pilot has no SQL/source tools; empty regions mean unavailable here.
    """
    model_config = ConfigDict(extra='forbid')
    region: Literal['conversation', 'numbers', 'sources']
    query: str = Field(default='', max_length=500)
    offset: int = Field(default=0, ge=0)


class ReadContextTurn(BaseModel):
    """Read original public text using an exact key returned by browse_context.

    Copy the key; historical assistant prose is fallible, not financial evidence.
    """
    model_config = ConfigDict(extra='forbid')
    message_id: str
    offset: int = Field(default=0, ge=0)


CONTEXT_MODELS = {'browse_context': BrowseContext, 'read_context_turn': ReadContextTurn}


def public_session_messages(rows):
    result = []
    for row in rows:
        cls = {'user': HumanMessage, 'assistant': AIMessage}.get(row.get('role'))
        if cls and row.get('id') is not None and not row.get('is_compaction_summary'):
            content = row.get('content') or ''
            if isinstance(content, (str, list)):
                result.append(cls(id=str(row['id']), content=content))
    return result


def execute_context_tool(name, parameters, rows):
    args = CONTEXT_MODELS[name].model_validate(parameters).model_dump()
    messages = public_session_messages(rows)
    if name == 'browse_context':
        result = browse_checkpoint(messages, **args)
        result['retrieval'] = 'hermes_native_session_literal_no_remote_calls'
        result['notice'] = '本会话公开原文；底稿单独检索。此 Hermes 试用未开放数字查询和外部来源工具。'
        return result
    return read_checkpoint_turn(messages, **args)
