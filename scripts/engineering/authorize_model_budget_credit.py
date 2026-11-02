"""Append an explicitly approved credit to an existing envelope; no model I/O.

Use a provisioner connection, not the runtime worker. Apply migration 005 first.
The approval ID must identify one authorization, even when retrying this command.
"""
import argparse
import json
import os

from sec_agent.adapters.model_dispatch_store import ModelDispatchStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--budget', required=True)
    parser.add_argument('--currency', required=True)
    parser.add_argument('--amount-micros', required=True, type=int)
    parser.add_argument('--authorization-id', required=True)
    parser.add_argument('--authorization-ref', required=True)
    args = parser.parse_args()
    store = ModelDispatchStore(os.environ['FIN_MODEL_BUDGET_PROVISIONER_URI'])
    store.add_credit(args.owner, args.budget, args.authorization_id, args.currency,
                     args.amount_micros, args.authorization_ref)
    # Provisioner intentionally cannot read raw dispatches. Do not broaden its grants.
    print(json.dumps({'status': 'authorized', 'budget_id': args.budget,
                      'authorization_id': args.authorization_id,
                      'amount_micros': args.amount_micros, 'currency': args.currency}))


if __name__ == '__main__':
    main()
