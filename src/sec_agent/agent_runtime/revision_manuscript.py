"""The active editing surface, distinct from source material and old research.

Derived from native successful reads/saves, never from model reasoning or a new
required plan. Whole-paper reads do not pin a whole paper. Focused field reads
survive unrelated tools until that field is saved or the revision stage ends.
"""
from copy import deepcopy

import jsonpointer
from langchain_core.messages import HumanMessage, ToolMessage
from .research_graph_contracts import canonical_sha256

ROOT = '/submission_to_repair/candidate'
PREFIX = 'runtime:context:' + ROOT


def manuscript_reads(messages, bodies, calls, before_index=None):
    active = {}
    for index, (message, body) in enumerate(zip(messages, bodies)):
        if (isinstance(message, HumanMessage)
                and message.additional_kwargs.get('fin_research_stage_boundary') == 'accepted_submission_to_revision'):
            active.clear()
        if not isinstance(message, ToolMessage) or message.status != 'success' or not isinstance(body, dict):
            continue
        result = body.get('result', body)
        if not isinstance(result, dict):
            continue
        call = (calls.get(message.tool_call_id) or (None, {}))[1]
        args = call.get('args') or {}
        if not isinstance(args, dict):
            continue
        if message.name == 'ReadResearchHistoryAction':
            locator = args.get('tool_call_id', '')
            if not locator.startswith(PREFIX + '/'):
                continue
            path = locator[len(PREFIX):]
            # Broad collections stay as an outline, not permanently expanded.
            # Historical task records never become current revision guidance.
            if path in {'/claims', '/task_note'} or path.startswith(('/task_note/coverage', '/task_note/issues', '/task_note/changes')):
                continue
            page = result.get('historical_record', {})
            receipt = page.get('receipt', {})
            if before_index is not None and index >= before_index:
                if 'result' in receipt:
                    active.pop(path, None)  # Full value is in the fresh native reply.
                continue
            if receipt.get('status') != 'success':
                continue
            if 'serialized_record_window' in page:
                try:
                    value = jsonpointer.resolve_pointer(body['current_context']['submission_to_repair']['candidate'], path)
                except (KeyError, jsonpointer.JsonPointerException):
                    continue
                digest = canonical_sha256(value)
                item = active.get(path, {})
                if item.get('value_fingerprint') != digest:
                    item = {'path': path, 'value_fingerprint': digest, 'read_windows': []}
                item['read_windows'] = [w for w in item['read_windows'] if w['page'].get('offset') != page.get('offset')]
                item['read_windows'].append({'read_call_id': message.tool_call_id, 'page': deepcopy(page)})
                active[path] = item
                continue  # Keep only the pages actually read, never the whole field.
            if 'result' not in receipt:
                continue
            value = receipt['result']
            active[path] = {'path': path, 'value': deepcopy(value), 'read_call_id': message.tool_call_id}
        elif message.name == 'SaveWorkpaperEditsAction' and result.get('saved') is True:
            paths = result.get('changed_paths', result.get('latest_changed_paths', []))
            for path in list(active):
                if any(path == p or path.startswith(p + '/') or p.startswith(path + '/') for p in paths):
                    del active[path]
    return list(active.values())


def editing_surface(candidate, fragment, reads, readback):
    """Expose exact current statements and bounded, explicitly read fields.

    A retained field must still equal its saved value. If it changed, the host's
    current fragment/latest saved values own it; never resurrect an old value.
    """
    hot = {c.get('claim_id'): i for i, c in enumerate(fragment.get('claims', []))}
    outline = []
    for index, claim in enumerate(candidate.get('claims', [])):
        row = {'claim_id': claim.get('claim_id'), 'read': readback(ROOT + f'/claims/{index}')}
        if claim.get('claim_id') in hot:
            row['current_value_at'] = '/current_context/submission_to_repair/current_fragment/claims/' + str(hot[claim['claim_id']])
        else:
            row['statement'] = claim.get('statement')
        outline.append(row)
    kept = []
    for item in reads:
        path = item['path']
        try:
            value = jsonpointer.resolve_pointer(candidate, path)
        except jsonpointer.JsonPointerException:
            continue
        if ('value' in item and value != item['value']) or (
                'value_fingerprint' in item and canonical_sha256(value) != item['value_fingerprint']):
            continue
        # The target claim is already complete in current_fragment.
        if isinstance(value, dict) and value.get('claim_id') in hot:
            continue
        kept.append({**deepcopy(item), 'read': readback(ROOT + path)})
    for index, item in enumerate(kept):
        value = item.get('value')
        if isinstance(value, dict) and value.get('claim_id'):
            for row in outline:
                if row['claim_id'] == value['claim_id']:
                    row.pop('statement', None)
                    row['current_value_at'] = f'/current_context/submission_to_repair/manuscript/open_fields/{index}/value'
    return {'claim_outline': outline, 'open_fields': kept,
            'basis': 'current_candidate_exact_values_not_new_tasks',
            'lifecycle': 'focused_reads_until_field_saved_or_revision_boundary; whole_record_remains_on_demand'}
