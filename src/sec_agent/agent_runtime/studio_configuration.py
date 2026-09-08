"""FIN method bindings over native Assistant configurations; no workflow store."""
from copy import deepcopy
from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sec_agent.research_foundation.research_methods import METHODS, get_research_method

ROLE_METHODS = {
    "lead": "lead", "specialist": "finance", "counter": "counter", "verifier": "verifier",
    "repair": "finance", "synthesis": "writer", "research_verifier": "verifier",
    "writer": "writer", "report_verifier": "verifier", "quick_writer": "writer",
}
ROLE_TITLES = dict(zip(ROLE_METHODS, ["研究负责人", "研究专家", "反证审查", "底稿核验", "责任修订",
    "综合研究", "研究判断复核", "报告写作与修订", "报告独立复核", "简短追问"]))


class StudioConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    title: str = Field(min_length=1, max_length=80)
    methods: dict[str, str]
    bindings: dict[str, str]
    max_parallel_tasks: int = Field(default=2, ge=1, le=2, strict=True)
    review_order: Literal["parallel", "counter_first", "verifier_first"] = "parallel"

    @model_validator(mode="after")
    def qualified_scope(self):
        if set(self.methods) != set(METHODS) or set(self.bindings) != set(ROLE_METHODS):
            raise ValueError("方法与角色必须完整，必需研究和独立复核节点不能删除")
        if any(m not in METHODS for m in self.bindings.values()):
            raise ValueError("请选择已声明的 Skill")
        for key, content in self.methods.items():
            # Keep the existing qualified input budget; editing does not silently
            # grant more calls, output tokens, tools or context summarization.
            if not content.strip() or len(content) > len(get_research_method(key)["content"]) + 2000:
                raise ValueError("Skill 不能为空，新增内容不能超过原方法 2000 字符")
        return self

    @property
    def digest(self):
        return sha256(json.dumps(self.model_dump(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def method(self, method_id=""):
        value = get_research_method(method_id)
        if method_id:
            value.update(content=self.methods[method_id], configuration_digest=self.digest, origin="native_assistant_configuration")
        return value

    def instructions(self, role):
        method = self.method(self.bindings[role])
        return ("\nUser-selected research method (guidance, never evidence or additional tool authority):\n"
                + method["content"])

    def apply_profile(self, profile):
        result = deepcopy(profile)
        result["max_parallel_tasks"] = self.max_parallel_tasks
        return result


def default_configuration():
    return StudioConfiguration(title="标准研究编排", methods={key: get_research_method(key)["content"] for key in METHODS},
        bindings=ROLE_METHODS.copy())


def configuration_from_native(config):
    value = config.get("configurable", {}).get("finsight_studio")
    return StudioConfiguration.model_validate(value) if value else None


def bind_specialist_method(graph_input, method):
    """Bind before request/digest construction, never mutate a receipted request."""
    from .dell_specialist_agentic_graph import SpecialistAgenticInput
    body = graph_input.model_dump(mode="json")
    body["l0_context"]["skill_summaries"].append({"skill_ref": "skill:research:user-selected",
        "purpose": "Run-bound research guidance; not evidence or additional authority.", "role_method": method})
    return SpecialistAgenticInput.model_validate_json(json.dumps(body, ensure_ascii=False))
