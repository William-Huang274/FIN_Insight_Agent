from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract
ROOT = Path(__file__).resolve().parents[2]


def test_m4_synthetic_persistent_pilot_preflight_is_read_only_after_setup(tmp_path: Path) -> None:
    output = tmp_path / "preflight.json"
    subprocess.run(
        [sys.executable, "scripts/engineering/run_point01_m4_synthetic_pilot_preflight.py", "--work-root", str(tmp_path / "persistent-synthetic"), "--output", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["pilot_kind"] == "isolated_nonproduction_synthetic_persistent_case"
    assert result["mutation_performed"] is False
    assert result["downstream_consumer_count"] == 0
    assert result["authority_before_after"] == {"before": "legacy", "after": "legacy"}
    assert len(result["backup_snapshot_sha256"]) == 64
    assert result["source_store_integrity_check"]["status"] == "pass"
    assert result["backup_restore_drill"]["status"] == "pass"
    assert result["backup_restore_drill"]["exact_bindings_match"] is True
    assert result["backup_restore_drill"]["content_fingerprint_match"] is True
    source = SQLiteCanonicalStore(tmp_path / "persistent-synthetic" / "canonical.sqlite")
    restored = SQLiteCanonicalStore(tmp_path / "persistent-synthetic" / "restores" / "preflight_restored.sqlite")
    assert source.store_identity() != restored.store_identity()
    assert source.content_fingerprint() == restored.content_fingerprint()
    source.set_kill_switch(True)
    assert source.content_fingerprint() != restored.content_fingerprint()
