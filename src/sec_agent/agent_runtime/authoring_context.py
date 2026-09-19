"""Version-bound author preparation and scoped method disclosure, no summarizer."""
from copy import deepcopy
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .research_graph_contracts import canonical_sha256
from sec_agent.research_foundation.research_methods import get_research_method


class AuthoringBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, description="Current substantive answer in assigned scope, not a publication draft.")
    argument_plan: list[str] = Field(min_length=1, description="Argument sequence and how the evidence supports it.")
    decisions: list[str] = Field(description="Public reasons for accepting, qualifying or rejecting interpretations; not private reasoning.")
    material_conditions: list[str] = Field(description="Conditions/counterevidence that must survive writing; preserve quantitative meaning.")
    unresolved: list[str] = Field(description="Actual open work or limitations, not invented boilerplate.")
    ready: bool = Field(description="Ready for the assigned bounded deliverable, not omniscient research. False only when unresolved work prevents a core promised conclusion from being responsibly stated. Ordinary coverage limits, unmeasured outcomes outside scope, or unavailable precision may accompany an otherwise useful bounded answer; do not hide material blockers.")


class PrepareWorkpaperAction(BaseModel):
    """Organize current domain judgment before drafting. Alone in a tool batch."""
    model_config = ConfigDict(extra="forbid")
    action: Literal["prepare_workpaper"]
    context_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason_summary: str = Field(min_length=1, max_length=1000)
    brief: AuthoringBrief


CORE_SEMANTICS = (
    "Preserve subject, period, unit, denominator, source/calculation identity and version. "
    "Distinguish observation, calculation, assumption and inference; do not revive rejected interpretations. "
    "Keep decisive conditions attached to reusable claims, not only in footnotes. "
    "Prose, tables, structured findings and remaining issues must agree. New substantive judgments require "
    "the relevant method and original evidence, not stylistic completion. Tool failure is not non-disclosure."
)


def method_sections(method_id, headings, reader=get_research_method):
    """Select exact H2 sections; saved/custom methods without them stay intact."""
    method = deepcopy(reader(method_id))
    if 'method' in method and 'mcp_receipt' in method:
        # Native MCP returns a receipted envelope; packaged/custom readers return
        # the resource directly. Preserve provenance and label deterministic parsing.
        method = {**method['method'], 'mcp_receipt': method['mcp_receipt'],
                  'runtime_compatibility_parse': 'receipted_method_envelope.v1'}
    original = method['content']
    parts = re.split(r'(?m)(?=^## )', original)
    available = {p.splitlines()[0][3:]: p for p in parts if p.startswith('## ')}
    if not headings or not set(headings) <= available.keys():
        content, selection = original, 'full_resource'
    else:
        content = parts[0] + ''.join(available[h] for h in headings)
        selection = list(headings)
    return {**method, 'content': content, 'selection': selection,
            'resource_digest': canonical_sha256(original), 'content_digest': canonical_sha256(content)}


def stage_methods(stage, *, domain='finance', reader=get_research_method):
    if stage not in {'prepare_report', 'report', 'prepare_workpaper', 'workpaper'}:
        raise ValueError('unknown_authoring_stage')
    workpaper = stage.endswith('workpaper')
    if stage.startswith('prepare'):
        methods = [method_sections(domain, (), reader)]
        if domain != 'survey_analysis':
            methods.append(method_sections('lead', ('专家Lead的适用范围与交付责任',) if workpaper else ('执行顺序与交付',), reader))
    else:
        methods = []
    headings = ('先确定交付对象：报告或专题底稿',) if workpaper else (
        '成文风格与研究价值', '边界项与未决项如何落笔', '执行顺序与交付')
    methods.append(method_sections('writer', headings, reader))
    # D5 never receives the report/financial synthesis instructions.
    if domain == 'survey_analysis' and not stage.startswith('prepare'):
        methods.append(method_sections(domain, (), reader))
    return {'stage': stage, 'domain': domain, 'methods': methods,
            'core_semantics': CORE_SEMANTICS,
            'readback': {'tool': 'get_research_method', 'arguments': {'method_id': domain}},
            'selection_origin': 'runtime_stage_policy', 'financial_acceptance': False}


def bind_authoring(brief, *, owner, stage, basis):
    brief = AuthoringBrief.model_validate(brief).model_dump(mode='json')
    return {'version': 'authoring_context.v1', 'owner': owner, 'stage': stage,
            'brief': brief, 'basis': deepcopy(basis), 'basis_digest': canonical_sha256(basis),
            'financial_acceptance': False}


def validate_authoring(packet, *, owner, basis):
    if (packet.get('owner') != owner or packet.get('basis_digest') != canonical_sha256(basis)
            or packet.get('basis') != basis or not packet.get('brief', {}).get('ready')):
        raise ValueError('authoring_owner_or_basis_changed_prepare_again')


def specialist_basis(state):
    return {'task': deepcopy(state['task']),
        'observations_digest': canonical_sha256(state['notebook'].get('observations', [])),
        'working_state': deepcopy(state.get('research_working_state')),
        'revision_feedback': deepcopy((state.get('task_context') or {}).get('revision_feedback', [])),
        'source_checks': deepcopy(state.get('required_source_checks', []))}
