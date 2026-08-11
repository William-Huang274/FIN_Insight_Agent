"""Build lightweight source snapshots for P32 learning ledgers.

This script does not promote any external source into an active registry. It
only records whether a learning-ledger source is addressable and stores a small
sample hash / title so later work can replay the learning provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping


DEFAULT_LEDGER_PATHS = (
    Path("docs/project_os/financial_research_method_learning_ledger.jsonl"),
    Path("docs/project_os/agent_engineering_pattern_learning_ledger.jsonl"),
)


@dataclass(frozen=True)
class LearningSource:
    source_key: str
    source_type: str
    source_title: str
    source_url: str
    ledger_path: str


def _read_jsonl(path: Path) -> Iterable[dict]:
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object")
        yield row


def load_learning_sources(paths: Iterable[Path]) -> list[LearningSource]:
    sources: list[LearningSource] = []
    for path in paths:
        for row in _read_jsonl(path):
            source_key = str(row.get("source_id") or row.get("pattern_id") or "").strip()
            source_url = str(row.get("source_url") or "").strip()
            if not source_key or not source_url:
                continue
            sources.append(
                LearningSource(
                    source_key=source_key,
                    source_type=str(row.get("source_type") or "").strip(),
                    source_title=str(row.get("source_title") or "").strip(),
                    source_url=source_url,
                    ledger_path=str(path),
                )
            )
    return sources


_TITLE_RE = re.compile(rb"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def extract_html_title(sample: bytes) -> str:
    match = _TITLE_RE.search(sample)
    if not match:
        return ""
    raw = re.sub(rb"\s+", b" ", match.group(1)).strip()
    try:
        title = html.unescape(raw.decode("utf-8", errors="replace"))
        return re.sub(r"\s+", " ", title.replace("\xa0", " ")).strip()
    except Exception:
        return ""


def fetch_url_snapshot(url: str, timeout: float, max_bytes: int) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "FINInsightAgent/0.1 source-snapshot; contact=local",
            "Accept": "text/html,application/pdf,text/plain,*/*;q=0.8",
            "Range": f"bytes=0-{max(0, max_bytes - 1)}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            sample = response.read(max_bytes)
            headers = response.headers
            return {
                "snapshot_status": "fetched_sample",
                "http_status": getattr(response, "status", None),
                "final_url": response.geturl(),
                "content_type": headers.get("content-type", ""),
                "content_length_header": headers.get("content-length", ""),
                "sample_bytes": len(sample),
                "sample_sha256": hashlib.sha256(sample).hexdigest() if sample else "",
                "sample_title": extract_html_title(sample),
            }
    except urllib.error.HTTPError as exc:
        return {
            "snapshot_status": "http_error",
            "http_status": exc.code,
            "final_url": url,
            "content_type": exc.headers.get("content-type", "") if exc.headers else "",
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "snapshot_status": "fetch_error",
            "final_url": url,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def build_snapshot_row(
    source: LearningSource,
    *,
    repo_root: Path,
    now_iso: str,
    fetcher: Callable[[str], Mapping[str, object]] | None,
) -> dict:
    url = source.source_url
    base = {
        "schema_version": "fin_insight_p32_learning_source_snapshot_v0_1",
        "snapshot_at": now_iso,
        "source_key": source.source_key,
        "source_type": source.source_type,
        "source_title": source.source_title,
        "source_url": url,
        "ledger_path": source.ledger_path,
    }
    if url.startswith(("http://", "https://")):
        if fetcher is None:
            return {**base, "snapshot_status": "external_fetch_skipped"}
        return {**base, **dict(fetcher(url))}

    local_path = (repo_root / url).resolve()
    try:
        local_path.relative_to(repo_root.resolve())
    except ValueError:
        return {**base, "snapshot_status": "local_path_outside_repo", "resolved_path": str(local_path)}

    if not local_path.exists():
        return {**base, "snapshot_status": "local_path_missing", "resolved_path": str(local_path)}
    sample = local_path.read_bytes()[:65536]
    return {
        **base,
        "snapshot_status": "local_file_sampled",
        "resolved_path": str(local_path),
        "sample_bytes": len(sample),
        "sample_sha256": hashlib.sha256(sample).hexdigest() if sample else "",
        "sample_title": "",
    }


def write_jsonl(rows: Iterable[dict], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--ledger", type=Path, action="append", default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/manifests/p32_learning_source_snapshots_v0_1.jsonl"),
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-bytes", type=int, default=65536)
    parser.add_argument("--offline", action="store_true", help="Do not fetch external URLs.")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    ledger_paths = args.ledger or list(DEFAULT_LEDGER_PATHS)
    sources = load_learning_sources([repo_root / path for path in ledger_paths])
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    fetcher = None
    if not args.offline:
        fetcher = lambda url: fetch_url_snapshot(url, timeout=args.timeout, max_bytes=args.max_bytes)
    rows = [
        build_snapshot_row(source, repo_root=repo_root, now_iso=now_iso, fetcher=fetcher)
        for source in sources
    ]
    count = write_jsonl(rows, repo_root / args.output)
    print(json.dumps({"output": str(args.output), "row_count": count}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
