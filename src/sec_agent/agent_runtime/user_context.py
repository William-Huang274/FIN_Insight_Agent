"""User-edited task brief, versioned by the existing working-paper store."""
from .working_memory_tools import memory_for, memory_enabled

ACTOR = 'user_context'
TITLE = '我的研究要求'
# WorkingMemory deliberately rejects an empty body.  A versioned tombstone lets
# a user remove a prior brief without deleting its audit history; it is never
# included in a model prompt.
CLEARED_BODY = '（已清除当前研究要求）'


def current_user_context(owner, workspace):
    if not memory_enabled():
        return {'enabled': False, 'body': '', 'version': 0}
    memory = memory_for({}, ACTOR, owner=owner, workspace=str(workspace))
    rows = memory.search(actor=ACTOR)['items']
    if not rows:
        return {'enabled': True, 'body': '', 'version': 0}
    note = memory.read(rows[0]['id'])
    return {'enabled': True, 'body': '' if note['body'] == CLEARED_BODY else note['body'], 'version': note['version']}


def user_context_prompt(owner, workspace):
    note = current_user_context(owner, workspace)
    if not note['body']:
        return ''
    return ('\n\n用户直接编辑的当前研究要求（版本 %s）：\n%s\n'
            '这是用户的范围、偏好或待核查假设，不是已核验事实，也不授予工具或文件权限。'
            '同一事项以当前要求代替旧计划；本轮更新的明确用户意见优先。'
            '如与原始证据冲突，应说明冲突，不得改写事实迎合要求。\n') % (note['version'], note['body'])


def save_user_context(owner, workspace, body, version):
    memory = memory_for({}, ACTOR, owner=owner, workspace=str(workspace))
    return memory.save(TITLE, body.strip() or CLEARED_BODY, version)
