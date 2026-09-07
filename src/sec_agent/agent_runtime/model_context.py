"""Request-only use of LangChain's existing tool-history edit.

No summaries, source store or memory engine. Native/legacy histories and their
tool artifacts remain unchanged; both provider paths share this projection.
"""
from copy import deepcopy

from langchain.agents.middleware import ClearToolUsesEdit
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately


REREADABLE_TOOLS = frozenset({
    "read_research_artifact", "read_current_workpaper", "read_research_source",
    "read_current_source", "read_source_document", "query_company_financial_facts",
    "RequestEvidenceAction", "RequestFinanceAction", "RequestSourceAction", "ReadWorkpaperAction",
})


def project_tool_history(messages, *, trigger_tokens=None, keep=6):
    if trigger_tokens is None:
        return messages
    names = {call["id"]: call["name"] for m in messages if isinstance(m, AIMessage) for call in m.tool_calls}
    protected = {m.name or names.get(m.tool_call_id) for m in messages
                 if isinstance(m, ToolMessage) and m.status == "error"}
    known = set(names.values()) | {m.name for m in messages if isinstance(m, ToolMessage)}
    edit = ClearToolUsesEdit(trigger=trigger_tokens, keep=keep, clear_tool_inputs=False,
        exclude_tools=tuple(sorted(name for name in known if name and (name not in REREADABLE_TOOLS or name in protected))),
        placeholder="[Older read result omitted from this request; the host retains the original. Repeat the same read tool and arguments when its source context is needed.]")
    projected = deepcopy(list(messages))
    edit.apply(projected, count_tokens=count_tokens_approximately)
    return projected
