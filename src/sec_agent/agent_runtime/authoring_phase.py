"""Host-pinned, saved-material-only native authoring phase.

The native harness owns the model loop. This module owns the phase identity,
immutable seed and tool capability boundary, not research conclusions.
"""
import json
import shutil
import sqlite3
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL
from .authoring_editorial import EDITORIAL_BRIEF
from .authoring_materials import workpaper_locator


AUTHORING_TOOLS = frozenset({
    'reuse_adopted_judgment', 'read_research_workpaper', 'research_updates', 'read_workpaper_evidence',
    'read_authoring_context', 'update_research_understanding',
    'prepare_research_synthesis', 'read_synthesis_material', 'bind_research_synthesis',
    'read_saved_result', 'get_research_method', 'calculate_research_metric', 'create_report_chart',
    'save_research_report', 'repair_report_fields', 'read_current_report',
    'edit_research_report', 'deliver_current_report',
    'authoring_section',
})


def file_digest(path):
    h = sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def pinned_file(ref):
    path = Path(ref['path']).resolve(strict=True)
    if file_digest(path) != ref['sha256']:
        raise ValueError('authoring_phase_seed_digest_mismatch')
    return path


def prepare_authoring_phase(binding, directory, *, tid, question, as_of):
    """Create once; resumed sessions retain their own changes, never reseed."""
    phase_id = str(UUID(binding['id']))
    entry = json.loads(pinned_file(binding['entry']).read_text(encoding='utf8'))
    seed = pinned_file(binding['database'])
    mode = binding.get('mode', 'write_from_research')
    if mode not in {'write_from_research', 'edit_saved_chapters'}:
        raise ValueError('unknown_authoring_phase_mode')
    if (entry['root_id'] != tid or entry['original_question'] != question
            or entry['as_of'] != as_of or not entry['research_question'].strip()
            or not entry['source_checkpoint'].get('checkpoint_id')):
        raise ValueError('authoring_phase_identity_mismatch')
    with sqlite3.connect(f'{seed.as_uri()}?mode=ro', uri=True) as db:
        if db.execute('SELECT root,question,as_of FROM identity').fetchall() != [(tid,question,as_of)]:
            raise ValueError('authoring_phase_workspace_identity_mismatch')
        actual = {t:{'revision':r,'digest':d} for t,r,d in db.execute(
            'SELECT p.topic,p.revision,p.digest FROM papers p WHERE p.revision=(SELECT MAX(q.revision) FROM papers q WHERE q.topic=p.topic)')}
        if actual != entry['catalog_versions']:
            raise ValueError('authoring_phase_catalog_mismatch')
        row = db.execute('SELECT revision,digest,payload FROM understanding ORDER BY revision DESC LIMIT 1').fetchone()
        if not row or {'revision':row[0],'digest':row[1]} != entry['understanding']:
            raise ValueError('authoring_phase_understanding_mismatch')
        state = json.loads(row[2])
        chapters = {}
        for table in ('reads','snapshots','bindings','authoring_report','section_bindings','authoring_issues','authoring_resolutions','authoring_sections','authoring_focus','authoring_editing','authoring_workset','authoring_released_materials'):
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
                if table == 'authoring_sections' and mode == 'edit_saved_chapters':
                    chapters = {s: {'revision':r, 'digest':sha256(p.encode('utf8')).hexdigest()}
                        for s,r,p in db.execute('''SELECT section,revision,payload FROM authoring_sections a
                            WHERE revision=(SELECT MAX(revision) FROM authoring_sections b WHERE b.section=a.section)''')}
                    continue
                if db.execute(f'SELECT 1 FROM {table} LIMIT 1').fetchone():
                    raise ValueError('authoring_phase_seed_contains_later_authoring_state')
        if mode == 'edit_saved_chapters' and (not chapters or chapters != entry.get('chapters')):
            raise ValueError('authoring_phase_chapter_manifest_mismatch')
        if mode == 'edit_saved_chapters':
            from .research_graph_contracts import canonical_sha256
            for (payload,) in db.execute('SELECT payload FROM authoring_sections'):
                for key,ref in json.loads(payload).get('receipts',{}).items():
                    evidence=db.execute('SELECT payload FROM evidence WHERE id=?',(key,)).fetchone()
                    if not evidence or canonical_sha256(json.loads(evidence[0])['data']['content'])!=ref['content_digest']:
                        raise ValueError('authoring_phase_chapter_receipt_not_archived')
    target = Path(directory) / ('authoring-' + phase_id)
    target.mkdir(parents=True, exist_ok=True)
    marker = target / 'authoring-phase.json'
    destination = target / 'research-workpapers.sqlite'
    identity = {'binding':binding,'root_id':tid}
    if marker.exists():
        if json.loads(marker.read_text(encoding='utf8')) != identity or not destination.exists():
            raise ValueError('authoring_phase_binding_changed')
    else:
        if destination.exists() and file_digest(destination) != binding['database']['sha256']:
            raise ValueError('authoring_phase_unconfirmed_seed')
        if not destination.exists():
            temporary = target / 'research-workpapers.seed.tmp'
            shutil.copyfile(seed, temporary)
            temporary.replace(destination)
        temporary = target / 'authoring-phase.tmp'
        temporary.write_text(json.dumps(identity,ensure_ascii=False),encoding='utf8')
        temporary.replace(marker)
    context = {'phase':'authoring_saved_materials_only','source_checkpoint':entry['source_checkpoint'],
        'question':entry['research_question'],'as_of':as_of,
        'understanding':entry['understanding'],
        'current_state_location':'The live runtime authoring state supplies current findings and report orientation once; read_authoring_context recovers complete current records.',
        'full_state_readback':{'tool':'read_authoring_context','arguments':{}},
        'writing_workflow':'Choose a reader-facing report outline; select/open the current writing workset without deleting other chapters. '
            'Use section_ids for chapter material snapshots; use a whole-report snapshot only for final binding. '
            'Save complete prose and the successful material receipts used before moving on. '
            'Previously saved chapter details can leave active context; exact drafts and evidence remain readable. '
            'Use authoring_section(action="assemble", section_id="") for whole-report editing after drafting. '
            'Reuse current lead findings via reuse_adopted_judgment and save its receipt. Open exact originals for changed claims, conflicts or precise quantities. '
            'Historical corrections and stage status remain in full-state readback; select what the reader needs, '
            'preserving substantive assumptions and counterevidence rather than transcribing every audit note.',
        'materials': [workpaper_locator(ref, 'outline') for ref in entry['materials']],
        'mode':mode, 'editorial_brief':EDITORIAL_BRIEF,
        'saved_chapters':chapters,
        'historical_outline':'The saved outline is provisional. Choose the structure and materials the answer needs.',
        'scope':'Use saved arguments and sources. No new retrieval, delegation or independent review. '
                'If new investigation is necessary, explain the missing relationship and stop without delivery.'}
    memory = str(uuid5(NAMESPACE_URL,tid+':authoring:'+phase_id))
    return target, memory, context


def first_saved_outline(workspace, seed_revision):
    """Return the earliest authored report map, excluding judgment-only revisions."""
    with workspace.connection() as db:
        initial = workspace.authoring._state(db, seed_revision)['sections']
        for (revision,) in db.execute('SELECT revision FROM understanding WHERE revision>? ORDER BY revision',
                                      (seed_revision,)):
            state = workspace.authoring._state(db, revision)
            sections = state['sections']
            if sections and sections != initial and all(
                    row['question'].strip() and row['role'].strip() for row in sections.values()):
                return {'revision': revision, 'digest': state['digest'],
                        'outline': workspace.authoring.orientation(state)['outline']}
    return None


def authoring_grants(grants):
    return [g for g in grants if g.tool.name in AUTHORING_TOOLS]
