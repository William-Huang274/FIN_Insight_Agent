"""Offline projection audit of exported canonical messages; never runs tools/models."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import jsonpointer
from langchain_core.messages import ToolMessage
from sec_agent.agent_runtime.harness_business_tools import model_receipt


def expanded(row, root):
    if isinstance(row, list):
        return [expanded(item, root) for item in row]
    if not isinstance(row, dict):
        return row
    result = {}
    for key, value in row.items():
        if key in {'shared_organization_source', 'shared_retrieval', 'shared_original_sources',
                   'original_source_inheritance', 'shared_source_provenance'}:
            continue
        if key in {'organization_source_ref', 'retrieval_ref', 'original_source_ref', 'source_provenance_ref'}:
            base = key[:-4]
            shared = jsonpointer.resolve_pointer(root, value[1:])
            result[base] = {**shared, **row.get(base, {})} if base == 'original_source' else shared
        elif key + '_ref' not in row:
            result[key] = expanded(value, root)
    return result


def audit(messages):
    totals = defaultdict(lambda: {'count': 0, 'original_characters': 0, 'model_characters': 0})
    largest = []
    for data in messages:
        if data.get('type') != 'tool':
            continue
        message = ToolMessage(**data)
        before = message.model_dump(mode='json')
        view = model_receipt(message)
        assert message.model_dump(mode='json') == before
        old_size = len(message.content) if isinstance(message.content, str) else len(json.dumps(message.content, ensure_ascii=False))
        new_size = len(json.dumps(view, ensure_ascii=False, separators=(',', ':')))
        total = totals[message.name]
        total['count'] += 1; total['original_characters'] += old_size; total['model_characters'] += new_size
        largest.append({'tool': message.name, 'receipt_id': message.tool_call_id,
                        'original_characters': old_size, 'model_characters': new_size})
        if view.get('original_readback'):
            assert view['original_readback']['arguments']['tool_call_id'] == message.tool_call_id
        try:
            original = json.loads(message.content)
        except (ValueError, TypeError):
            continue
        projected = view['result']
        if message.status != 'success' or not isinstance(original, dict):
            continue
        restored = expanded(projected, projected)
        if original.get('operation') in {'catalog', 'outline', 'search', 'read'} and isinstance(original.get('items'), list):
            assert len(original['items']) == len(restored['items'])
            for source, recovered in zip(original['items'], restored['items']):
                # All originals, exact evidence, IDs, periods, readback arguments,
                # statuses and unknown fields on this actual source protocol.
                assert source == recovered, (message.tool_call_id, 'item_changed')
            for key in ('next_offset', 'total_matches', 'source_snapshot_sha256'):
                assert original.get(key) == restored.get(key)
        if original.get('result_state') == 'non_authoritative_metric':
            assert original == restored, (message.tool_call_id, 'calculation_changed')
    return {'paid_calls': 0, 'canonical_messages_unchanged': True, 'groups': dict(totals),
            'largest': sorted(largest, key=lambda x: -x['original_characters'])[:15]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('messages', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.messages.read_text(encoding='utf-8'))
    result = audit(data['messages'] if isinstance(data, dict) else data)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result['groups'], ensure_ascii=False))


if __name__ == '__main__':
    main()
