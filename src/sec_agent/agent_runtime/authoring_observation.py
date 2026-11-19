"""Operator checkpoint after an actual author-selected chapter input; no model-facing instructions."""
import asyncio
import json

from langchain_core.messages import ToolMessage

from .authoring_sections import MATERIAL_TOOLS
from .harness_acp_session import _persist


class SavedChapterObservation:
    """Observe the first new or revised chapter, including writes within one native tool batch."""
    def __init__(self, workspace, marker):
        self.workspace = workspace
        self.marker = marker
        self.initial = self.versions()

    def versions(self):
        with self.workspace.connection() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='authoring_sections'").fetchone():
                return {}
            return dict(db.execute('SELECT section,MAX(revision) FROM authoring_sections GROUP BY section'))

    async def reached(self):
        if self.marker.exists():
            return True
        versions = await asyncio.to_thread(self.versions)
        changes = {k:v for k,v in versions.items() if v != self.initial.get(k)}
        if changes:
            _persist(self.marker, {'saved_chapters':changes})
        return bool(changes)

    async def ready(self):
        if await self.reached():
            await asyncio.sleep(5)
            return {'status':'waiting'}
        return {'status':'ready'}

    async def before_tool(self, name, arguments):
        if await self.reached():
            await asyncio.Event().wait()


class ChapterInputObservation:
    def __init__(self, workspace, bridge, marker):
        self.workspace = workspace
        self.bridge = bridge
        self.marker = marker
        self.input_basis = None

    def focus(self):
        with self.workspace.connection() as db:
            row = db.execute('SELECT section FROM authoring_focus WHERE id=1').fetchone()
            if row:
                state = self.workspace.authoring._state(db)
                chapter = state['sections'].get(row[0])
                if chapter:
                    return {'understanding_revision': state['revision'],
                            'chapter': {k: chapter[k] for k in ('id', 'question', 'role')}}

    def mark(self, reason, tool=None):
        if not self.marker.exists():
            _persist(self.marker, {'reason': reason, 'next_tool': tool, 'input_basis': self.input_basis})

    async def ready(self):
        if self.input_basis or self.marker.exists():
            self.mark('before_next_dispatch')
            await asyncio.sleep(5)
            return {'status': 'waiting'}
        focus = await asyncio.to_thread(self.focus)
        if focus:
            receipts = []
            for msg in (await self.bridge.state()).get('messages', []):
                if not isinstance(msg, ToolMessage) or msg.name not in MATERIAL_TOOLS or msg.status != 'success':
                    continue
                try:
                    body = json.loads(msg.content)
                except (ValueError, TypeError):
                    continue
                if isinstance(body, dict) and body.get('result_digest') and not body.get('error'):
                    if body.get('section_id') in (None, focus['chapter']['id']):
                        receipts.append(msg.tool_call_id)
            if receipts:
                self.input_basis = {**focus, 'material_receipt_ids': receipts}
        return {'status': 'ready'}

    async def before_tool(self, name, arguments):
        writing = (name == 'authoring_section' and arguments.get('action') == 'save'
                   or name in {'save_research_report', 'edit_research_report', 'repair_report_fields', 'deliver_current_report'})
        if self.input_basis or writing or self.marker.exists():
            self.mark('after_material_input' if self.input_basis else 'write_before_identified_material_input', name)
            # Cancellation leaves the original provider response in the audit and the paper unchanged.
            await asyncio.Event().wait()
