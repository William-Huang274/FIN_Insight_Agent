from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge append-only JSONL staging shards.")
    parser.add_argument("--input", action="append", dest="inputs", required=True, help="Input JSONL path. Repeat for multiple shards.")
    parser.add_argument("--output", required=True, help="Merged output JSONL path.")
    parser.add_argument("--summary-output", default="", help="Summary JSON path. Defaults to <output>.summary.json.")
    parser.add_argument("--require-unique-field", default="", help="Optional field that must be unique across shards.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = _resolve(Path(args.output))
    summary_path = _resolve(Path(args.summary_output)) if args.summary_output else output_path.with_suffix(output_path.suffix + ".summary.json")
    summary = merge_jsonl_shards(
        inputs=[_resolve(Path(path)) for path in args.inputs],
        output_path=output_path,
        summary_path=summary_path,
        require_unique_field=str(args.require_unique_field or ""),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "pass" else 1


def merge_jsonl_shards(
    *,
    inputs: list[Path],
    output_path: Path,
    summary_path: Path,
    require_unique_field: str = "",
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    seen_values: set[str] = set()
    duplicate_values: list[str] = []
    input_summaries: list[dict[str, Any]] = []
    total_rows = 0
    parse_errors: list[dict[str, Any]] = []

    with tmp_path.open("w", encoding="utf-8") as out:
        for path in inputs:
            row_count = 0
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    text = line.rstrip("\n")
                    if not text.strip():
                        continue
                    if require_unique_field:
                        try:
                            payload = json.loads(text)
                        except json.JSONDecodeError as exc:
                            parse_errors.append({"path": _path_for_metadata(path), "line_number": line_number, "error": str(exc)})
                            continue
                        value = str(payload.get(require_unique_field) or "")
                        if not value:
                            parse_errors.append({"path": _path_for_metadata(path), "line_number": line_number, "error": f"missing {require_unique_field}"})
                            continue
                        if value in seen_values:
                            duplicate_values.append(value)
                        seen_values.add(value)
                    out.write(text)
                    out.write("\n")
                    row_count += 1
                    total_rows += 1
            input_summaries.append({"path": _path_for_metadata(path), "rows": row_count})
    tmp_path.replace(output_path)
    summary = {
        "schema_version": "fin_agent_jsonl_shard_merge_summary_v0.1",
        "status": "pass" if not parse_errors and not duplicate_values else "fail",
        "output": _path_for_metadata(output_path),
        "inputs": input_summaries,
        "row_count": total_rows,
        "unique_field": require_unique_field,
        "duplicate_count": len(duplicate_values),
        "duplicate_sample": duplicate_values[:50],
        "parse_error_count": len(parse_errors),
        "parse_errors": parse_errors[:50],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _path_for_metadata(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
