from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import subprocess


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "engineering"
    / "build_archive_redirect_index.py"
)
SPEC = importlib.util.spec_from_file_location("build_archive_redirect_index", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

PORTABLE_ARCHIVE_PATH_LIMIT = MODULE.PORTABLE_ARCHIVE_PATH_LIMIT
_portable_archive_path = MODULE._portable_archive_path
_source_and_version = MODULE._source_and_version
_canonical_archive_digest = MODULE._canonical_archive_digest


def test_portable_archive_path_is_bounded_and_preserves_mapping_authority() -> None:
    source_path = (
        "configs/releases/"
        + "very_long_financial_research_attempt_authority_decision_" * 8
        + "v1_0.json"
    )
    digest = hashlib.sha256(b"immutable historical artifact").hexdigest()

    archive_path = _portable_archive_path(
        source_path,
        "pre_fin_0_1_3/unpromoted_active_tree",
        digest,
    )
    path_map = {
        archive_path: {
            "archive_path": archive_path,
            "source_path": source_path,
            "origin_version": "pre_fin_0_1_3/unpromoted_active_tree",
            "sha256": digest,
        }
    }

    assert len(archive_path) <= PORTABLE_ARCHIVE_PATH_LIMIT
    assert "/_portable/" in archive_path
    assert _source_and_version(archive_path, path_map) == (
        source_path,
        "pre_fin_0_1_3/unpromoted_active_tree",
    )


def test_portable_archive_paths_do_not_collide_for_distinct_source_paths() -> None:
    digest = hashlib.sha256(b"same historical content").hexdigest()

    first = _portable_archive_path("configs/releases/first.json", "fin_0_1_2", digest)
    second = _portable_archive_path("configs/releases/second.json", "fin_0_1_2", digest)

    assert first != second


def test_archive_digest_uses_canonical_staged_blob_not_checkout_line_endings(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    relative = "archive/versions/fin_0_1_2/example.ps1"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(b"first\nsecond\n")
    subprocess.run(["git", "add", "--", relative], cwd=tmp_path, check=True)
    target.write_bytes(b"first\r\nsecond\r\n")

    assert _canonical_archive_digest(tmp_path, relative) == hashlib.sha256(
        b"first\nsecond\n"
    ).hexdigest()
