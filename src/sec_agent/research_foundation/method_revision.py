"""Version-bound, replace-only workpaper revisions using standard JSON Patch.

Separate from schema-error supplements: these edits may change research meaning.
The caller owns allowed fields and must run evidence/semantic checks afterwards.
"""
from copy import deepcopy
from typing import Any

import jsonpatch
import jsonpointer
from pydantic import Field

from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from sec_agent.agent_runtime.evidence_resolution import parsing_record
from .method_execution import Contract, MethodWorkResult


class FieldRevision(Contract):
    path: str = Field(min_length=1, description='Exact field path authorized by runtime.')
    value: Any = Field(description='Complete replacement value of this field only, not the entire workpaper.')
    reason: str = Field(min_length=1, description='Brief public evidence-based reason for changing this field.')


class MethodRevision(Contract):
    changes: list[FieldRevision] = Field(max_length=32)
    review_note: str = Field(min_length=1, description='Explain retained judgments and any remaining uncertainty. Do not invent changes.')


class TargetedFieldRevision(Contract):
    target_ref: str = Field(min_length=1, description='Select the runtime target_ref by owner_label, field and CURRENT field content; do not infer array indices or count findings. Empty reference lists belong to the owner shown in the menu.')
    value: Any = Field(description='Complete new value for this selected field only.')
    reason: str = Field(min_length=1)


class TargetedMethodRevision(Contract):
    changes: list[TargetedFieldRevision] = Field(max_length=32)
    review_note: str = Field(min_length=1)


def revision_targets(original: dict, allowed_paths: set[str]) -> dict:
    """A current-content menu, scoped to the exact workpaper version.

    Long identities and zero-based pointer selection stay runtime-owned.
    Content is supplied verbatim; no semantic target selection is inferred.
    """
    digest = canonical_sha256(original)
    targets = {}
    for path in sorted(allowed_paths):
        current = deepcopy(jsonpointer.resolve_pointer(original, path))
        parent_path, _, field = path.rpartition('/')
        parent = jsonpointer.resolve_pointer(original, parent_path)
        owner_label = 'workpaper'
        if isinstance(parent, dict):
            owner_label = parent.get('statement') or parent.get('step_id') or owner_label
        ref = 'R-' + canonical_sha256({'base_digest': digest, 'path': path})[:24]
        targets[ref] = {'path': path, 'current_value': current, 'base_digest': digest,
                        'field': field, 'owner_label': owner_label}
    return targets


def revise_targeted_workpaper(original: dict, original_digest: str,
                             revision: TargetedMethodRevision, allowed_paths: set[str]):
    if canonical_sha256(original) != original_digest:
        raise ValueError('stale_workpaper_revision')
    directory = revision_targets(original, allowed_paths)
    mapped = []
    records = []
    for change in revision.changes:
        if change.target_ref not in directory:
            raise ValueError('unknown_or_stale_revision_target')
        target = directory[change.target_ref]
        mapped.append(FieldRevision(path=target['path'], value=change.value, reason=change.reason))
        records.append(parsing_record('current_workpaper_revision_target_v1',
            {'target_ref': change.target_ref}, {'path': target['path'], 'base_digest': original_digest},
            target_value_digest=canonical_sha256(target['current_value']),
            financial_meaning_not_inferred=True))
    candidate, audit = revise_workpaper(original, original_digest,
        MethodRevision(changes=mapped, review_note=revision.review_note), allowed_paths)
    audit['runtime_parsing'] = records
    return candidate, audit


def revise_workpaper(original: dict, original_digest: str, revision: MethodRevision,
                     allowed_paths: set[str]):
    """Return a schema-valid candidate and actual diff; never mutate/accept input.

    A frozen caller-bound digest supplies identity; the model need not copy it.
    No add/remove, overlapping writes, identity edits or implicit retries.
    """
    if canonical_sha256(original) != original_digest:
        raise ValueError('stale_workpaper_revision')
    paths = [c.path for c in revision.changes]
    if len(paths) != len(set(paths)) or not set(paths) <= allowed_paths:
        raise ValueError('revision_requires_unique_authorized_fields')
    allowed_roots = {'summary', 'steps', 'findings', 'unresolved'}
    for path in paths:
        if (not path.startswith('/') or (path.split('/')[1] not in allowed_roots
                and path not in {'/task_note/blockers', '/task_note/next_action'})):
            raise ValueError('revision_cannot_change_identity_or_runtime_note')
        if any(other != path and other.startswith(path + '/') for other in paths):
            raise ValueError('overlapping_revision_fields')
    operations = []
    diff = []
    for change in revision.changes:
        before = jsonpointer.resolve_pointer(original, change.path)
        if before == change.value:
            continue
        operations.extend([{'op': 'test', 'path': change.path, 'value': deepcopy(before)},
                           {'op': 'replace', 'path': change.path, 'value': deepcopy(change.value)}])
        diff.append({'path': change.path, 'before': deepcopy(before),
                     'after': deepcopy(change.value), 'model_reason': change.reason})
    candidate = jsonpatch.JsonPatch(operations).apply(original, in_place=False)
    candidate['task_note']['changes'] = [*candidate['task_note']['changes'],
        *(f'Runtime recorded field revision: {row["path"]} (base {original_digest[:12]})' for row in diff)]
    parsed = MethodWorkResult.model_validate(candidate)
    return parsed, {'origin': 'runtime_workpaper_revision', 'base_digest': original_digest,
        'candidate_digest': canonical_sha256(parsed.model_dump(mode='json')),
        'changes': diff, 'review_note': revision.review_note,
        'schema_valid': True, 'accepted': False, 'requires_evidence_and_semantic_review': True}
