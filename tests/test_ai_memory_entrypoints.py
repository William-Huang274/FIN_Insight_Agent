"""Archived module names remain usable after qualification package cleanup."""
import importlib
import subprocess
import sys

import pytest


@pytest.mark.parametrize("name", ["context_probe", "final_evidence_probe", "phase_checkpoint_probe", "model_comparison"])
def test_old_and_canonical_modules_are_identical(name):
    old = importlib.import_module("scripts.qualification.ai_memory_" + name)
    current = importlib.import_module("scripts.qualification.ai_memory." + name)
    assert old is current


@pytest.mark.parametrize("name", ["final_evidence_probe", "model_comparison"])
def test_compatibility_cli_help_does_not_execute_research(name):
    result = subprocess.run([sys.executable, "-m", "scripts.qualification.ai_memory_" + name, "--help"],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "--output" in result.stdout
