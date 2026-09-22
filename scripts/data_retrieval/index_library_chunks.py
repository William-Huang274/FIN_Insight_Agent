"""Explicit corpus embedding, persisted vector matrix, and usage accounting."""
import argparse
import json
from pathlib import Path
from retrieval.library_vectors import prepare
from scripts.deployment.research_workbench import configured_key
from sec_agent.research_foundation.research_library import ResearchLibrary


def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--execute',action='store_true')
    p.add_argument('--skip-blocked',action='store_true',help='Process never-submitted texts only; leave failed/unknown texts and index publication pending.')
    p.add_argument('--retry-request-id',action='append',default=[],help='Explicitly approved failed/unknown request ID; retain original receipt and create one new attempt.')
    a=p.parse_args()
    key=configured_key('QWEN_API_KEY') if a.execute else ''
    if a.execute and not key:raise ValueError('QWEN_API_KEY_not_configured')
    print(json.dumps(prepare(ResearchLibrary(a.library),a.cache,key,a.audit,execute=a.execute,skip_blocked=a.skip_blocked,retry_request_ids=a.retry_request_id)))


if __name__=='__main__':main()
