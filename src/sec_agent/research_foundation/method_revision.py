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
from .method_execution import Contract, MethodWorkResult


class FieldRevision(Contract):
    path: str = Field(min_length=1, description='Exact field path authorized by runtime.')
    value: Any = Field(description='Complete replacement value of this field only, not the entire workpaper.')
    reason: str = Field(min_length=1, description='Brief public evidence-based reason for changing this field.')


class MethodRevision(Contract):
    changes: list[FieldRevision] = Field(max_length=32)
    review_note: str = Field(min_length=1, description='Explain retained judgments and any remaining uncertainty. Do not invent changes.')


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
