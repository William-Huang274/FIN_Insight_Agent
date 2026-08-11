from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "releases"))

from inspect_fin_ia_0_1_2_s4_t05_c_mu_agent_exact_live_utf8_safe import render_for_host_stdout  # noqa: E402


def test_safe_inspector_is_printable_under_legacy_windows_stdout() -> None:
    rendered = render_for_host_stdout({"text": "one • two", "公司": "美光"})
    assert all(ord(char) < 128 for char in rendered)
    assert "\\u2022" in rendered
    rendered.encode("gbk", errors="strict")
