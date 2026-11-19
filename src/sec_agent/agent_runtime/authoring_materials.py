"""Lossless authoring views over archived workpapers, without semantic rewriting."""
from contextlib import nullcontext
from markdown_it import MarkdownIt


def workpaper_locator(ref, field):
    """Keep the catalog navigable without importing the reviewer's handoff prose."""
    return {**{k: ref[k] for k in ('topic_id', 'revision', 'digest', 'title', 'use') if k in ref},
            'readback': {'tool': 'read_research_workpaper', 'arguments': {
                'topic_id': ref['topic_id'], 'revision': ref['revision'], 'field': field}}}


def material_view(value, *, compact_dependencies=True):
    # Remove only known execution-history fields. Unknown fields stay visible.
    view = {k: v for k, v in value.items() if k not in {'original_task', 'change', 'next_decision'}}
    if compact_dependencies and 'dependencies' in view:
        view['dependencies'] = [{k: v for k, v in ref.items() if k != 'rationale'}
                                for ref in view['dependencies']]
    view['metadata_readback'] = {'tool': 'read_research_workpaper', 'arguments': {
        'topic_id': value['topic_id'], 'revision': value['revision'], 'field': 'metadata'}}
    view['presentation'] = 'authoring_material_v1'
    return view


def chapter_argument(workspace, snapshot_id, snapshot, topic_id, *, _db=None):
    """Show the frozen finding and the chapter's actual adoption terms; reads remain explicit."""
    ref = snapshot['selected'][topic_id]
    with (workspace.connection() if _db is None else nullcontext(_db)) as db:
        paper = workspace._get(db, topic_id, ref['revision'])
        state = workspace.authoring._state(db, snapshot['understanding_revision'])
        ids = [key for s in snapshot['section_ids'] for key in state['sections'][s]['judgment_ids']]
        terms = []
        for key in sorted(workspace.authoring._closure(state, ids)):
            for parent in state['judgments'][key]['workpapers']:
                if parent['topic_id'] == topic_id:
                    edges = [parent]
                else:
                    source = workspace._get(db, parent['topic_id'], parent['revision'])
                    edges = source['dependencies']
                for edge in edges:
                    if edge['topic_id'] == topic_id and all(edge[k] == ref[k] for k in ('revision', 'digest')):
                        term = {k: edge[k] for k in ('use', 'rationale')}
                        term['via_topic'] = parent['topic_id']
                        if term not in terms:
                            terms.append(term)
        result = {k:paper[k] for k in ('topic_id','revision','digest','as_of','finding','conditions',
                                        'counterevidence','remaining','evidence_receipt_ids')}
        from .assessment_evidence import current_counterexamples
        observations = current_counterexamples(workspace,db,[(topic_id,ref['revision'],ref['digest'])],descend=False)
        if observations:
            result['reviewed_counterexamples'] = observations
        result.update(chapter_adoption=terms, argument_sections=[
            {k: h[k] for k in ('title','offset','characters')} for h in argument_outline(paper)['argument_sections']],
            window_readback={'tool':'read_synthesis_material','arguments':{
                'snapshot_id':snapshot_id,'topic_id':topic_id,'view':'window'}},
            history_readback={'tool':'read_synthesis_material','arguments':{
                'snapshot_id':snapshot_id,'topic_id':topic_id,'view':'history'}},
            source_tool='read_workpaper_evidence',
            read_scope='Frozen workpaper finding with adoption terms where recorded. For a body passage use its offset and characters (up to 24000 per read); for a source use its receipt ID. Body not read by this view.')
        return result


def argument_outline(paper, *, compact_dependencies=True):
    """Markdown parser supplies heading positions; no heading is classified or suppressed."""
    body = paper['body']
    lines = body.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    headings = []
    tokens = MarkdownIt().parse(body)
    for i, token in enumerate(tokens):
        if token.type == 'heading_open' and token.map:
            headings.append({'title': tokens[i + 1].content, 'level': int(token.tag[1:]),
                             'offset': offsets[token.map[0]]})
    if not headings or headings[0]['offset']:
        headings.insert(0, {'title': 'Opening argument', 'level': 0, 'offset': 0})
    for i, heading in enumerate(headings):
        end = headings[i + 1]['offset'] if i + 1 < len(headings) else len(body)
        heading['characters'] = end - heading['offset']
        heading['window'] = {'offset': heading['offset'],
                             'max_characters': max(1, min(24000, heading['characters']))}
    return {**material_view({k: v for k, v in paper.items() if k != 'body'},
                            compact_dependencies=compact_dependencies),
            'argument_sections': headings, 'total_characters': len(body),
            'body_readback': {'tool': 'read_research_workpaper', 'arguments': {
                'topic_id': paper['topic_id'], 'revision': paper['revision'], 'field': 'body'}},
            'read_scope': 'Structure only, not evidence read or semantic acceptance. Select relevant '
                          'arguments and counterevidence. Combine body_readback arguments with the '
                          'selected window. Follow next_offset for long sections. History remains readable.'}
