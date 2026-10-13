"""Check frozen organization input identities and custody; never create a run."""
from datetime import datetime, timezone
import re
from uuid import UUID

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from sec_agent.research_foundation.asset_workspace import AssetRef, AssetConflict
from sec_agent.research_foundation.project_asset_access import ProjectAssetUnavailable


def validate_grant(grant, project_id, draft_id):
    try:
        manifest = grant['manifest']
        org = str(UUID(grant['organization_id']))
        if (str(grant['id']) != str(draft_id) or str(grant['project_id']) != str(project_id)
                or manifest['draft_id'] != str(draft_id) or manifest['project_id'] != str(project_id)
                or manifest['organization_id'] != org
                or manifest['contract_version'] != 'organization_research_inputs.v1'
                or manifest['visibility_policy'] != 'current_project_and_all_inputs'
                or not re.fullmatch(r'sha256:[a-f0-9]{64}', grant['manifest_digest'])):
            raise ValueError('grant_scope')
        inputs = grant['inputs']
        frozen = {str(UUID(item['resource_id'])): item for item in manifest['inputs']}
        if not 1 <= len(inputs) <= 12 or len(frozen) != len(manifest['inputs']) or len(inputs) != len(frozen):
            raise ValueError('input_count')
        seen = set()
        for item in inputs:
            identifier = str(UUID(item['resource_id']))
            binding, selected = item['binding'], frozen[identifier]
            ref = AssetRef.model_validate(binding['ref'])
            if (identifier in seen or binding['organization_id'] != org
                    or binding['space_id'] != selected['space_id'] or str(ref.project_id) != binding['space_id']
                    or binding['ref'] != selected['ref']):
                raise ValueError('input_scope')
            seen.add(identifier)
        return org, inputs
    except (KeyError, ValueError, TypeError, AttributeError):
        raise HTTPException(502, '研究输入授权身份或固定版本不匹配') from None


def verify_storage(shared, org, inputs):
    checked = []
    for item in inputs:
        ref = AssetRef.model_validate(item['binding']['ref'])
        try:
            # resolve verifies original bytes, version digest and any captured financial/source snapshot.
            version, _ = shared.workspace.resolve('organization:' + org, ref)
        except KeyError:
            raise HTTPException(409, '已保存的研究原件缺失；准备单保留，请恢复存储后重新校验') from None
        except (AssetConflict, ProjectAssetUnavailable, ValueError, OSError):
            raise HTTPException(409, '固定研究原件暂不可核实；不会替换版本或启动研究') from None
        checked.append({'resource_id': item['resource_id'], 'ref': version['ref']})
    return checked


async def verify_inputs(shared, authority, actor, project_id, draft_id):
    path = f'projects/{project_id}/research-drafts/{draft_id}/material-access'
    grant = await authority(actor, 'POST', path)
    org, inputs = validate_grant(grant, project_id, draft_id)
    checked = await run_in_threadpool(verify_storage, shared, org, inputs)
    # No distributed transaction: recheck after I/O and fail on any intervening revocation.
    after = await authority(actor, 'POST', path)
    validate_grant(after, project_id, draft_id)
    if after != grant:
        raise HTTPException(409, '研究输入授权发生变化，请重新读取原准备单')
    return {'id': str(draft_id), 'project_id': str(project_id), 'manifest_digest': grant['manifest_digest'],
            'status': 'inputs_verified', 'checked_at': datetime.now(timezone.utc).isoformat(),
            'inputs': checked, 'execution_enabled': False,
            'notice': '本次权限与原件校验通过；不是启动许可，未创建研究运行。'}
