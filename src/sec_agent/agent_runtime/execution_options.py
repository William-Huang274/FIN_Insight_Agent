"""User research scope over native run configuration, never provider authority."""
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExecutionOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["standard", "auto", "selected", "single"] = "standard"
    model: Literal["default", "deepseek-v4-flash", "deepseek-v4-pro"] = "default"
    branch_ids: list[str] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def scope_shape(self):
        if len(set(self.branch_ids)) != len(self.branch_ids):
            raise ValueError("研究范围不能重复")
        if self.mode == "selected" and not self.branch_ids:
            raise ValueError("指定专家模式至少选择一个研究方向")
        if self.mode == "single" and len(self.branch_ids) != 1:
            raise ValueError("单 Agent 研究需要选择一个主研究方向")
        if self.mode in {"standard", "auto"} and self.branch_ids:
            raise ValueError("自动或完整研究不接受隐藏的方向限制")
        return self

    def validate_catalog(self, branches):
        if not set(self.branch_ids).issubset({b["branch_id"] for b in branches}):
            raise ValueError("研究方向不在当前服务提供的范围内")
        return self

    def apply_profile(self, profile):
        result = deepcopy(profile)
        if self.model != "default":
            for role, node in result["nodes"].items():
                node["profile"]["model"] = self.model
                # Keep each role's qualified reasoning/output/stop contract.
                node["budget"]["comparable_run_evidence"] += (
                    f" User-selected model {self.model} for {role}; existing role input/output and stop contract retained; "
                    "cross-model quality and cost require a separately recorded run, no assumed equivalence.")
        if self.mode == "single":
            result["max_parallel_tasks"] = 1
        return result


def execution_from_config(config):
    return ExecutionOptions.model_validate(config.get("configurable", {}).get("finsight_execution") or {})


def unreviewed_report_status():
    return {"summary": "本次按用户选择由单一 Agent 完成研究或修订；未运行独立的反证审查、底稿核验或报告复核。来源绑定和计算检查不代表金融语义通过，结果需要人工核对。",
            "findings": [], "unresolved_data_requests": [], "review_status": "not_run"}
