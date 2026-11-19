"""Lossless draft metadata repair and observed changes, not research approval."""
from copy import deepcopy
import re

from .research_graph_contracts import canonical_sha256
from .workpaper_changes import workpaper_changes


def normalize_response_metadata(candidate, issues):
    """Repair empty response metadata; never discard populated claim associations.

    Legacy empty claim metadata becomes an empty list. Populated IDs are supported
    by the response schema, not guessed or converted into evidence identities.
    The raw proposal remains in the native journal; return an explicit repair log.
    """
    corrected = deepcopy(candidate)
    repairs = []
    for issue in issues:
        loc = issue['loc']
        if (len(loc) != 4
                or tuple(loc[:2]) != ('task_note', 'finding_responses')):
            continue
        if issue['type'] != 'extra_forbidden' and not (loc[3] == 'claim_ids' and issue['type'] == 'list_type'):
            continue
        row = corrected['task_note']['finding_responses'][loc[2]]
        value = row[loc[3]]
        if value is not None and value != [] and value != {} and value != '':
            continue
        if loc[3] == 'claim_ids' and issue['type'] == 'list_type':
            repairs.append({'location': list(loc), 'operation': 'normalize_empty_response_claim_ids',
                            'original_value': deepcopy(value), 'normalized_value': []})
            row['claim_ids'] = []
            continue
        if issue['type'] != 'extra_forbidden':
            continue
        repairs.append({'location': list(loc), 'operation': 'remove_empty_unknown_response_field',
                        'original_value': deepcopy(value)})
        del row[loc[3]]
    return corrected, repairs


def draft_change_status(baseline, candidate):
    """Keep author completion assertions separate from mechanical version evidence.

    An affirmative prose-update assertion with identical prose is diagnosable.
    Changed prose alone never establishes that any claimed correction is complete.
    These advisories cannot block saving or require unrelated prose edits.
    """
    diff = workpaper_changes(baseline, candidate)
    paths = [r['path'] for r in diff['locations']]
    narrative_changed = '/narrative_markdown' in paths
    advisories = []
    claim_ids = {c.get('claim_id') for c in candidate.get('claims', [])}
    for i, response in enumerate((candidate.get('task_note') or {}).get('finding_responses') or []):
        unknown = [cid for cid in response.get('claim_ids', []) if cid not in claim_ids]
        if unknown:
            advisories.append({'location': ['task_note', 'finding_responses', i, 'claim_ids'],
                'code': 'unknown_response_claim_ids', 'claim_ids': unknown, 'blocking': False,
                'message': 'Associations were preserved, but these IDs do not resolve in the current manuscript. They confer no evidence authority or verified completion.'})
        explanation = response.get('explanation', '')
        # Narrow observable mismatch only; no general natural-language verifier.
        affirmed = re.search(r'正文[^。；\n]{0,120}?(?:均已|已经|已)(?:同步)?(?:改写|更新|修改)', explanation)
        if affirmed and re.search(r'尚未|未(?:曾)?(?:同步)?(?:改写|更新|修改)|没有(?:改写|更新|修改)|无需', affirmed.group(0)):
            affirmed = None
        if not affirmed:
            affirmed = re.search(r'(?:narrative|body|prose)\s+(?:has|have)\s+(?:already\s+)?been\s+(?:updated|rewritten|revised)', explanation, re.I)
        if affirmed and not narrative_changed:
            advisories.append({'location': ['task_note', 'finding_responses', i, 'explanation'],
                'code': 'claimed_prose_update_but_narrative_unchanged',
                'finding_id': response.get('finding_id'), 'claimed_text': affirmed.group(0),
                'blocking': False,
                'message': 'The narrative is identical to the revision baseline. This author completion claim is not supported by the saved diff. Correct the response or finish any genuinely needed prose edits before final submission; unrelated edits are not required.'})
    return {'baseline_digest': canonical_sha256(baseline), 'candidate_digest': canonical_sha256(candidate),
            'changed_claim_ids': diff['changed_claim_ids'], 'changed_fields': paths,
            'narrative_changed': narrative_changed,
            'author_dispositions_verified': False, 'semantic_status': 'not_independently_verified',
            'advisories': advisories}
