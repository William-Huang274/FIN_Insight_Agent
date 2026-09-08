"""Model-authored research responsibilities; native LangGraph owns routing."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class ResearchExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    depth: Literal["focused", "integrated", "extended"] = Field(description=
        "focused: one self-contained workpaper then independent final verification. "
        "integrated: research counter/source review, direct report writer, final verification. "
        "extended: integrated plus a distinct synthesis and its verification, only for justified cross-paper conflicts.")
    rationale: str = Field(min_length=20, max_length=2000, description="Explain scope, evidence risk and why these responsibilities are necessary, in user-facing Chinese.")
    omitted_steps_reason: str = Field(min_length=20, max_length=2000, description="Explain which steps add no distinct work and are omitted; do not omit required evidence or independent final verification for cost.")
    escalation_conditions: str = Field(min_length=20, max_length=2000, description="Evidence/complexity conditions requiring a deeper route; update the plan at handoff if they actually occur.")

    def public_summary(self):
        label = {"focused": "聚焦核实", "integrated": "综合研究", "extended": "深入综合"}[self.depth]
        return f"**执行方案：{label}**\n\n{self.rationale}\n\n**省略步骤及理由**\n\n{self.omitted_steps_reason}\n\n**升级条件**\n\n{self.escalation_conditions}"
