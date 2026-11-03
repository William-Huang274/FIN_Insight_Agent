"""Issue a host-signed recovery permit after explicit user approval; no dispatch."""
import argparse
import json
import os

from apps.workbench.backend.api.v1.report_sessions import public_run_usage
from sec_agent.adapters.explicit_run_recovery import issue_recovery_authorization


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('audit-root', 'thread-id', 'run-id', 'authorization-id', 'authorization-ref'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    events, usage = public_run_usage(a.audit_root, a.thread_id, a.run_id)
    value = issue_recovery_authorization(a.audit_root, a.thread_id, a.run_id, events, usage,
        secret=os.environ['FINSIGHT_ORGANIZATION_RUNTIME_SECRET'],
        authorization_id=a.authorization_id, authorization_ref=a.authorization_ref)
    print(json.dumps({k: value[k] for k in ('authorization_id', 'thread_id', 'previous_run_id',
                                          'unknown_call_ids', 'expires_at')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
