"""Precompute reviewed financial formulas in a mutable research-library build."""
import argparse
from datetime import date
import json
from pathlib import Path
from sec_agent.research_foundation.derived_financials import materialize

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--as-of',type=date.fromisoformat,required=True)
    a=p.parse_args()
    print(json.dumps(materialize(a.db,a.as_of.isoformat()),ensure_ascii=False))
