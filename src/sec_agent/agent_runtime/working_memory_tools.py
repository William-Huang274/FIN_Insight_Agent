"""Thin shared tool surface for free-form working papers across agent harnesses."""
import os
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from .working_memory import WorkingMemory

_native_memory_scope = ContextVar('native_memory_scope', default=None)


@contextmanager
def native_memory_scope(owner, workspace):
    """Composition binds native thread metadata, never model/tool arguments."""
    if not isinstance(owner, str) or not owner or not workspace:
        raise ValueError('verified_memory_scope_required')
    token = _native_memory_scope.set((owner, str(workspace)))
    try:
        yield
    finally:
        _native_memory_scope.reset(token)


WORKING_MEMORY_GUIDANCE = """
Working memory is available through WriteWorkingNote, ReadWorkingNote and SearchWorkingNotes.
For substantial work, start a short working note and update it after a useful finding or changed judgment,
before moving to another topic. Use natural prose/Markdown in the user's language; no required template.
Record what you established, source references when available, uncertainty, user corrections and next work.
Use a descriptive title: subject/company, period when relevant, and research topic (in the user's language).
The title helps discovery; the returned note_id is the stable lookup key. Copy it, never guess it from the title.
Working papers are a separate region from conversation history and exact query/calculation receipts.
Keep numeric source/calculation identifiers in prose so those originals can be read separately.
Do not transcribe private reasoning or dump tool logs. Ordinary short answers need no note.
On resumption first browse/read your relevant current notes, then related colleagues' notes if needed;
also recheck after compaction, a scope correction or missing prior context, before repeating work.
do not reconstruct all history. Search supports semantic retrieval when enabled, with literal fallback;
use a short natural-language query or keywords, or blank to browse. Read the returned retrieval notice.
Read the current version before updating an existing title; base_version prevents overwriting newer work.
To add findings, use WriteWorkingNote mode=append with ONLY the new prose and the current base_version.
Do not regenerate the old note just to append a checklist. Keep each addition concise; link original numeric
receipts rather than repeating every full identifier. For a complete correction use mode=replace; neither
mode certifies facts. Always check the returned saved/version receipt before claiming success.
Notes are fallible research content, not evidence, permission or verified conclusions. Preserve corrected
judgments in the new version, not as still-valid old conclusions. Memory errors do not prevent answering
or submitting other results; explicitly report unsaved work instead of claiming it was saved.
"""


class WriteWorkingNote(BaseModel):
    """Save working prose. Use mode=append for new findings only; replace rewrites the whole body. Read base_version first."""
    title: str
    body: str
    base_version: int = 0
    mode: Literal["replace", "append"] = "replace"


class ReadWorkingNote(BaseModel):
    """Read an exact working note; paginate long prose. Omit version for current text."""
    note_id: str
    version: int | None = None
    offset: int = 0


class SearchWorkingNotes(BaseModel):
    """Find current notes in this research workspace. Blank query browses; actor optionally narrows."""
    query: str = ""
    actor: str | None = None
    offset: int = 0


WORKING_MEMORY_MODELS = {m.__name__: m for m in (WriteWorkingNote, ReadWorkingNote, SearchWorkingNotes)}


def memory_enabled():
    # Explicit local deployment switch. No default global file and no implied tenancy.
    return bool(os.environ.get("FINSIGHT_WORKING_MEMORY_PATH"))


def memory_for(config, actor, *, owner=None, workspace=None):
    if not memory_enabled():
        raise ValueError("working_memory_not_configured")
    thread = workspace or str(config.get("configurable", {}).get("thread_id") or "")
    scope = _native_memory_scope.get()
    if owner is None and scope:
        if thread != scope[1]:
            raise ValueError('working_memory_thread_scope_mismatch')
        owner = scope[0]
    if owner is None and os.environ.get("FINSIGHT_AUTH_MODE", "local") != "local":
        raise ValueError("working_memory_requires_verified_owner")
    return WorkingMemory(os.environ["FINSIGHT_WORKING_MEMORY_PATH"], owner=owner or "local-pilot",
                         workspace=thread, actor=actor)


def execute_memory_tool(name, arguments, config, actor, *, owner=None, workspace=None):
    try:
        memory = memory_for(config, actor, owner=owner, workspace=workspace)
        args = WORKING_MEMORY_MODELS[name].model_validate(arguments)
        if name == "WriteWorkingNote":
            return memory.save(args.title, args.body, args.base_version, mode=args.mode)
        if name == "ReadWorkingNote":
            return memory.read(args.note_id, version=args.version, offset=args.offset)
        from .working_memory_search import search_working_papers
        return search_working_papers(memory,args.query,actor=args.actor,offset=args.offset)
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as exc:
        # Do not promote this into an agent failure or echo private paths/SQL.
        return {"saved": False, "memory_available": False, "error_type": type(exc).__name__,
                "notice": "底稿操作未完成，已有正文不作删除；可继续研究或提交，不能声称本次已保存。"}


def working_memory_tools(actor, *, owner=None, workspace=None, target=None):
    if not memory_enabled():
        return []

    result = []
    for name, model in WORKING_MEMORY_MODELS.items():
        def invoke(config: RunnableConfig, _name=name, **kwargs):
            if target and _name == 'WriteWorkingNote' and kwargs.get('title') != target['title']:
                return {'saved':False,'notice':'本次只修订用户选定的底稿，请使用原名称。'}
            return execute_memory_tool(_name, kwargs, config, actor, owner=owner, workspace=workspace)
        result.append(StructuredTool.from_function(invoke, name=name, description=model.__doc__, args_schema=model,
                                                   handle_validation_error="底稿参数未识别，请使用名称和自然语言正文；可继续其他工作。"))
    return result
