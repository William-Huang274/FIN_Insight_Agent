import pytest

from sec_agent.research_foundation.public_network import browser_options, http_options, network_feedback, proxy_url


def test_default_route_does_not_replace_existing_environment(monkeypatch):
    monkeypatch.delenv('FIN_PUBLIC_HTTPS_PROXY', raising=False)
    assert http_options() == {}
    assert browser_options() == {}


def test_explicit_route_shared_without_exposing_credentials(monkeypatch):
    monkeypatch.setenv('FIN_PUBLIC_HTTPS_PROXY', 'http://reader:secret@localhost:1234')
    assert http_options() == {'proxy': 'http://reader:secret@localhost:1234', 'trust_env': False}
    assert browser_options() == {'proxy': {'server': 'http://localhost:1234', 'username': 'reader', 'password': 'secret'}}
    feedback = str(network_feedback())
    assert 'configured_proxy' in feedback
    assert 'secret' not in feedback and '1234' not in feedback


@pytest.mark.parametrize('value', ['https://host/path', 'file:///tmp/proxy', 'http://host:1234?token=x'])
def test_reject_unsupported_proxy_configuration(monkeypatch, value):
    monkeypatch.setenv('FIN_PUBLIC_HTTPS_PROXY', value)
    with pytest.raises(ValueError):
        proxy_url()
