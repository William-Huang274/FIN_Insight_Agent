"""Append source-scoped industry metric reviews to an unpublished library."""
import argparse
import json
from pathlib import Path
from sec_agent.research_foundation.metric_reviews import import_reviews


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',required=True)
    parser.add_argument('--reviews',required=True)
    parser.add_argument('--reviewed-at',required=True)
    args=parser.parse_args()
    reviews=json.loads(Path(args.reviews).read_text(encoding='utf-8-sig'))
    count=import_reviews(args.build,reviews,reviewed_at=args.reviewed_at)
    print(json.dumps({'reviewed_fields':count,'old_observations_modified':0}))


if __name__=='__main__':main()
