"""Retire successful disposable test stacks; retain diagnostics and pinned fixtures."""
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timedelta, timezone


def finish(stack, *, failed=None):
    """Only called at final teardown, never at an in-test restart boundary."""
    failed = sys.exc_info()[0] is not None if failed is None else failed
    if not re.fullmatch(r'fin-intake-native-[a-f0-9]{12}', stack.project):
        raise ValueError('refuse_foreign_qualification_project')
    reason = os.getenv('FIN_NATIVE_RETAIN_REASON', '').strip()
    adopted = stack.project != getattr(stack, 'owned_project', None)
    sealed = any(p.is_file() for p in (stack.output/'retention-pin.json',
                                      stack.output/'retained-publication.json'))
    # Paid work must not lose its budget/unknown-usage database on test success.
    paid = bool(getattr(stack, 'preserve_model_storage', False))
    if not getattr(stack, 'deterministic_model_fixture', False):
        paid = paid or any(p.stat().st_size for p in (stack.state/'calls').rglob('model-call-events.jsonl'))
    retain = failed or adopted or sealed or paid or bool(reason)
    now = datetime.now(timezone.utc)
    record = dict(schema='qualification-retention.v1', project=stack.project,
                  policy='retain' if retain else 'retire', failed=bool(failed),
                  reason=reason or ('adopted_fixture' if adopted else 'pinned_fixture' if sealed
                                   else 'model_usage_evidence' if paid else 'failure' if failed else 'successful_disposable_test'),
                  recorded_at=now.isoformat(), review_after=(now+timedelta(days=7)).isoformat() if retain else None,
                  evidence_directory=str(stack.output), status='planned', removed_copies=[])
    stack.save('resource-retention', record)
    if retain:
        stack.compose('stop', '-t', '5')
        record['status'] = 'retained_stopped'
    else:
        # Compose scopes deletion to this randomly allocated owned project.
        # Do not prune global caches, other projects, images or bind mounts.
        stack.compose('down', '--volumes', '--remove-orphans', '--timeout', '5')
        for value in getattr(stack, 'disposable_copies', []):
            path = Path(value)
            root = stack.output.resolve()
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError('disposable_copy_outside_attempt')
            cursor = path.parent
            while cursor != root:
                if cursor.is_symlink():
                    raise ValueError('disposable_copy_symlink')
                cursor = cursor.parent
            if path.exists():
                path.unlink()
                record['removed_copies'].append(str(path.relative_to(root)))
        record['status'] = 'retired'
    stack.save('resource-retention', record)
    return record
