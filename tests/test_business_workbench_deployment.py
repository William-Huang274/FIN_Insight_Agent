import json
from pathlib import Path

from fastapi.testclient import TestClient
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_business_runtime_preserves_role_migrations_without_old_case_dependencies():
    current = yaml.safe_load((ROOT/'deploy/agent_server/compose.yaml').read_text())
    independent = yaml.safe_load((ROOT/'deploy/agent_server/compose.business-workbench.yaml').read_text())
    for service in ('langgraph-postgres', 'langgraph-redis'):
        assert independent['services'][service] == current['services'][service]
    native = independent['services']['langgraph-api']
    assert all(port.startswith('127.0.0.1:') for port in native['ports'])
    env = native['environment']
    assert env['FINSIGHT_RESEARCH_SESSION_ENABLED'] == '0'
    assert env['FINSIGHT_ORGANIZATION_START_ENABLED'] == '0'
    assert not any(env.get(k) for k in ('DEEPSEEK_API_KEY','OPENAI_API_KEY','DASHSCOPE_API_KEY'))
    graphs = json.loads(env['LANGSERVE_GRAPHS'])
    assert graphs['research_session']['path'] == 'sec_agent.agent_runtime.research_session_runtime:research_session_graph'
    assert not any('qualification' in str(v) or 'reviewed' in str(v) for v in native['volumes'])


def test_preparation_config_does_not_enable_personal_research(tmp_path, monkeypatch):
    monkeypatch.setenv('FINSIGHT_REPORT_SESSION_API_URL','http://127.0.0.1:18865')
    monkeypatch.setenv('FINSIGHT_LOCAL_STATE_ROOT',str(tmp_path))
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_PREPARATION_ENABLED','1')
    monkeypatch.setenv('FINSIGHT_RESEARCH_SESSION_ENABLED','0')
    monkeypatch.setenv('FINSIGHT_AUTH_MODE','local')
    monkeypatch.setenv('FIN_REPO_ROOT',str(ROOT))
    monkeypatch.delenv('FINSIGHT_REPORT_SESSION_SETTINGS',raising=False)
    monkeypatch.delenv('FINSIGHT_BUSINESS_API_URL',raising=False)
    from apps.workbench.backend.app import create_app
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/research-session-config').json()['fresh_research_enabled'] is False
        assert client.get('/api/health').json()['legacy_report_loaded'] is False
