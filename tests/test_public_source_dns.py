import socket
import json
import pytest
from sec_agent.research_foundation.external_sources import PublicURLGuard, ExternalSourceError


@pytest.mark.parametrize('address,allowed',[('93.184.216.34',True),('127.0.0.1',False)])
def test_transient_dns_retry_still_checks_address(monkeypatch,address,allowed):
    calls=[]
    monkeypatch.setattr('sec_agent.research_foundation.external_sources.time.sleep',lambda _:None)
    def resolve(host):
        calls.append(host)
        if len(calls)==1:raise socket.gaierror(socket.EAI_AGAIN,'temporary')
        return (address,)
    guard=PublicURLGuard(resolver=resolve)
    if allowed:assert guard.validate('https://example.com/a')=='https://example.com/a'
    else:
        with pytest.raises(ExternalSourceError,match='address_forbidden'):
            guard.validate('https://example.com/a')
    assert len(calls)==2


@pytest.mark.parametrize('code,attempts',[(socket.EAI_AGAIN,2),(socket.EAI_NONAME,1)])
def test_dns_failure_keeps_host_code_and_never_claims_missing_source(monkeypatch,code,attempts):
    calls=[]
    monkeypatch.setattr('sec_agent.research_foundation.external_sources.time.sleep',lambda _:None)
    def resolve(host):
        calls.append(host);raise socket.gaierror(code,'failed')
    with pytest.raises(ExternalSourceError) as e:
        PublicURLGuard(resolver=resolve).validate('https://example.com/a')
    data=json.loads(str(e.value).split(':',1)[1])
    assert data['host']=='example.com' and data['resolver_code']==code
    assert data['temporary']==(code==socket.EAI_AGAIN)
    assert not data['http_request_dispatched'] and len(calls)==attempts
