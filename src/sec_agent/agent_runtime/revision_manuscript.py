"""The active editing surface, distinct from source material and old research.

Derived from native successful reads/saves, never from model reasoning or a new
required plan. Whole-paper reads do not pin a whole paper. Focused field reads
survive unrelated tools. Successful saves replace their values in the editing
surface; they do not close the document while this revision is still active.
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
            # A whole claim collection stays an outline. Explicitly read task
            # records are manuscript content, not renewed task requirements.
            if path == '/claims':
                continue
            page = result.get('historical_record', {})
            receipt = page.get('receipt', {})
            if (path == '/task_note' and receipt.get('status') == 'success'
                    and receipt.get('content_projection') == 'manuscript_and_current_revision_responses'
                    and isinstance(receipt.get('result'), dict)):
                # The default document view may have returned only summary
                # and current responses. Retain those actual fields, not an
                # inferred full task record that the author has not read.
                for key, value in receipt['result'].items():
                    field = path + '/' + key.replace('~', '~0').replace('/', '~1')
                    active[field] = {'path': field, 'value': deepcopy(value),
                                     'read_call_id': message.tool_call_id}
                    if before_index is not None and index >= before_index:
                        active[field]['in_native_reply'] = True
                continue
            if before_index is not None and index >= before_index:
                if 'result' in receipt:
                    active[path] = {'path': path, 'value': deepcopy(receipt['result']),
                                    'in_native_reply': True}
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
    return list(active.values())


def _covers(parent, child):
    return child == parent or child.startswith(parent + '/')


def _saved_replacement(item, value, saved_paths):
    """Only refresh differences accounted for by host-accepted field saves."""
    path = item['path']
    if any(_covers(p, path) for p in saved_paths):
        return True
    if 'value' not in item:
        return False  # Do not turn a previously paginated read into full text.
    old = deepcopy(item['value'])
    try:
        for saved in saved_paths:
            if _covers(path, saved):
                relative = saved[len(path):]
                old = jsonpointer.set_pointer(old, relative,
                    deepcopy(jsonpointer.resolve_pointer(value, relative)), inplace=True)
    except (jsonpointer.JsonPointerException, TypeError, IndexError):
        return False
    return old == value


def editing_surface(candidate, fragment, reads, readback, saved_paths=()):
    """Expose exact current statements and bounded, explicitly read fields.

    Retain explicitly read fields and accepted edits for the active revision.
    The native draft owns saved paths, including recovered successful saves.
    Failed proposals cannot add paths or replace values. Old field text is
    never revived, and unread sections of the original paper stay on demand.
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
    fresh = []
    for item in reads:
        path = item['path']
        try:
            value = jsonpointer.resolve_pointer(candidate, path)
        except jsonpointer.JsonPointerException:
            continue
        if item.get('in_native_reply') and value == item.get('value'):
            fresh.append(path)
            continue  # One exact copy, in the unconsumed native tool reply.
        if ('value' in item and value != item['value']) or (
                'value_fingerprint' in item and canonical_sha256(value) != item['value_fingerprint']):
            if not _saved_replacement(item, value, saved_paths):
                continue
            item = {'path': path, 'value': deepcopy(value),
                    'read_call_id': item.get('read_call_id'), 'origin': 'current_saved_revision'}
        # The target claim is already complete in current_fragment.
        if isinstance(value, dict) and value.get('claim_id') in hot:
            continue
        kept.append({**deepcopy(item), 'read': readback(ROOT + path)})
    # Accumulate the *current* accepted values, not past versions or receipts.
    # Parent fields subsume their children. A later unrelated save must not
    # retire the author's earlier changes before reconciliation/finalization.
    for path in sorted(set(saved_paths), key=lambda p: (p.count('/'), p)):
        if (path in {'', '/claims'} or any(_covers(p, path) for p in fresh)
                or any('value' in r and _covers(r['path'], path) for r in kept)):
            continue
        try:
            value = jsonpointer.resolve_pointer(candidate, path)
        except jsonpointer.JsonPointerException:
            continue
        if isinstance(value, dict) and value.get('claim_id') in hot:
            continue
        kept = [r for r in kept if not _covers(path, r['path'])]
        kept.append({'path': path, 'value': deepcopy(value), 'origin': 'current_saved_revision',
                     'read': readback(ROOT + path)})
    kept = [r for r in kept if not any(_covers(p, r['path']) for p in fresh)
            and not any('value' in parent and parent['path'] != r['path']
                        and _covers(parent['path'], r['path']) for parent in kept)]
    for item in kept:
        if _covers('/task_note', item['path']):
            item['role'] = 'saved_research_record_not_current_revision_requirements'
    for index, item in enumerate(kept):
        value = item.get('value')
        if isinstance(value, dict) and value.get('claim_id'):
            for row in outline:
                if row['claim_id'] == value['claim_id']:
                    row.pop('statement', None)
                    row['current_value_at'] = f'/current_context/submission_to_repair/manuscript/open_fields/{index}/value'
    return {'claim_outline': outline, 'open_fields': kept,
            'basis': 'current_candidate_exact_values_not_new_tasks',
            'lifecycle': 'read_and_saved_fields_follow_current_revision; replace_on_save; release_at_revision_end; whole_record_on_demand'}
