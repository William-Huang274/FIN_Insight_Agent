"""Read-only development gate. External case records, no provider invocation."""
import argparse
import json
from pathlib import Path


def assess_gate(plan, records, stage_id):
    stages = {s['id']: s for s in plan['stages']}
    if stage_id not in stages:
        raise ValueError('unknown_stage')
    missing, visited = [], set()
    def inspect(key):
        if key in visited:
            return
        visited.add(key)
        stage = stages[key]
        for dependency in stage['depends_on']:
            inspect(dependency)
        for case in stage['cases']:
            record = records.get(case, {})
            for axis in stage['required']:
                if record.get(axis) != 'accepted' or not record.get('evidence_refs'):
                    missing.append({'stage':key,'case':case,'axis':axis,'state':record.get(axis,'not_tested')})
            if record.get('open_material_errors'):
                missing.append({'stage':key,'case':case,'axis':'material_errors','state':'open'})
    inspect(stage_id)
    return {'stage':stage_id,'passed':not missing,'missing':missing,
        'meaning':'Recorded engineering/research decisions only; does not independently judge research truth.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records',type=Path,required=True)
    parser.add_argument('--stage',required=True)
    args=parser.parse_args()
    plan=json.loads((Path(__file__).resolve().parents[2]/'configs/research/qualification/runtime_flow.json').read_text(encoding='utf-8'))
    result=assess_gate(plan,json.loads(args.records.read_text(encoding='utf-8')),args.stage)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
