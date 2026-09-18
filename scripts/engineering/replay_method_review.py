"""Offline review-coverage replay of a saved method diagnostic state.

Never calls a model, changes a checkpoint, or supplies financial answer keys.
Original files are hashed and left untouched. Replays protocol coverage only.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from sec_agent.research_foundation.method_review import MethodReview, assess_method_review, review_targets


def replay(state_path, decision_path):
    state_bytes = state_path.read_bytes()
    decision_bytes = decision_path.read_bytes()
    state = json.loads(state_bytes)
    decision = json.loads(decision_bytes)
    results = state['results']
    receipt = assess_method_review(results, MethodReview.model_validate(decision.get('review', {})),
                                   state.get('review_state'))
    return {'kind': 'offline_review_contract_replay', 'provider_calls': 0,
            'input_digests': {'state': sha256(state_bytes).hexdigest(), 'decision': sha256(decision_bytes).hexdigest()},
            'old_terminal': state.get('terminal'), 'legacy_review_omitted': 'review' not in decision,
            'candidate_count': len(results), 'target_count': sum(len(review_targets(r)) for r in results),
            'candidates_without_cited_originals': [r['obligation']['obligation_id'] for r in results
                                                   if not r.get('review_evidence')],
            'receipt': receipt,
            'interpretation': 'Missing review is pending; this replay does not discover or repair financial errors.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--decision', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.state, args.decision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({k: result[k] for k in ('kind', 'provider_calls', 'candidate_count', 'target_count')}, ensure_ascii=False))
    print(json.dumps({'complete': result['receipt']['complete'],
                      'pending_targets': len(result['receipt']['pending_targets'])}))


if __name__ == '__main__':
    main()
