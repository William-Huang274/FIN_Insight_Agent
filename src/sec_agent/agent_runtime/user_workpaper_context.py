"""Small owner-scoped navigation to human revisions; originals stay in SQLite."""
import json
import sqlite3


def human_revision_catalog(memory, offset=0, limit=20):
    with memory.connection() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='working_note_user_edits'").fetchone():
            return {'items': [], 'next_offset': None}
        rows = db.execute('''SELECT n.id,n.title,n.actor,n.version,MAX(e.version) AS user_version
            FROM working_notes n JOIN working_note_user_edits e ON e.id=n.id
            WHERE n.owner=? AND n.workspace=? GROUP BY n.id ORDER BY MAX(e.updated_at) DESC,n.id
            LIMIT ? OFFSET ?''', (memory.owner, memory.workspace, limit + 1, offset)).fetchall()
        return {'items': [dict(r) for r in rows[:limit]], 'next_offset': offset + limit if len(rows) > limit else None}


def human_revision_prompt(config, actor, *, owner=None, workspace=None):
    from .working_memory_tools import memory_for, memory_enabled
    if not memory_enabled():
        return ''
    try:
        catalog = human_revision_catalog(memory_for(config, actor, owner=owner, workspace=workspace))
    except (sqlite3.Error, OSError, ValueError):
        return '\n用户底稿修订目录暂不可读取；不能声称已经核对最新修改。请保留未完成状态并报告存储问题。'
    if not catalog['items']:
        return ''
    return ('\n用户曾直接修改以下工作底稿。目录仅用于定位，不是正文或已核验事实。'
            '继续依赖相关判断前，用ReadWorkingNote按id回读当前version；如需理解用户修改，另读user_version。'
            '区分用户假设、原始来源和研究判断；若与原件矛盾，明确解释，不能改事实迎合用户。'
            '旧会话、旧摘要和旧底稿不能代替当前版本。WriteWorkingNote仍须提交当前base_version，冲突时重新读合并。'
            '目录最多20项；有next_offset时可用SearchWorkingNotes(user_edits_only=true,offset=next_offset)继续浏览。\n'
            + json.dumps(catalog, ensure_ascii=False))


def current_scope_revision_prompt(actor):
    from .working_memory_tools import _native_memory_scope
    scope = _native_memory_scope.get()
    if scope is None:
        return ''
    return human_revision_prompt({}, actor, owner=scope[0], workspace=scope[1])
