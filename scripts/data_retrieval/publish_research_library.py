"""Publish an immutable public graph/retrieval release; never modify source DBs."""
import argparse
import json
from pathlib import Path
from sec_agent.research_foundation.research_library import publish_library


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', action='append', required=True)
    parser.add_argument('--public-nodes', type=Path)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--confirm-public-sources', action='store_true')
    args = parser.parse_args()
    nodes = [json.loads(line) for line in args.public_nodes.read_text(encoding='utf-8').splitlines() if line.strip()] if args.public_nodes else ()
    print(json.dumps(publish_library(args.target, args.snapshot, public_sources_confirmed=args.confirm_public_sources, public_nodes=nodes), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
