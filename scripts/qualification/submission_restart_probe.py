"""Zero-model real BFF receipt replay before/after an operator service restart."""
import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=['prepare', 'replay'], required=True)
    args = parser.parse_args()
    body = {'title': '208 durable submission receipt', 'mode': 'research',
            'question': '仅建立无模型运行的隔离验收草稿，保留提交回执。', 'defer_start': True}
    if args.phase == 'prepare':
        args.output.mkdir(parents=True, exist_ok=False)
        key = str(uuid4())
    else:
        prior = json.loads((args.output/'prepare.json').read_text(encoding='utf-8'))
        key = prior['key']
    headers = {'X-Workbench-Request': '1', 'Idempotency-Key': key}
    with httpx.Client(base_url='http://127.0.0.1:18795', trust_env=False, timeout=30) as client:
        first = client.post('/api/v1/research-sessions', json=body, headers=headers)
        first.raise_for_status()
        result = first.json()
        again = client.post('/api/v1/research-sessions', json=body, headers=headers)
        again.raise_for_status()
        assert again.json() == result and again.headers.get('Idempotent-Replayed') == 'true'
        if args.phase == 'replay':
            assert result == prior['result'] and first.headers.get('Idempotent-Replayed') == 'true'
        tid = result['thread_id']
        with httpx.Client(base_url='http://127.0.0.1:18165', trust_env=False, timeout=30) as native:
            runs = native.get(f'/threads/{tid}/runs')
            runs.raise_for_status()
            assert runs.json() == []
        evidence = {'key': key, 'result': result, 'replayed': True, 'native_model_runs': 0}
        (args.output/f'{args.phase}.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print(json.dumps({'phase': args.phase, 'thread_id': tid, 'replayed': True, 'native_model_runs': 0}))


if __name__ == '__main__':
    main()
