import json
import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "engineering" / "build_p32_learning_source_snapshots.py"
SPEC = importlib.util.spec_from_file_location("build_p32_learning_source_snapshots", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)

LearningSource = module.LearningSource
build_snapshot_row = module.build_snapshot_row
extract_html_title = module.extract_html_title
load_learning_sources = module.load_learning_sources
write_jsonl = module.write_jsonl


def test_extract_html_title() -> None:
    assert extract_html_title(b"<html><title>  FIN&nbsp;Insight </title></html>") == "FIN Insight"


def test_load_learning_sources_reads_source_and_pattern_rows(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        "\n".join(
            [
                json.dumps({"source_id": "s1", "source_type": "pdf", "source_title": "A", "source_url": "https://example.com/a"}),
                json.dumps({"pattern_id": "p1", "source_type": "docs", "source_title": "B", "source_url": "docs/local.md"}),
            ]
        ),
        encoding="utf-8",
    )

    rows = load_learning_sources([ledger])

    assert [row.source_key for row in rows] == ["s1", "p1"]
    assert rows[1].source_url == "docs/local.md"


def test_build_snapshot_row_samples_local_file_inside_repo(tmp_path: Path) -> None:
    local = tmp_path / "docs" / "local.md"
    local.parent.mkdir()
    local.write_text("hello", encoding="utf-8")
    source = LearningSource("p1", "docs", "Local", "docs/local.md", "ledger.jsonl")

    row = build_snapshot_row(source, repo_root=tmp_path, now_iso="2026-07-04T00:00:00+00:00", fetcher=None)

    assert row["snapshot_status"] == "local_file_sampled"
    assert row["sample_bytes"] == 5
    assert row["sample_sha256"]


def test_build_snapshot_row_offline_external_skip(tmp_path: Path) -> None:
    source = LearningSource("s1", "web", "Web", "https://example.com", "ledger.jsonl")

    row = build_snapshot_row(source, repo_root=tmp_path, now_iso="2026-07-04T00:00:00+00:00", fetcher=None)

    assert row["snapshot_status"] == "external_fetch_skipped"


def test_write_jsonl(tmp_path: Path) -> None:
    output = tmp_path / "out" / "rows.jsonl"
    count = write_jsonl([{"a": 1}, {"b": 2}], output)

    assert count == 2
    assert [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()] == [{"a": 1}, {"b": 2}]
