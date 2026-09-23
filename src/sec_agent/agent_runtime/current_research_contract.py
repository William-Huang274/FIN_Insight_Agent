"""Current task identity, independent of immutable historical dataset contracts.

The archived foundation still validates captured data. It is not the active
question, method package or company scope. Never rewrite evidence or its IDs.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sec_agent.research_foundation.contracts import ResearchGraphFoundation

CONTRACT_VERSION = 'research_session.v2'
CONTRACT_ENV = 'FINSIGHT_RESEARCH_CONTRACT_VERSION'
SOURCE_CAPABILITY = 'capability:research:source-document-read'


def current_foundation(archived, *, thread_id, profile, research_as_of):
    """Derive a separately hashed method contract, not an edited data manifest."""
    identity = 'research:' + str(UUID(thread_id))
    body = archived.model_dump(mode='json')
    body.update(schema_version='fin_ia_research_foundation_v2_0',
        status='active_research_foundation', purpose='Source-bound research for the current user task.')
    body['case_identity'] = {
        'case_id': identity, 'subject_ticker': 'task-defined',
        'subject_legal_name': 'Subjects selected by the current research question',
        'top_level_question_zh': '以本次用户问题和明确委派为研究范围，按实际目录确认资料覆盖。',
        'current_snapshot_state': 'Inspect the bound data versions and individual source dates.',
        'current_complete_financial_period': 'Determine separately for each issuer and metric.',
        'public_demo_requires_latest_refresh': True,
    }
    body['scope_ceiling'].update(one_subject_company_only=False,
        context_entities=['task-defined'],
        context_entity_rule='The user question determines subjects; no reference issuer or fixed peer allowlist.',
        company_financial_window='Select comparable periods needed by the question.',
        industry_and_model_window='Check source freshness against the host research cutoff.',
        regulatory_window='Check effective dates and jurisdiction against the question.',
        non_goals=['unauthorized_data_access', 'automatic_publication'])
    # These describe interfaces, not an issuer-specific discovery route catalog.
    body['source_families'] = [{
        'source_family_id': 'F_RESEARCH_SOURCES', 'classes': ['A', 'B', 'C', 'D'],
        'purpose': 'Task-authorized financial observations and original documents.',
        'entrypoints': [], 'storage_route': 'runtime_disclosed_tools',
        'authority': 'Authority, units, dates and revision are retained per source.',
        'boundary': 'Inspect tool catalogs for available entities; candidates and graph clues require verification.',
    }]
    body['question_branches'] = [{
        'branch_id': row['branch_id'], 'priority': 'high', 'objective': row['objective'],
        'required_source_families': ['F_RESEARCH_SOURCES'], 'formula_ids': [],
        'counter_questions': ['哪些证据或替代解释会改变本专题判断？'],
    } for row in profile['branch_topics']]
    body['formulas'] = []  # Actual supported formulas come from the numeric tool catalog.
    body['freshness_contract'] = {'schema_version': 'research_freshness.v2',
        'research_as_of': research_as_of,
        'rules': ['Check dates individually; the newest document is not proof the entire library is current.',
                  'Compare newer issuer, counterparty and regulatory sources when material.',
                  'Unknown dates and failed retrieval are execution or availability gaps, not non-disclosure.']}
    body['acceptance_and_stop'].update(
        must_have=['Material question scope accounted for', 'Claims linked to observed sources',
                   'Subject, period, unit, status and uncertainty preserved'],
        stop_and_leave_null=['Required inputs unavailable', 'Period, unit or identity unresolved',
                            'Source acquisition or parsing failed; diagnose before asserting non-disclosure'])
    return ResearchGraphFoundation.model_validate_json(json.dumps(body))


def bind_current_foundation(archived, environment, root):
    version = environment.get(CONTRACT_ENV)
    if not version:
        return archived  # Explicit archive/qualification path, not new product tasks.
    if version != CONTRACT_VERSION:
        raise ValueError('unknown_research_contract_version')
    if not environment.get('FINSIGHT_RESEARCH_AS_OF'):
        raise ValueError('current_research_requires_host_cutoff')
    profile = json.loads((Path(root) / 'configs/research/cases/growth_quality.json').read_text(encoding='utf-8'))
    from .agent_server_data_composition import task_research_as_of
    return current_foundation(archived, thread_id=environment['FINSIGHT_TASK_THREAD_ID'], profile=profile,
                              research_as_of=task_research_as_of(environment))


def canonical_capability(value):
    """Only named, retired capability IDs are input aliases; no free-text rewrite."""
    return {
        'capability:dell:source-document-read': SOURCE_CAPABILITY,
        'capability:dell:financial-fact-query': 'capability:research:financial-fact-query',
        'capability:dell:reviewed-evidence-query': 'capability:research:reviewed-evidence-query',
    }.get(value, value)
