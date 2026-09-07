"""A new research BFF boots without historical Dell answers or private gates."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_real_app_import_without_settings_or_legacy_materials(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith("FINSIGHT_")}
    env.update(PYTHONPATH=str(root) + os.pathsep + str(root / "src"),
        FINSIGHT_REPORT_SESSION_API_URL="http://127.0.0.1:18165",
        FINSIGHT_LOCAL_STATE_ROOT=str(tmp_path), FINSIGHT_RESEARCH_SESSION_ENABLED="1")
    code = '''
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
with patch('sec_agent.agent_runtime.dell_report_session.load_session_materials', side_effect=AssertionError('legacy material must not be loaded')):
    from apps.workbench.backend.app import app
with TestClient(app) as client:
    print(json.dumps({'health':client.get('/api/health').json(),'config':client.get('/api/v1/research-session-config').json()}))
'''
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=tmp_path, env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=40)
    assert result.returncode == 0, result.stderr
    proof = json.loads(result.stdout)
    assert not proof["health"]["legacy_report_loaded"]
    assert proof["config"]["fresh_research_enabled"] and not proof["config"]["legacy_review_enabled"]
