"""Mechanical version/position records; never infer that a finding is resolved."""
from copy import deepcopy
from difflib import SequenceMatcher

from .research_graph_contracts import canonical_sha256


FIELDS = ("thesis", "mechanism", "narrative_markdown", "counterevidence", "what_would_change", "open_gaps", "task_note")


def claim_changes(before, after):
    """Exact changed fields, not a model-selected research scope."""
    old = {c['claim_id']: c for c in before.get('claims', [])}
    new = {c['claim_id']: c for c in after.get('claims', [])}
    rows = []
    for cid in sorted(old.keys() | new.keys()):
        if old.get(cid) == new.get(cid):
            continue
        left, right = old.get(cid, {}), new.get(cid, {})
        fields = []
        for key in sorted(left.keys() | right.keys()):
            if key in left and key in right and left[key] == right[key]:
                continue
            a, b = left.get(key), right.get(key)
            row = {'field': key, 'before_present': key in left, 'after_present': key in right,
                   'before_digest': canonical_sha256(a), 'after_digest': canonical_sha256(b)}
            if isinstance(a, str) and isinstance(b, str):
                row['edits'] = [{'before_span': [i, j], 'after_span': [x, y],
                    'before_text': a[i:j], 'after_text': b[x:y],
                    'current_context': b[max(0, x-80):min(len(b), y+80)]}
                    for op, i, j, x, y in SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if op != 'equal']
            else:
                row.update(before_value=deepcopy(a), after_value=deepcopy(b))
            fields.append(row)
        rows.append({'claim_id': cid, 'change_kind': 'added' if cid not in old else 'removed' if cid not in new else 'modified',
                     'fields': fields, 'unchanged_fields': sorted(k for k in left.keys() & right.keys() if left[k] == right[k])})
    return rows


def workpaper_changes(before, after):
    old = {c["claim_id"]: c for c in before.get("claims", [])}
    new = {c["claim_id"]: c for c in after.get("claims", [])}
    changed = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
    locations = []
    for field in FIELDS:
        left, right = before.get(field), after.get(field)
        if left == right:
            continue
        row = {"path": "/" + field, "before_digest": canonical_sha256(left), "after_digest": canonical_sha256(right)}
        if isinstance(left, str) and isinstance(right, str):
            row["spans"] = [{"before": [a, b], "after": [c, d]} for op, a, b, c, d in
                SequenceMatcher(None, left, right, autojunk=False).get_opcodes() if op != "equal"]
        locations.append(row)
    return {"baseline_digest": canonical_sha256(before), "current_digest": canonical_sha256(after),
        "comparison_basis": "recorded_before_after_versions",
        "changed_claim_ids": changed, "claim_changes": claim_changes(before, after), "locations": locations,
        "position_unit": "unicode_characters_zero_based_half_open",
        "semantic_status": "not_independently_verified",
        "notice": "Runtime-observed changes only. Read current changed sections with their necessary context and source/claim bindings before judgment; offsets are navigation, not financial verification."}


def paper_versions(artifacts):
    return {p["paper_id"]: canonical_sha256(artifacts.read_paper(p["paper_id"])) for p in artifacts.catalog()["papers"]}


def partition_author_responses(value):
    """Project old mixed handoffs without changing their original journal."""
    value = deepcopy(value)
    if not value:
        return value
    historical = value.setdefault('historical_author_responses', {})
    for pid, findings in value.get('findings_to_confirm', {}).items():
        ids = {f['finding_id'] for f in findings if f.get('finding_id')}
        rows = value.get('author_responses', {}).get(pid, [])
        past = historical.setdefault(pid, [])
        # Exact IDs only: suffixes are not proof that two findings are the same.
        for row in rows:
            if row['finding_id'] not in ids and row not in past:
                past.append(deepcopy(row))
        value.setdefault('author_responses', {})[pid] = [r for r in rows if r['finding_id'] in ids]
    value['response_scope'] = {
        'author_responses': 'Answers to the exact current findings_to_confirm IDs; not independent closure.',
        'historical_author_responses': 'Prior author statements, not current assignments or proof of review. '
            'Revisit when relevant to the current change or a newly found issue.'}
    return value


def confirmation_context(artifacts, revisions, feedback, *, artifact_history=(), confirmation_history=()):
    current = artifacts.with_revisions(revisions)
    changes = {}
    for pid in feedback:
        row = revisions.get(pid, {})
        observed = row.get('runtime_changes', {})
        # Native author output binds the immediate before/after versions.
        # Older saved revisions without that record retain the original diff.
        changes[pid] = (deepcopy(observed) if observed.get('current_digest') ==
            canonical_sha256(current.read_paper(pid)) else
            workpaper_changes(artifacts.read_paper(pid), current.read_paper(pid)))
        change = changes[pid]
        change.setdefault('comparison_basis', 'recorded_before_after_versions')
        if observed.get('current_digest') != canonical_sha256(current.read_paper(pid)):
            change['comparison_basis'] = 'original_paper_fallback_not_last_revision'
        if 'claim_changes' not in change:
            # Older observations have hashes but no field diff. Recover only
            # the exact recorded baseline, never the original paper by guess.
            candidates = [artifacts.read_paper(pid)] + [r.get('output', {}).get('workpaper')
                for r in artifact_history if r.get('output', {}).get('paper_id') == pid]
            baseline = next((p for p in candidates if p and canonical_sha256(p) == change['baseline_digest']), None)
            if baseline is not None:
                change['claim_changes'] = claim_changes(baseline, current.read_paper(pid))
            else:
                change['claim_change_detail_status'] = 'exact_baseline_unavailable'
        change['position_unit'] = 'unicode_characters_zero_based_half_open'
    history = []
    for record in confirmation_history:
        context = record.get('context', {})
        if not set(feedback).intersection(context.get('findings_to_confirm', {})):
            continue
        review = record.get('review', {})
        history.append({'correction_round': record.get('correction_round'),
            'paper_version_digests': deepcopy(context.get('paper_version_digests', {})),
            'assigned_findings': {pid: deepcopy(context['findings_to_confirm'][pid])
                for pid in feedback if pid in context['findings_to_confirm']},
            'phase': review.get('phase'),
            'roles': {role: {'status': review.get(role, {}).get('status'),
                'review': deepcopy(review.get(role, {}).get('review'))} for role in ('verifier', 'counter')},
            'notice': 'Recorded reviewer judgments for these historical versions; not acceptance of the current revision.'})
    return partition_author_responses({"paper_version_digests": paper_versions(current), "findings_to_confirm": deepcopy(feedback),
        "changes": changes,
        "author_responses": {pid: deepcopy(revisions.get(pid, {}).get("finding_responses", [])) for pid in feedback},
        'historical_reviews': history,
        "instruction": "Independently check each assigned finding against current workpaper and original sources. Each change identifies its comparison versions; an original-paper fallback is not the last revision. History is reference, not a cumulative whole-case re-review assignment. All other papers remain readable when relevant; their omission here does not mean their review passed. Author responses are claims, not closure. Inspect changed text, citation bindings and consequential related explanations; reuse unchanged research. Record newly introduced issues together. Necessary unchecked dependencies mean incomplete. Do not infer absence from a failed or incomplete read."})
