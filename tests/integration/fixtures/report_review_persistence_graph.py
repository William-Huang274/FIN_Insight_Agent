"""Real verifier agent with a deterministic model, isolated qualification only.

No network model client is constructed. Decisions depend on persisted messages,
not a process-local reply counter, so restarting the worker is a meaningful test.
"""
import json
import os
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent

if os.getenv("FIN_REPORT_REVIEW_PERSISTENCE_QUALIFICATION") != "1":
    raise RuntimeError("isolated_report_review_qualification_only")


class PersistedReviewModel(BaseChatModel):
    @property
    def _llm_type(self):
        return "qualification-only-no-provider"

    def bind_tools(self, tools, **kwargs):
        assert {"read_review_history", "submit_report_review"} <= {t.name for t in tools}
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        current = json.loads(next(m.content for m in messages if isinstance(m, HumanMessage)))
        version = current["report"]["narrative_markdown"]
        # Model-facing projection retains only the current assignment, with
        # navigation to earlier receipts. Old private reasoning stays in storage.
        assert len([m for m in messages if isinstance(m, HumanMessage)]) == 1
        assert "history" in current
        reads = [m for m in messages if isinstance(m, ToolMessage) and m.name == "read_review_history"]
        if not reads:
            calls = [
                {"id": f"{version}-read-{i}", "name": "read_review_history",
                 "args": {"message_index": i}}
                for i in (1, 2)
            ]
            phase = "history_read"
        else:
            assert len(reads) == 2
            assert all(m.status == "success" for m in reads)
            public = "\n".join(m.content for m in reads)
            assert "PRIVATE_" not in public and "FY2027" in public and "CALC::a" in public
            calls = [{"id": f"{version}-submit", "name": "submit_report_review",
                      "args": {"review": {
                          "summary": f"Static persisted verification of {version}; this is engineering evidence, not financial certification.",
                          "completion": "complete", "findings": [], "unresolved_data_requests": []}}}]
            phase = "submission"
        path = Path(os.environ["FIN_PROBE_EVIDENCE"]) / "review-model-turns.jsonl"
        with path.open("a", encoding="utf-8") as out:
            out.write(json.dumps({"version": version, "phase": phase,
                                 "pid": os.getpid(), "provider_calls": 0}) + "\n")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(
            content="", tool_calls=calls, additional_kwargs={"reasoning_content": "PRIVATE_CURRENT"}))])


def graph(config):
    artifacts = CaseArtifacts.from_observed_sources(
        {}, case_id="static-persisted-review", research_as_of="2026-10-20")
    built = build_case_output_agent(role="verifier", model=PersistedReviewModel(),
        tools=[], artifacts=artifacts, limits={"model_calls": 4, "tool_calls": 6})
    # Agent Server supplies the actual PostgreSQL checkpointer.
    return built.builder.compile(
        interrupt_after=["tools"] if config.get("configurable", {}).get("pause_after_history") else [])
