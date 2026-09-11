import asyncio
import json
from types import SimpleNamespace

import httpx2
import pytest

from scripts.deployment import local_sandbox as deployment
from sec_agent.agent_runtime.sandbox_mcp import sandbox_server


@pytest.fixture
def settings(tmp_path):
    for name in deployment.FILES:
        (tmp_path / name).write_text(json.dumps({"unchanged": "财务资料", "other_secret": "fixture-only"}), encoding="utf-8")
    return tmp_path


def test_configuration_preserves_other_settings_backup_and_credential_on_repeat(settings):
    originals = {name: (settings / name).read_bytes() for name in deployment.FILES}
    receipt = deployment.configure(settings)
    token = deployment.connection(deployment.settings_pair(settings))
    assert len(token) >= 32 and token not in json.dumps(receipt)
    from pathlib import Path
    for name in deployment.FILES:
        assert (Path(receipt["backup"]) / name).read_bytes() == originals[name]
        data = json.loads((settings / name).read_text(encoding="utf-8"))
        assert data["unchanged"] == "财务资料" and data["other_secret"] == "fixture-only"
    assert deployment.configure(settings) == {"configured": True, "changed": False}
    assert deployment.connection(deployment.settings_pair(settings)) == token


def test_second_file_write_failure_restores_first(settings, monkeypatch):
    originals = {name: (settings / name).read_bytes() for name in deployment.FILES}
    write = deployment.atomic_write
    def fail_second(path, data):
        if path.name == "container-settings.json":
            raise OSError("fixture_write_failure")
        write(path, data)
    monkeypatch.setattr(deployment, "atomic_write", fail_second)
    with pytest.raises(OSError, match="fixture_write_failure"):
        deployment.configure(settings)
    assert all((settings / name).read_bytes() == raw for name, raw in originals.items())


@pytest.mark.parametrize("change", [
    {"conversation_sandbox_url": "http://unapproved.example/mcp"},
    {"conversation_sandbox_url": "http://127.0.0.1:18796/mcp", "conversation_sandbox_token": "short"},
    {"conversation_sandbox_url": "http://127.0.0.1:18796/mcp", "conversation_sandbox_token": "fixture-" * 8},
])
def test_conflicting_or_partial_configuration_is_not_overwritten(settings, change):
    path = settings / "host-settings.json"
    path.write_text(json.dumps(change), encoding="utf-8")
    originals = {name: (settings / name).read_bytes() for name in deployment.FILES}
    with pytest.raises(ValueError):
        deployment.configure(settings)
    assert all((settings / name).read_bytes() == raw for name, raw in originals.items())
    assert not (settings / "sandbox-config-backups").exists()


def test_invalid_second_file_cannot_partially_configure_first(settings):
    original = (settings / "host-settings.json").read_bytes()
    (settings / "container-settings.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        deployment.configure(settings)
    assert (settings / "host-settings.json").read_bytes() == original


def test_check_verifies_auth_and_catalog_without_execution(settings, monkeypatch):
    deployment.configure(settings)
    token = deployment.connection(deployment.settings_pair(settings))
    def never_execute(*args, **kwargs):
        pytest.fail("health check must not execute agent code")
    app = sandbox_server(SimpleNamespace(execute=never_execute), token=token, port=18796)
    original = httpx2.AsyncClient
    monkeypatch.setattr(httpx2, "AsyncClient", lambda **kwargs: original(transport=httpx2.ASGITransport(app=app), **kwargs))
    async def run():
        async with app.router.lifespan_context(app):
            result = await deployment.check(settings)
            assert result["authentication"] == "passed" and result["executions"] == 0
    asyncio.run(run())


def test_container_check_rejects_stale_mounted_credential(settings, monkeypatch):
    deployment.configure(settings)
    monkeypatch.setattr(deployment.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout=json.dumps({"credential_sha256": "stale", "catalog": "passed"})))
    with pytest.raises(ValueError, match="container_has_different_configuration"):
        deployment.check_container(settings, "fixture-native-runtime")


def test_container_check_failure_does_not_expose_transport_error_or_secret(settings, monkeypatch):
    deployment.configure(settings)
    token = deployment.connection(deployment.settings_pair(settings))
    monkeypatch.setattr(deployment.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1, stdout="", stderr="sensitive request " + token))
    with pytest.raises(ValueError, match="container_mcp_check_failed") as error:
        deployment.check_container(settings, "fixture-native-runtime")
    assert token not in str(error.value)
