"""Production convergence routing and native child agents, scripted decisions only."""
import json
import os
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent
from sec_agent.agent_runtime.research_convergence import build_research_convergence_graph

if os.getenv("FIN_REPORT_REVIEW_PERSISTENCE_QUALIFICATION") != "1":
    raise RuntimeError("isolated_report_convergence_qualification_only")


class ConvergenceModel(BaseChatModel):
    actor: str
    round_index: int
    citation: str

    @property
    def _llm_type(self):
        return "qualification-only-convergence"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        body = json.loads(next(m.content for m in messages if isinstance(m, HumanMessage)))
        phase = "submission"
        if self.actor == "writer":
            prose = (
                "Deterministic convergence fixture. This paragraph exercises saved source identity, "
                "report corrections and independent review routing; it does not establish a financial conclusion. "
            ) * 2 + f"\nRevision {self.round_index}. [{self.citation}]"
            name, args = "submit_case_report", {
                "report": {"title": "Persisted convergence fixture", "narrative_markdown": prose}}
        else:
            assert body["review_target"] == "final_report"
            assert f"Revision {self.round_index}." in body["report"]["narrative_markdown"]
            receipts = [m for m in messages if isinstance(m, ToolMessage)]
            if not receipts:
                if self.round_index == 0:
                    name, args = "read_current_source", {"source_id": self.citation}
                else:
                    prior = next(r for r in body["history"]["records"]
                                 if r.get("name") == "read_current_source" and r["type"] == "tool")
                    name, args = "read_review_history", prior["read"]["arguments"]
                phase = name
            else:
                assert receipts[-1].status == "success", receipts[-1].content
                assert "PRIVATE_" not in receipts[-1].content
                findings = [] if self.round_index == 2 else [{
                    "finding_id": f"static-{self.round_index}", "severity": "material",
                    "report_quote": f"Revision {self.round_index}.",
                    "diagnosis": "Synthetic expression correction to exercise the real responsibility router.",
                    "requested_change": "Advance the fixture revision label while retaining the actual source binding.",
                    "responsibility": "writer", "paper_ids": []}]
                name, args = "submit_report_review", {"review": {
                    "summary": "Deterministic review of the saved current report; no financial quality certification.",
                    "completion": "complete", "findings": findings, "unresolved_data_requests": []}}
        with (Path(os.environ["FIN_PROBE_EVIDENCE"]) / "convergence-turns.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps({"actor": self.actor, "round": self.round_index, "phase": phase,
                                 "provider_calls": 0}) + "\n")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="",
            tool_calls=[{"id": f"{self.actor}-{self.round_index}-{phase}", "name": name, "args": args}],
            additional_kwargs={"reasoning_content": "PRIVATE_CONVERGENCE"}))])


def graph(config):
    papers = json.loads((Path(os.environ["FIN_PROBE_EVIDENCE"]) / "convergence-papers.json").read_text())
    artifacts = CaseArtifacts(papers)

    def make_agent(role, current, *, feedback, paper_id, correction_round, revising_report):
        assert role in {"writer", "report_verifier"}
        citation = "P01:" + current.read_paper("P01")["claims"][0]["claim_id"]
        return build_case_output_agent(role="writer" if role == "writer" else "verifier",
            model=ConvergenceModel(actor=role, round_index=correction_round, citation=citation),
            tools=[], artifacts=current, limits={"model_calls": 4, "tool_calls": 6},
            report_revision=revising_report and role == "writer",
            require_responsibility=role == "report_verifier")

    return build_research_convergence_graph(
        artifacts=artifacts, question="Static persisted correction qualification",
        feedback={}, research_review_context={}, make_agent=make_agent, max_correction_rounds=3,
        execution_plan={"depth": "integrated", "rationale": "Synthetic integration qualification.",
                        "omitted_steps_reason": "Existing deterministic workpapers are the source fixture.",
                        "escalation_conditions": "Real responsibility routing remains active."},
    ).compile(interrupt_after=["writer"])
