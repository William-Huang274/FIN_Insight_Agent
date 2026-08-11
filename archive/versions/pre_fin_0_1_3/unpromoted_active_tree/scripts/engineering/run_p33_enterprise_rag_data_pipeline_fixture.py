from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.p33_enterprise_rag_data_pipeline_fixture import (  # noqa: E402
    build_p33_enterprise_rag_data_pipeline_fixture,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build P33-1.1 enterprise RAG/data pipeline no-paid fixture.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--no-rebuild-p14", action="store_true", help="Read existing P14 outputs instead of rebuilding them.")
    args = parser.parse_args(argv)

    manifest = build_p33_enterprise_rag_data_pipeline_fixture(
        args.repo_root.resolve(),
        rebuild_p14=not args.no_rebuild_p14,
        write_outputs=True,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0 if manifest.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
