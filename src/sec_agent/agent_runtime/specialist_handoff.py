"""Task-scoped expert handoffs using the same source/analysis views as the Lead.

Original papers and observations stay in the host archive. Only requested source
observations enter the receiving notebook; author prose never grants authority.
"""
from copy import deepcopy

from .case_artifacts import CaseArtifacts
from .report_authoring import author_analysis, author_overview, historical_assignment, research_handoff


def dependency_navigation(task_id, paper):
    """Literal navigation, without selecting facts or summarizing the author."""
    read = {"tool": "ReadDependencyWorkAction", "arguments": {"task_id": task_id, "section": "sources"}}
    items = [item for obs in paper['notebook']['observations'] for item in obs['content']
             if item.get('result_state') in {'numeric_fact', 'reviewed_evidence', 'source_bound_passage', 'non_authoritative_metric'}]
    return {
        'task_id': task_id, 'agent_id': paper['agent_id'], 'branch_id': paper['task']['branch_id'],
        'revision': paper['task']['revision'],
        'topic': paper.get('task_context', {}).get('assignment', {}).get('topic_title') or paper['task']['branch_id'],
        'source_count': len({item.get('passage_id') or item.get('evidence_id') or item.get('numeric_fact_id')
                             or item.get('calculation_id') or item.get('fact_id') for item in items}),
        'coverage': {key: sorted({str(item[key]) for item in items if item.get(key) is not None})
                     for key in ('company', 'ticker', 'period_start', 'period_end')},
        'read': read,
        'author_analysis': {'tool': 'ReadDependencyWorkAction', 'arguments': {'task_id': task_id, 'section': 'overview'}},
    }


def saved_material_navigation(task_id, paper):
    """A fresh formation session receives sources, never an earlier author state."""
    value = dependency_navigation(task_id, paper)
    value.pop('author_analysis')
    value['available_sections'] = ['sources', 'handoff']
    value['read_materials'] = {'tool': 'ReadDependencyWorkAction',
        'arguments': {'task_id': task_id, 'section': 'handoff'}}
    value['notice'] = 'Saved originals and calculations from this assignment. Read them to form a new answer; no previous conclusion or operational guidance is supplied.'
    return value


def bind_saved_materials(graph_input, paper):
    """Validate the archived task/data boundary before exposing a source-only reader."""
    from .specialist_graph import SpecialistAgenticInput
    from .workpaper_review_graph import validate_workpaper_state
    import json
    old = validate_workpaper_state(paper)
    current = graph_input.model_dump(mode='json')
    for key in ('case_id', 'snapshot_id', 'research_as_of', 'foundation_digest', 'task_id', 'branch_id'):
        if old['task'][key] != current['task'][key]:
            raise ValueError('saved_material_task_scope_mismatch:' + key)
    for key in ('owner_data_gate_decision_digest', 'source_route_catalog_digest', 'inventory_snapshot_digest'):
        if old['notebook'][key] != current['l0_context'][key]:
            raise ValueError('saved_material_data_scope_mismatch:' + key)
    current['task_context']['saved_source_materials'] = saved_material_navigation(old['task']['task_id'], old)
    return SpecialistAgenticInput.model_validate_json(json.dumps(current))


