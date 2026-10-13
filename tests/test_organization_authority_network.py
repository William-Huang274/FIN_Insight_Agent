"""Deployment URL choices cannot be expanded by task or redirect data."""
from uuid import uuid4

import httpx
import pytest

from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionAuthority, OrganizationExecutionUnavailable


def authority(url, profile='loopback', **kwargs):
    return OrganizationExecutionAuthority(base_url=url, network_profile=profile,
        secret='static-network-test-secret-at-least-32-bytes', execution_id=str(uuid4()),
        manifest_digest='sha256:'+'a'*64, **kwargs)


@pytest.mark.parametrize('url,profile', [
    ('http://host.docker.internal:8095','loopback'),
    ('http://127.0.0.1:8095','docker-desktop-host'),
    ('http://host.docker.internal.example.test:8095','docker-desktop-host'),
    ('http://192.168.1.2:8095','docker-desktop-host'),
    ('http://host.docker.internal:8095/path','docker-desktop-host'),
    ('http://user:secret@host.docker.internal:8095','docker-desktop-host'),
    ('http://host.docker.internal:8095?redirect=elsewhere','docker-desktop-host'),
    ('http://host.docker.internal:8095#fragment','docker-desktop-host'),
    ('http://host.docker.internal','docker-desktop-host'),
    ('http://host.docker.internal:0','docker-desktop-host'),
    ('http://host.docker.internal:65536','docker-desktop-host'),
    ('http://host.docker.internal:8095','arbitrary-host'),
])
def test_authority_rejects_url_outside_explicit_deployment_profile(url,profile):
    with pytest.raises(ValueError): authority(url,profile)


@pytest.mark.parametrize('url,profile', [('http://localhost:8095','loopback'),
    ('http://127.0.0.1:8095','loopback'),('http://host.docker.internal:8095','docker-desktop-host')])
def test_signed_call_uses_one_origin_without_redirect_or_retry(url,profile):
    calls=[]
    def handler(request):
        calls.append(request)
        assert str(request.url)==url+'/v1/runtime/test'
        assert request.headers['authorization'].startswith('Bearer ')
        return httpx.Response(302,headers={'Location':'http://external.invalid/steal'})
    client=authority(url,profile,transport=httpx.MockTransport(handler))
    with pytest.raises(OrganizationExecutionUnavailable): client.request('/v1/runtime/test',{})
    assert len(calls)==1
