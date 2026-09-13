"""Deployment environment parsing preserves literal values and hides file errors."""
import pytest

from scripts.deployment.environment import read_local_environment


def test_environment_file_is_literal_and_does_not_expand_shell_or_env(tmp_path):
    source = tmp_path / "deployment.env"
    source.write_text('# comment\nexport FIRST="a=b"\nSECOND=\'${FIRST}\'\nEMPTY=\n', encoding="utf-8-sig")
    assert read_local_environment(source) == {"FIRST": "a=b", "SECOND": "${FIRST}", "EMPTY": ""}


def test_missing_file_returns_typed_error(tmp_path):
    with pytest.raises(RuntimeError, match="^deployment_environment_missing$"):
        read_local_environment(tmp_path / "missing")
