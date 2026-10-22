import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException
from apps.workbench.backend.organization_index_registration import registration_status
from test_organization_research_inputs import fixture


@pytest.mark.parametrize('fault',[None,'missing','unavailable','wrong_draft','wrong_release','revoked','changed'])
def test_registration_readback_checks_scope_and_never_authorizes_retry(tmp_path,fault):
    _,grant=fixture(tmp_path)
    project,draft,release=grant['project_id'],grant['id'],str(uuid4())
    contract=dict(release_id=release,index_digest='a'*64,matrix_sha256='b'*64,
                  model='qwen3.7-text-embedding',dimensions=1024,projection='organization-text-6000.v1')
    calls=[]
    async def authority(actor,method,path):
        calls.append((method,path))
        assert actor=='alice'
        if method=='POST':
            assert path.endswith('/material-access')
            if fault=='revoked':raise HTTPException(404)
            if fault=='changed' and len(calls)>1:return {**grant,'manifest_digest':'sha256:'+'b'*64}
            return deepcopy(grant)
        assert method=='GET' and path==f'projects/{project}/retrieval-releases/{release}'
        if fault in ('missing','unavailable'):raise HTTPException(404 if fault=='missing' else 503)
        return {'contract':{**contract,'release_id':str(uuid4())} if fault=='wrong_release' else contract,
                'source_draft_id':str(uuid4()) if fault=='wrong_draft' else draft}
    if fault not in (None,'missing'):
        with pytest.raises(HTTPException):asyncio.run(registration_status(authority,'alice',project,draft,release))
        if fault=='revoked':assert len(calls)==1
    else:
        result=asyncio.run(registration_status(authority,'alice',project,draft,release))
        assert result['status']==('registered' if fault is None else 'unconfirmed')
        assert result['retry_allowed'] is False
        if fault is None:assert result['contract']==contract
        else:assert 'contract' not in result
        assert len(calls)==3
