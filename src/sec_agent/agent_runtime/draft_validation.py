"""Lossless draft metadata repair and observed changes, not research approval."""
from copy import deepcopy
import re

from .research_graph_contracts import canonical_sha256
from .workpaper_changes import workpaper_changes


def remove_empty_response_extras(candidate, issues):
    """Only discard schema-rejected empty metadata on author finding responses.

    Never discard content, repair identities, coerce types, or change known fields.
    The raw proposal remains in the native journal; return an explicit repair log.
    """
    corrected = deepcopy(candidate)
    repairs = []
    for issue in issues:
        loc = issue['loc']
        if (issue['type'] != 'extra_forbidden' or len(loc) != 4
                or tuple(loc[:2]) != ('task_note', 'finding_responses')):
            continue
        row = corrected['task_note']['finding_responses'][loc[2]]
        value = row[loc[3]]
        if value is not None and value != [] and value != {} and value != '':
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
    for i, response in enumerate((candidate.get('task_note') or {}).get('finding_responses') or []):
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
