"""Resolve sources used by current, assembled chapters for the report reader."""
from collections import defaultdict
from datetime import datetime
import json

from langchain_core.messages import ToolMessage, message_to_dict

from sec_agent.research_foundation.calculation_receipt_restore import public_capture_identity
from sec_agent.research_foundation.saved_web_navigation import read_saved_web_window
from sec_agent.research_foundation.source_bound_calculator import source_observation_identity, sources_from_receipts
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from .authoring_sections import AuthoringSections
from .public_source_restore import validated_public_source
from .report_synthesis_agent import answer_reference_ids
from .research_graph_contracts import canonical_sha256


def same_source(left, right):
    """The same public passage may have several genuine reads of identical bytes."""
    if left == right:
        return True

    def identity(item):
        value = source_observation_identity(item)
        if value.get('source_role') == 'external_public_source_unverified':
            validated_public_source(item)
            if value.get('source_locator', {}).get('captured_at'):
                value = public_capture_identity(value)
            value.pop('source_read_method', None)
        return value
    return identity(left) == identity(right)


def archive_chapter_citations(db, prose, messages, previous=None):
    wanted = set(answer_reference_ids(prose))
    receipts = {ref: key for ref, key in (previous or {}).items() if ref in wanted}
    wanted.difference_update(receipts)
    for message in messages:
        if not wanted:
            break
        if not isinstance(message, ToolMessage) or not message.artifact or message.status != 'success':
            continue
        matched = wanted.intersection(sources_from_receipts([{
            'name': message.name, 'status': message.status, 'artifact': message.artifact}]))
        if matched:
            key = message.tool_call_id
            wire = message_to_dict(message)
            row = db.execute('SELECT payload FROM evidence WHERE id=?', (key,)).fetchone()
            if row and json.loads(row[0]) != wire:
                raise ValueError('chapter_original_receipt_changed')
            db.execute('INSERT OR IGNORE INTO evidence VALUES (?,?)', (key, json.dumps(wire, ensure_ascii=False)))
            receipts.update(dict.fromkeys(matched, key))
            wanted.difference_update(matched)
    return receipts


def selected_originals(workspace, db, chapter):
    """Follow host receipts, never parse a source binding out of workpaper prose."""
    originals = set()
    for key, meta in chapter['receipts'].items():
        row = db.execute('SELECT payload FROM evidence WHERE id=?', (key,)).fetchone()
        if not row:
            raise ValueError('chapter_material_receipt_missing')
        message = json.loads(row[0])['data']
        if (message['tool_call_id'] != key or message['name'] != meta['tool']
                or message['status'] != 'success' or canonical_sha256(message['content']) != meta['content_digest']):
            raise ValueError('chapter_material_receipt_changed')
        body = json.loads(message['content'])
        if message['name'] in {'read_synthesis_material', 'read_research_workpaper'} and body.get('topic_id'):
            paper = workspace._get(db, body['topic_id'], body['revision'])
            if paper['digest'] != body['digest']:
                raise ValueError('chapter_workpaper_digest_changed')
            originals.update(paper['evidence_receipt_ids'])
        elif message['name'] == 'read_workpaper_evidence' and body.get('source_evidence') is not False:
            originals.add(body['receipt_id'])
        elif message['name'] == 'reuse_adopted_judgment':
            originals.update(source['receipt_id'] for source in body['sources'])
        else:
            originals.add(key)
    return originals


def _source_rows(db, keys, wanted, as_of):
    rows = {}
    # Older papers sometimes kept only the calculator's exact operand locator
    # and a wider passage from the same capture. Require both for exact recovery.
    documents = {ref.rsplit('::', 2)[0][len('PASSAGE::'):] for ref in wanted if ref.startswith('PASSAGE::WEB::')}
    windows = defaultdict(list)
    operands = defaultdict(list)
    for key in sorted(keys):
        record = db.execute('SELECT payload FROM evidence WHERE id=?', (key,)).fetchone()
        if not record:
            continue
        data = json.loads(record[0])['data']
        if data.get('tool_call_id') != key:
            raise ValueError('chapter_original_receipt_changed')
        for ref, item in sources_from_receipts([data]).items():
            if ref in wanted:
                if ref in rows and not same_source(rows[ref], item):
                    raise ValueError('chapter_source_identity_conflict:' + ref)
                rows.setdefault(ref, item)
            if item.get('document_id') in documents:
                loc = item.get('source_locator') or {}
                windows[item['document_id'], loc.get('capture_receipt_digest')].append(item)
            for operand in item.get('operands', {}).values():
                if operand.get('source_id') in wanted:
                    operands[operand['source_id']].append(operand.get('source_provenance', {}))
    for ref in wanted - rows.keys():
        for provenance in operands[ref]:
            loc = provenance.get('source_locator') or {}
            if not ref.startswith('PASSAGE::WEB::') or not loc.get('capture_receipt_digest'):
                continue
            start, end = loc.get('character_start'), loc.get('character_end')
            if type(start) is not int or type(end) is not int or not 100 <= end - start <= 80000:
                continue
            for window in windows[loc['document_id'], loc['capture_receipt_digest']]:
                bounds = window['source_locator']
                if bounds['character_start'] <= start < end <= bounds['character_end']:
                    request = SourceDocumentRequest(source_space='web', operation='read',
                        document_id=loc['document_id'], offset=start, max_characters=end-start)
                    result = read_saved_web_window(request, [window], research_as_of=as_of)
                    exact = result.items[0]
                    if (exact.get('passage_id') == ref and exact.get('source_locator') == loc
                            and exact.get('content_sha256') == provenance.get('content_sha256')):
                        rows[ref] = exact
                        break
            if ref in rows:
                break
    return rows


class ChapterVersionsChanged(ValueError):
    def __init__(self, edit):
        super().__init__('assembled_chapter_versions_changed')
        self.changes = edit['changed_chapters']
        self.refresh = edit['readback']


def assembled_chapter_sources(workspace, requested, *, for_report_save=False):
    if (not requested and not for_report_save) or not workspace.authoring_active():
        return {}
    chapters = AuthoringSections(workspace)
    sources = {}
    with workspace.connection() as db:
        edit = chapters.editing_status(db)
        if for_report_save and edit.get('changed_chapters'):
            raise ChapterVersionsChanged(edit)
        if not requested or edit['status'] != 'editing':
            return {}
        state = workspace.authoring._state(db)
        as_of = datetime.fromisoformat(db.execute('SELECT as_of FROM identity').fetchone()[0])
        for key, draft in chapters._latest(db).items():
            if edit['chapters'].get(key) != draft['revision'] or chapters._status(db, draft, state) != 'current':
                continue
            wanted = set(requested).intersection(answer_reference_ids(draft['prose']))
            if wanted:
                direct = {receipt for ref, receipt in draft.get('citation_receipts', {}).items() if ref in wanted}
                rows = _source_rows(db, direct, wanted, as_of)
                missing = wanted - rows.keys()
                if missing:
                    rows.update(_source_rows(db, selected_originals(workspace, db, draft), missing, as_of))
                for ref, item in rows.items():
                    if ref in sources and not same_source(sources[ref], item):
                        raise ValueError('chapter_source_identity_conflict:' + ref)
                    sources.setdefault(ref, item)
    return sources
