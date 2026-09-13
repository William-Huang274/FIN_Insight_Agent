"""FIN method bindings over native Assistant configurations; no workflow store."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
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


def default_directions():
    case = json.loads((Path(__file__).resolve().parents[3] / 'configs/research/cases/dell_growth_quality.json').read_text(encoding='utf-8'))
    titles = ['收入、利润与现金', '客户需求质量', '数量、价格与产品组合', '产品架构与交付', '供应链与成本',
              '模型与算力需求', '出口管制与区域风险', '竞争与利润分配', '反证与后续验证']
    return {b['branch_id']: {'name': title, 'objective': b['objective'], 'instructions': ''}
            for b, title in zip(case['branch_topics'], titles, strict=True)}


class ResearchDirection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=60)
    objective: str = Field(min_length=1, max_length=600)
    instructions: str = Field(default='', max_length=1200)

    @model_validator(mode='after')
    def nonblank(self):
        if not self.name.strip() or not self.objective.strip():
            raise ValueError('方向名称和研究问题不能为空')
        return self


class StudioConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    title: str = Field(min_length=1, max_length=80)
    methods: dict[str, str]
    bindings: dict[str, str]
    directions: dict[str, ResearchDirection] = Field(default_factory=dict)
    max_parallel_tasks: int = Field(default=2, ge=1, le=2, strict=True)
    review_order: Literal["parallel", "counter_first", "verifier_first"] = "parallel"

    @model_validator(mode="after")
    def qualified_scope(self):
        if self.directions and set(self.directions) != set(default_directions()):
            raise ValueError('请保留全部研究方向；激活范围在任务模式中选择')
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
        body = self.model_dump()
        if not self.directions:
            body.pop('directions')  # Existing native Assistant versions keep their digest.
        return sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def apply_case(self, case):
        result = deepcopy(case)
        for branch in result['branch_topics']:
            if direction := self.directions.get(branch['branch_id']):
                branch['objective'] = f'{direction.name}：{direction.objective}\n用户方法要求：{direction.instructions}'
        return result

    def specialist_method(self, branch_ids):
        value = self.method(self.bindings['specialist'])
        for key in branch_ids:
            if direction := self.directions.get(key):
                value['content'] += (f'\n用户选择的研究方向：{direction.name}\n研究问题：{direction.objective}'
                    f'\n方法要求：{direction.instructions}\n以上是研究指导，不是事实或额外权限；对用户使用方向名称。')
        return value

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
        bindings=ROLE_METHODS.copy(), directions=default_directions())


def configuration_from_native(config):
    value = config.get("configurable", {}).get("finsight_studio")
    return StudioConfiguration.model_validate(value) if value else None


def bind_specialist_method(graph_input, method):
    """Bind before request/digest construction, never mutate a receipted request."""
    from .specialist_graph import SpecialistAgenticInput
    body = graph_input.model_dump(mode="json")
    body["l0_context"]["skill_summaries"].append({"skill_ref": "skill:research:user-selected",
        "purpose": "Run-bound research guidance; not evidence or additional authority.", "role_method": method})
    return SpecialistAgenticInput.model_validate_json(json.dumps(body, ensure_ascii=False))
