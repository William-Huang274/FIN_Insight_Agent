"""Fixed organization originals behind the maintained specialist MCP boundary.

No archived baseline, host SQL, uploads or public library is opened. This does
not enable native organization runs or claim reviewed/numeric-fact authority.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from copy import deepcopy

from sec_agent.research_foundation.contracts import bind_research_method, canonical_sha256
from sec_agent.research_foundation.organization_source_navigation import (
    OrganizationSourceNavigation, build_organization_source_server,
)
from .organization_memory_scope import organization_memory_scope
from .research_mcp_tools import MCPToolLaneAdapter, compose_mcp_graph_run
from .research_graph import ResearchGraphDependencies


POLICY = 'organization_fixed_inputs_only'


class _MethodBinding:
    def __init__(self, foundation, graph_run, reader):
        self.foundation, self.graph_run, self.reader = foundation, graph_run, reader

    def __call__(self, *, branch_ids, research_as_of, data_snapshot_id, execution_attempt_id, source_policy):
        self.reader.check()
        bound = self.graph_run.foundation_binding
        if (tuple(branch_ids) != bound.required_branch_ids
                or research_as_of != datetime.fromisoformat(bound.research_as_of.replace('Z', '+00:00'))
                or data_snapshot_id != bound.snapshot_id
                or execution_attempt_id != self.graph_run.mcp_run_binding.execution_attempt_id
                or source_policy != POLICY):
            raise ValueError('organization_method_scope_mismatch')
        return bind_research_method(self.foundation, branch_ids, research_as_of=research_as_of,
            data_snapshot_id=data_snapshot_id, execution_attempt_id=execution_attempt_id, source_policy=POLICY)

    def validate_scope(self, branch_id, scope):
        if not isinstance(scope, dict) or branch_id not in scope.get('selected_branch_ids', ()):
            raise ValueError('organization_branch_scope_required')
        expected = self(branch_ids=scope['selected_branch_ids'],
            research_as_of=datetime.fromisoformat(scope['research_as_of'].replace('Z', '+00:00')),
            data_snapshot_id=scope['data_snapshot_id'], execution_attempt_id=scope['execution_attempt_id'],
            source_policy=scope['source_policy']).run_scope.model_dump(mode='json')
        if scope != expected:
            raise ValueError('organization_method_scope_mismatch')


@dataclass(frozen=True)
class OrganizationDataComposition:
    dependencies: ResearchGraphDependencies
    foundation_binding: object
    source_route_catalog: dict
    decision_digest: str
    inventory_snapshot_digest: str
    source_route_catalog_digest: str
    mcp_server: object
    method_reader: object
    restore_source_observations: object
    reviewed_topic_refs_by_branch: dict
    access_check: object
    case_artifacts: object = None
    source_spaces: tuple = ('organization',)
    baseline_source_plan: None = None


def _unavailable(*args, **kwargs):
    raise ValueError('organization_capability_not_authorized')


class OrganizationDataFactory:
    """Host injects a method-only foundation and an explicit timezone-aware cutoff."""
    def __init__(self, reader, *, foundation, research_as_of, workbench_url, retrieval_root=None):
        grant, manifest, _ = reader._grant()
        cutoff = datetime.fromisoformat(research_as_of.replace('Z', '+00:00'))
        if (foundation.case_identity.case_id != 'research:' + grant['execution_id']
                or foundation.status != 'active_research_foundation'
                or cutoff.tzinfo is None or cutoff.utcoffset() is None
                or cutoff.date().isoformat() != manifest['research_as_of']):
            raise ValueError('organization_foundation_identity_or_cutoff_mismatch')
        self.reader, self.foundation, self.research_as_of = reader, foundation, research_as_of
        self.workbench_url = workbench_url
        self.retrieval_root = retrieval_root
        self.grant = grant

    @contextmanager
    def __call__(self, *, run_invocation_id, environment=None, source_read_enabled=False,
                 live_web_read_enabled=False, role_method_reader=None, restored_observations=(), case_artifacts=None):
        if not source_read_enabled or live_web_read_enabled:
            raise ValueError('organization_requires_source_read_without_live_web')
        self.reader._after(self.grant)
        graph_run = compose_mcp_graph_run(self.foundation,
            branch_ids=[row.branch_id for row in self.foundation.question_branches],
            research_as_of=self.research_as_of, snapshot_id=self.reader.authority.manifest_digest,
            execution_attempt_id=run_invocation_id, source_policy=POLICY)
        inventory = self.reader.authority.manifest_digest[7:]
        catalog = {'schema_version':'organization_source_routes.v1', 'source_spaces':['organization'],
                   'manifest_digest':self.reader.authority.manifest_digest, 'routes':[]}
        catalog['catalog_digest'] = canonical_sha256(catalog)
        navigation = OrganizationSourceNavigation(self.reader, workbench_url=self.workbench_url,
            retrieval_root=self.retrieval_root)
        artifact_sources = {}
        if case_artifacts is not None:
            from .case_artifacts import CaseArtifacts
            if not isinstance(case_artifacts, CaseArtifacts):
                raise ValueError('organization_case_artifacts_required')
            case_artifacts = deepcopy(case_artifacts)
            expected = {key:getattr(graph_run.foundation_binding, key) for key in (
                'case_id','snapshot_id','research_as_of','foundation_digest')}
            expected.update(owner_data_gate_decision_digest=canonical_sha256(self.grant),
                source_route_catalog_digest=catalog['catalog_digest'], inventory_snapshot_digest=inventory)
            if any(getattr(case_artifacts, key, None) != value for key, value in expected.items()):
                raise ValueError('organization_case_artifacts_scope_mismatch')
            artifact_sources = case_artifacts.source_snapshot()
        validated = navigation.restore([*restored_observations,
            {'status':'success', 'content':list(artifact_sources.values())}])
        if case_artifacts is not None:
            # Only regenerated originals/calculations enter review tools. Keep
            # paper aliases; retain untouched author checkpoints separately.
            sources = {}
            for alias, item in artifact_sources.items():
                canonical = item.get('passage_id') or item.get('calculation_id')
                if canonical not in validated:
                    raise ValueError('organization_case_source_not_validated')
                sources[alias] = validated[canonical]
            case_artifacts = case_artifacts.with_source_snapshot(sources)
        server = build_organization_source_server(navigation,
            binding_reader=_MethodBinding(self.foundation, graph_run, self.reader), role_method_reader=role_method_reader,
            case_artifacts=case_artifacts)
        with organization_memory_scope(self.reader), MCPToolLaneAdapter(server,
                run_binding=graph_run.mcp_run_binding, source_read_enabled=True,
                organization_sources_only=True) as adapter:
            def guarded(port):
                def invoke(value):
                    self.reader._after(self.grant)
                    result = port(value)
                    self.reader._after(self.grant)
                    return result
                return invoke
            dependencies = ResearchGraphDependencies(foundation_binder=graph_run.foundation_binder,
                planner_tool_capabilities={'source_spaces':['organization'], 'financial_fact_query':False},
                planner_source_route_catalog=catalog, planner_agent=_unavailable,
                evidence_tool=guarded(adapter.evidence_tool), finance_tool=guarded(adapter.finance_tool),
                specialist_agent=_unavailable, counter_agent=_unavailable, lead_agent=_unavailable)
            yield OrganizationDataComposition(dependencies=dependencies, foundation_binding=graph_run.foundation_binding,
                source_route_catalog=catalog, decision_digest=canonical_sha256(self.grant),
                inventory_snapshot_digest=inventory, source_route_catalog_digest=catalog['catalog_digest'],
                mcp_server=server, method_reader=adapter.read_research_method,
                restore_source_observations=navigation.restore, reviewed_topic_refs_by_branch={},
                access_check=lambda: self.reader._after(self.grant), case_artifacts=case_artifacts)
