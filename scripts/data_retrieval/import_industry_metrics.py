"""Validate/import reviewed industry observations into an unpublished SQL build."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from sec_agent.research_foundation.industry_metrics import import_pack, validate_pack
from sec_agent.research_foundation.metric_workspace import materialize_contract


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',required=True)
    parser.add_argument('--pack',action='append',required=True)
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args()
    packs=[json.loads(Path(p).read_text(encoding='utf-8-sig')) for p in args.pack]
    with closing(sqlite3.connect(Path(args.build).resolve().as_uri()+'?mode=ro',uri=True)) as db:
        for pack in packs:validate_pack(db,pack)
    if args.validate_only:
        print(json.dumps({'validated_packs':len(packs),'writes':0}));return
    results=[import_pack(args.build,pack) for pack in packs]
    print(json.dumps({'imports':results,'metric_contract_records':materialize_contract(args.build)},ensure_ascii=False))


if __name__=='__main__':main()
