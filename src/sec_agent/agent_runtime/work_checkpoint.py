"""Research orientation using native messages and existing working notes.

This is an occasional reminder, not summarization, a scheduler or an evidence
store. LangGraph retains the original journal; the model owns its work index.
"""
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately


WORK_CHECKPOINT_GUIDANCE = """
At a meaningful research boundary (a question checked, a workpaper drafted, or
before switching topics), step back and reconcile the whole current assignment.
Use the existing working note as a concise work index: completed checks and their
paper/claim/source or calculation IDs; exact document/node/offset read arguments;
unresolved contradictions and failed reads; remaining required questions; the
next concrete action. Distinguish drafted, source-checked and still unverified.
Even if a paper is unfinished, index its completed parts before a long continuation.
Link exact original records; a note is neither Evidence nor a substitute for them.
For a known paper, recover the relevant claims or source window, not the whole
paper again unless the surrounding prose is needed to check consistency. For a
missing footnote, search inside the identified original document, inspect nearby
headings and table units, and distinguish consolidated from separate statements.
Keep the saved text and identifiers stable. Append only new progress/corrections
using the current version; do not paraphrase the entire index on every turn.
An old conclusion contradicted by new evidence is superseded, never silently
carried forward. Do not transcribe private reasoning. Use a few useful sentences,
not a second report or a log of every tool. One concise index may cover several
completed checks. Ordinary short work and final submission need no extra ritual.
Before final delivery, reconcile the opening thesis and final paragraph against
the checked periods, units, cash classifications and conditional assumptions.
Read the source's surrounding period/comparison words rather than inheriting a
draft's YoY/QoQ label. Reconcile the prose as well as its structured claim list;
one correct claim does not make contradictory prose correct. A scenario value
is not a necessary condition merely because it is labeled an inference: show
the relationship and check alternative revenue/margin/multiple assumptions, or
state it as one conditional scenario. Absent working context is not proof that
a previously successful read never occurred; inspect the retained index/notes.
"""

CHECKPOINT_NAME = "research_work_checkpoint"


class WorkCheckpointMiddleware(AgentMiddleware):
    """Append one stable notice per large interval, without rewriting the prefix.

Only enabled by builders offering working-note tools. A successful save or prior
notice starts a new interval. Failed saves do not count as completed organization.
The trigger counts approximate message tokens, not provider window capacity.
"""
    def __init__(self, trigger_tokens=48000):
        if trigger_tokens < 1:
            raise ValueError("work_checkpoint_trigger_must_be_positive")
        self.trigger_tokens = trigger_tokens

    def before_model(self, state, runtime):
        messages = state.get("messages", [])
        if state.get("review") or state.get("output"):
            return None
        # Never insert a message between an assistant call and its tool replies.
        if messages and isinstance(messages[-1], AIMessage):
            return None
        last_boundary = -1
        for i, message in enumerate(messages):
            if isinstance(message, SystemMessage) and message.name == CHECKPOINT_NAME:
                last_boundary = i
            elif isinstance(message, ToolMessage) and message.name == "WriteWorkingNote" and message.status != "error":
                import json
                try:
                    receipt = json.loads(message.content)
                except (ValueError, TypeError):
                    continue
                if isinstance(receipt, dict) and receipt.get("saved") is True:
                    last_boundary = i
        if count_tokens_approximately(messages[last_boundary + 1:]) < self.trigger_tokens:
            return None
        return {"messages": [SystemMessage(name=CHECKPOINT_NAME, content=
            "Research work checkpoint: substantial context has accumulated since the last work index or notice. "
            "Before switching topics or further broad reading, briefly reconcile completed checks, unresolved "
            "contradictions and remaining user questions. Save a concise progress index through WriteWorkingNote "
            "when useful, preserving exact original IDs/read arguments and the next unfinished action. "
            "Do not restart completed work, treat a note as verified evidence, or omit required checks. "
            "This notice does not compress history or add model-call authority; finish directly if the work is ready.") ]}
