from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download a model from ModelScope.")
    parser.add_argument("--model-id", default="Qwen/Qwen3-Embedding-0.6B")
    parser.add_argument(
        "--cache-dir",
        default="data/models_private/modelscope",
        help="ModelScope cache directory. Keep this under an ignored private data path.",
    )
    parser.add_argument("--revision")
    return parser.parse_args()


def main() -> None:
    from modelscope import snapshot_download

    args = parse_args()
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    kwargs = {"model_id": args.model_id, "cache_dir": str(cache_dir)}
    if args.revision:
        kwargs["revision"] = args.revision
    model_path = snapshot_download(**kwargs)
    print(json.dumps({"model_id": args.model_id, "model_path": model_path}, ensure_ascii=False))


if __name__ == "__main__":
    main()
