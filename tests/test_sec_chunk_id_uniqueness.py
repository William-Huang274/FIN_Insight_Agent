from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ingestion.parse_sec_filing import _unique_block_id  # noqa: E402


def test_unique_block_id_preserves_first_occurrence_and_suffixes_duplicates() -> None:
    occurrences: dict[str, int] = {}

    assert _unique_block_id("MSFT_2026_10Q_ITEM2_BLOCK_0001", occurrences) == "MSFT_2026_10Q_ITEM2_BLOCK_0001"
    assert _unique_block_id("MSFT_2026_10Q_ITEM2_BLOCK_0001", occurrences) == "MSFT_2026_10Q_ITEM2_BLOCK_0001_OCC_02"
    assert _unique_block_id("MSFT_2026_10Q_ITEM2_BLOCK_0001", occurrences) == "MSFT_2026_10Q_ITEM2_BLOCK_0001_OCC_03"
    assert _unique_block_id("MSFT_2026_10Q_ITEM7_BLOCK_0001", occurrences) == "MSFT_2026_10Q_ITEM7_BLOCK_0001"
