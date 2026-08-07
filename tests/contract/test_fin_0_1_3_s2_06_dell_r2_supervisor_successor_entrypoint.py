from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "scripts" / "releases"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from fin_ia_0_1_3_s2_06_dell_r2_supervisor_execution_support import (  # noqa: E402
    ENTRYPOINT_IMPLEMENTATION_REF,
    SupervisorExecutionSupportError,
    validate_authority_and_bindings,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_historical_r2_entrypoint_is_immutable_and_now_fails_closed() -> None:
    implementation = _load(ROOT / ENTRYPOINT_IMPLEMENTATION_REF)
    body = {
        key: value
        for key, value in implementation.items()
        if key != "implementation_digest"
    }
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert implementation["implementation_digest"] == hashlib.sha256(
        encoded
    ).hexdigest()
    assert implementation["stage_acceptance"]["DELL_R2_execution"] is False
    assert any(
        _sha256(ROOT / ref) != expected
        for ref, expected in implementation["implementation_bindings"].items()
    )
    with pytest.raises(
        SupervisorExecutionSupportError,
        match="s2_06_dell_r2_entrypoint_file_drift",
    ):
        validate_authority_and_bindings()
