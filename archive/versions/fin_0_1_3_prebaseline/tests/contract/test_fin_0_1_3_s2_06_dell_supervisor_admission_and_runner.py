from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "scripts" / "releases"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from fin_ia_0_1_3_s2_06_supervisor_execution_support import (  # noqa: E402
    SupervisorExecutionSupportError,
    load_case_material,
    validate_authority_and_bindings,
)


def test_consumed_r1_entrypoint_fails_closed_after_successor_contract() -> None:
    with pytest.raises(
        SupervisorExecutionSupportError,
        match="s2_06_implementation_file_drift",
    ):
        validate_authority_and_bindings()


def test_unknown_case_is_rejected_before_any_provider_work() -> None:
    with pytest.raises(
        SupervisorExecutionSupportError,
        match="s2_06_case_not_allowed",
    ):
        load_case_material("UNKNOWN")
