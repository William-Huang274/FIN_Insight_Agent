"""Read committed registration without assuming a missing row means no work is running."""
from fastapi import HTTPException
from .organization_research_inputs import validate_grant
from sec_agent.research_foundation.organization_index_release import validate_contract


async def registration_status(authority, actor, project, draft, release):
    path = f'projects/{project}/research-drafts/{draft}/material-access'
    before = await authority(actor, 'POST', path)
    validate_grant(before, project, draft)
    result = {'release_id': release, 'status': 'unconfirmed', 'retry_allowed': False}
    try:
        saved = await authority(actor, 'GET', f'projects/{project}/retrieval-releases/{release}')
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        # No completion record is not proof of failure or permission to resend.
    else:
        try:
            contract = validate_contract(saved['contract'])
            if contract['release_id'] != release or str(saved['source_draft_id']) != draft:
                raise ValueError('registration_identity_mismatch')
        except (KeyError, TypeError, ValueError):
            raise HTTPException(409, '登记结果与原准备单或索引标识不一致') from None
        result.update(status='registered', contract=contract)
    if await authority(actor, 'POST', path) != before:
        raise HTTPException(409, '读取登记结果期间资料授权发生变化')
    return result
