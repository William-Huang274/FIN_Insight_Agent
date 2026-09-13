"""Rebuild one read-only fact snapshot from compatible, captured source policies.

Uses the existing SEC parser and mart builder. Inputs are immutable; conflicting
definitions or source bindings require an explicit data decision, not last-wins.
"""
import argparse
import json
from pathlib import Path

from financial_facts.mart import build_company_fact_mart
from financial_facts.sec_companyfacts import load_company_fact_mart_policy


def combine(policies):
    result = dict(policies[0])
    for key in ('schema_version', 'minimum_period_end', 'allowed_forms', 'metric_definitions', 'authority'):
        if any(p[key] != result[key] for p in policies):
            raise ValueError('incompatible_financial_snapshot:' + key)
    sources = {}
    for policy in policies:
        for row in policy['source_bindings']:
            if row['ticker'] in sources and sources[row['ticker']] != row:
                raise ValueError('conflicting_issuer_snapshot:' + row['ticker'])
            sources[row['ticker']] = row
    result['source_bindings'] = [sources[k] for k in sorted(sources)]
    result['research_as_of'] = max(p['research_as_of'] for p in policies)
    result['recorded_at'] = max(p['recorded_at'] for p in policies)
    result['acceptance_qrels'] = []  # Existing old acceptance evidence is not relabeled as a new run.
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--policy',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    policy=combine([json.loads(p.read_text(encoding='utf-8')) for p in args.policy])
    loaded=load_company_fact_mart_policy(policy, require_acceptance_qrels=False)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'policy.json').write_text(json.dumps(policy,indent=2),encoding='utf-8')
    result=build_company_fact_mart(loaded,repository_root=Path.cwd(),sqlite_path=args.output/'financial-facts.sqlite')
    (args.output/'build-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'status':result['status'],'counts':result['counts']}))


if __name__=='__main__':main()
