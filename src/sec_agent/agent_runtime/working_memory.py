"""Local working papers: free prose, SQLite revisions, optional FTS5 navigation.

This is a task-artifact adapter, not an evidence admission or workflow engine.
Host-provided owner/workspace/actor identifiers never come from model arguments.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class WorkingMemory:
    def __init__(self, path, *, owner, workspace, actor):
        if not all(isinstance(x, str) and x for x in (owner, workspace, actor)):
            raise ValueError("working_memory_scope_required")
        self.path = Path(path)
        self.owner, self.workspace, self.actor = owner, workspace, actor

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            # Conservative mode on older embedded runtimes (SQLite WAL-reset fix 3.51.3).
            db.execute("PRAGMA journal_mode=" + ("WAL" if sqlite3.sqlite_version_info >= (3,51,3) else "DELETE"))
            db.execute("""CREATE TABLE IF NOT EXISTS working_notes (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, workspace TEXT NOT NULL,
                actor TEXT NOT NULL, title TEXT NOT NULL, version INTEGER NOT NULL,
                body TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS working_note_versions (
                id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
                updated_at TEXT NOT NULL, PRIMARY KEY(id, version))""")
            db.commit()
            yield db
        finally:
            db.close()

    def save(self, title: str, body: str, base_version: int = 0):
        # Only transport/resource limits; no heading, prose, citation or finance schema.
        if not title.strip() or len(title) > 240 or not body.strip() or len(body) > 200000:
            return {"saved": False, "reason": "名称需1–240字符，正文需1–200000字符；无必填章节，请分篇保存超长正文。"}
        identity = json.dumps([self.owner, self.workspace, self.actor, title], ensure_ascii=False)
        note_id = hashlib.sha256(identity.encode()).hexdigest()[:32]
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT * FROM working_notes WHERE id=?", (note_id,)).fetchone()
            if prior and prior["body"] == body:
                db.rollback()
                return {"saved": True, "note_id": note_id, "version": prior["version"], "unchanged": True}
            current = prior["version"] if prior else 0
            if base_version != current:
                db.rollback()
                return {"saved": False, "reason": "底稿已变化；先读当前版本再合并，旧请求未覆盖它。",
                        "note_id": note_id, "current_version": current}
            version = current + 1
            db.execute("INSERT INTO working_note_versions VALUES (?,?,?,?)", (note_id, version, body, now))
            db.execute("""INSERT INTO working_notes VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET body=excluded.body, version=excluded.version,
                updated_at=excluded.updated_at""",
                (note_id, self.owner, self.workspace, self.actor, title, version, body, now))
            db.commit()  # Body is durable BEFORE any optional indexing.
            try:
                self._index(db, note_id, title, body)
                indexed = True
            except sqlite3.Error:
                db.rollback()
                indexed = False
        return {"saved": True, "note_id": note_id, "version": version, "indexed": indexed,
                "notice": "工作底稿已保存；不是核验通过或新的事实来源。"}

    @staticmethod
    def _index(db, note_id, title, body):
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS working_notes_fts USING fts5(id UNINDEXED, title, body, tokenize='trigram')")
        db.execute("DELETE FROM working_notes_fts WHERE id=?", (note_id,))
        db.execute("INSERT INTO working_notes_fts VALUES (?,?,?)", (note_id, title, body))
        db.commit()

    def read(self, note_id, *, version=None, offset=0, limit=6000):
        offset, limit = max(0, offset), min(12000, max(1, limit))
        with self.connection() as db:
            row = db.execute("SELECT * FROM working_notes WHERE id=? AND owner=? AND workspace=?",
                             (note_id, self.owner, self.workspace)).fetchone()
            if row is None:
                return {"found": False, "notice": "当前研究空间没有此底稿。"}
            result = dict(row)
            if version is not None:
                old = db.execute("SELECT body, version, updated_at FROM working_note_versions WHERE id=? AND version=?",
                                 (note_id, version)).fetchone()
                if old is None:
                    return {"found": False, "notice": "此历史版本不存在。"}
                result.update(dict(old))
            text = result.pop("body")
            result.pop("owner")
            return {**result, "found": True, "body": text[offset:offset+limit], "offset": offset,
                    "total_characters": len(text), "next_offset": offset+limit if offset+limit < len(text) else None,
                    "is_current": result["version"] == row["version"],
                    "notice": "模型工作底稿，可能有错误；历史版本不是当前决定，原始证据需按来源回读。"}

    def search(self, query="", *, actor=None, offset=0, limit=12):
        """Exact scope first; trigram FTS plus literal fallback, no embeddings/calls."""
        query = query.strip()[:500]
        limit, offset = min(30, max(1, limit)), max(0, offset)
        where, args = "owner=? AND workspace=?", [self.owner, self.workspace]
        if actor:
            where += " AND actor=?"
            args.append(actor)
        with self.connection() as db:
            ids = []
            if len(query) >= 3:
                try:
                    # Literal phrase: model text cannot become an FTS expression.
                    phrase = '"' + query.replace('"', '""') + '"'
                    ids = [r[0] for r in db.execute("""SELECT f.id FROM working_notes_fts f
                        JOIN working_notes n ON n.id=f.id WHERE working_notes_fts MATCH ?
                        AND n.owner=? AND n.workspace=? ORDER BY rank LIMIT 100""",
                        (phrase, self.owner, self.workspace))]
                except sqlite3.Error:
                    pass
            if query:
                # Always include canonical text: indexing failures cannot hide new prose.
                where += " AND (instr(lower(title), lower(?))>0 OR instr(lower(body), lower(?))>0)"
                args += [query, query]
            rows = db.execute(f"""SELECT id,actor,title,version,updated_at,substr(body,1,240) AS preview
                FROM working_notes WHERE {where} ORDER BY updated_at DESC,id LIMIT ? OFFSET ?""",
                [*args, limit+1, offset]).fetchall()
            more = len(rows) > limit
            items = [dict(row) for row in rows[:limit]]
            # Rank within the returned page; stable paging remains date/id based.
            items.sort(key=lambda r: ids.index(r["id"]) if r["id"] in ids else len(ids))
            return {"items": items, "next_offset": offset+limit if more else None,
                    "retrieval": "literal_fulltext_current_workspace", "notice": "只列当前版本；可缩短关键词或留空浏览。无匹配不代表资料不存在。"}

    def export_markdown(self, note_id, version=None):
        item = self.read(note_id, version=version, limit=12000)
        if not item.get("found"):
            return item
        pieces = [item["body"]]
        while item["next_offset"] is not None:
            item = self.read(note_id, version=item["version"], offset=item["next_offset"], limit=12000)
            pieces.append(item["body"])
        return {"title": item["title"], "version": item["version"], "markdown": "".join(pieces)}

    def manifest(self):
        """Pin versions for an explicit host-authorized handoff, without copying prose."""
        with self.connection() as db:
            return [dict(row) for row in db.execute("""SELECT id,title,actor,version FROM working_notes
                WHERE owner=? AND workspace=? ORDER BY id""", (self.owner,self.workspace))]