class DependencyReader:
    def __init__(self, papers, *, source_only_tasks=()):
        self.papers = deepcopy(papers)
        self.source_only_tasks = frozenset(source_only_tasks)
        if not self.source_only_tasks.issubset(papers):
            raise ValueError('unknown_source_only_task')
        self.artifacts = CaseArtifacts(list(self.papers.values()))
        self.ids = {task_id: f'P{i:02d}' for i, task_id in enumerate(self.papers, 1)}

    def __call__(self, request):
        task_id = request['task_id']
        if task_id not in self.ids:
            raise ValueError('unknown_dependency_task_id_use_task_context_catalog')
        paper_id = self.ids[task_id]
        section = request.get('section', 'sources')
        if task_id in self.source_only_tasks and section not in {'sources', 'handoff'}:
            raise ValueError('saved_materials_are_source_only_use_sources_or_handoff')
        refs = []
        if section == 'sources':
            sources = self.artifacts.read_paper(paper_id, 'sources')
            offset, limit = request.get('offset', 0), request.get('limit', 4)
            page = list(sources)[offset:offset + limit]
            payload = {'source_count': len(sources), 'sources': [
                {**sources[key], 'read': {'tool': 'ReadDependencyWorkAction', 'arguments': {
                    'task_id': task_id, 'section': 'handoff', 'source_ids': [key]},
                    'notice': 'Read this saved original directly; document/node IDs are provenance, not a substitute reader request.'}}
                for key in page],
                       'read_page': {'tool': 'ReadDependencyWorkAction', 'arguments': {
                           'task_id': task_id, 'section': 'handoff', 'source_ids': page, 'limit': limit}},
                       'next_read': {'tool': 'ReadDependencyWorkAction', 'arguments': {
                           'task_id': task_id, 'section': 'sources', 'offset': offset + len(page), 'limit': limit}}
                       if offset + len(page) < len(sources) else None}
        elif section == 'handoff':
            if task_id in self.source_only_tasks:
                sources = self.artifacts.read_paper(paper_id, 'sources')
                requested = request.get('source_ids')
                if requested is not None and set(requested) - set(sources):
                    raise ValueError('unknown_saved_source_id_use_sources_catalog')
                keys = [key for key in sources if requested is None or key in requested]
                offset, limit = request.get('offset', 0), request.get('limit', 4)
                page = keys[offset:offset + limit]
                next_offset = offset + len(page) if offset + len(page) < len(keys) else None
                payload = {'source_materials': [{'source_id': key, 'source': sources[key]} for key in page],
                    'source_count': len(sources), 'next_read': {'tool': 'ReadDependencyWorkAction',
                    'arguments': {'task_id': task_id, 'section': 'handoff', 'offset': next_offset, 'limit': limit,
                        **({'source_ids': requested} if requested is not None else {})}} if next_offset is not None else None}
            else:
                payload = research_handoff(self.artifacts, paper_id, source_ids=request.get('source_ids'),
                                          offset=request.get('offset', 0), limit=request.get('limit', 4), include_uncited=True)
            refs = [row['source_id'] for row in payload['source_materials']]
        elif section == 'overview':
            payload = author_overview(self.artifacts, paper_id)
        elif section == 'analysis':
            payload = author_analysis(self.artifacts, paper_id, fields=request.get('analysis_fields'),
                                      claim_ids=request.get('claim_ids'))
        elif section == 'assignment':
            payload = historical_assignment(self.artifacts, paper_id)
        else:
            raise ValueError('unknown_dependency_section')
        # Rewrite navigation, not source IDs. No broken Lead-only tool pointers.
        def navigation(value):
            if isinstance(value, list):
                return [navigation(v) for v in value]
            if not isinstance(value, dict):
                return value
            if value.get('tool') == 'read_current_source':
                ref = value['arguments']['source_id']
                return {'tool': 'ReadDependencyWorkAction', 'arguments': {
                    'task_id': task_id, 'section': 'handoff', 'source_ids': [ref]},
                    'notice': 'Returns the complete saved source observation, including its original reader locator.'}
            if value.get('tool') == 'read_current_workpaper':
                args = {k: v for k, v in value['arguments'].items() if k != 'paper_id'}
                if args.get('section') in {'citations', 'claims'}:
                    args['section'] = 'analysis'
                    args['analysis_fields'] = ['claims']
                elif args.get('section') == 'workpaper':
                    args['section'] = 'analysis'
                return {'tool': 'ReadDependencyWorkAction', 'arguments': {'task_id': task_id, **args}}
            return {k: navigation(v) for k, v in value.items()}
        payload = navigation(payload)
        if section == 'handoff':
            # The exact originals below carry the text once, with canonical IDs.
            # Do not repeat quote windows or the entire source directory each read.
            payload.pop('source_catalog', None)
            for row in payload['source_materials']:
                for key in ('reading_context', 'quotes'):
                    row.pop(key, None)
        observations = []
        for ref in refs:
            item = self.artifacts.source_item(ref)
            identity = item.get('passage_id') or item.get('evidence_id') or item.get('numeric_fact_id') or item.get('calculation_id') or item.get('fact_id')
            for obs in self.papers[task_id]['notebook']['observations']:
                if obs['status'] == 'success' and any(r['ref_id'] == identity for r in obs['references']):
                    if obs not in observations:
                        observations.append(deepcopy(obs))
        payload.update(task_id=task_id, notice=(
            'Source views include previously read but uncited materials. Analysis is the prior author’s interpretation, '
            'not this task’s instruction. Restored observations preserve canonical citation IDs, periods, units and receipts; '
            'no new authority or route completion is inferred.'))
        # The caller restores unchanged receipted observations, as for delegated work.
        return payload, observations
