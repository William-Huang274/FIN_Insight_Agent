"""Model-authored research responsibilities; native LangGraph owns routing."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class ResearchExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    depth: Literal["focused", "integrated", "extended"] = Field(description=
        "focused: one self-contained workpaper then independent final verification. "
        "integrated: research counter/source review, direct report writer, final verification. "
        "extended: integrated plus a distinct synthesis and its verification, only for justified cross-paper conflicts.")
    rationale: str = Field(min_length=20, max_length=2000, description="Explain the complete delivery route, evidence risk and necessary responsibilities in Chinese. This is not merely the size of the first wave. Ground current availability claims in tool observations; training knowledge is only a hypothesis.")
    omitted_steps_reason: str = Field(min_length=20, max_length=2000, description="Explain omitted delivery responsibilities (source/counter review, synthesis, writer, final verification), not just deferred research topics. Retain required evidence and independent final verification. Unchecked data availability cannot justify omission.")
    escalation_conditions: str = Field(min_length=20, max_length=2000, description="Observable evidence/conflicts/complexity that would require a changed route or targeted followup. Reassess after each wave and at handoff; do not predeclare unqueried information boundaries.")

    def public_summary(self):
        label = {"focused": "聚焦核实", "integrated": "综合研究", "extended": "深入综合"}[self.depth]
        return f"**执行方案：{label}**\n\n{self.rationale}\n\n**省略步骤及理由**\n\n{self.omitted_steps_reason}\n\n**升级条件**\n\n{self.escalation_conditions}"
