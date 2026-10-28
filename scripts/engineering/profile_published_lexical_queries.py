"""Read-only lexical component profile; no authorization or service capacity claim."""
import argparse
import cProfile
from hashlib import sha256
import json
from pathlib import Path
import pstats
from time import perf_counter

from retrieval.published_lexical_index import PublishedLexicalStatistics, scores_from_identities
from retrieval.text import tokenize


def run(directory, output):
    output.mkdir(parents=True, exist_ok=False)
    records = json.loads((directory / 'index.json').read_bytes())['records']
    identities = [(r['node_id'], r['content_sha256'], r['lexical_input_sha256']) for r in records]
    # Deliberately mechanical sizes, not gold-selected evidence or quality cases.
    queries = ['cash cash equivalents restricted cash', 'repurchase authorization remaining shares',
               'revenue operating income fiscal year']
    report = {'scope': 'component-only, ordered prefix subsets; no live authorization or providers',
              'sources_index': str(directory), 'population': len(identities), 'samples': []}
    for size in dict.fromkeys((300, 3000, 15000, len(identities))):
        selected = identities[:size]
        cache = PublishedLexicalStatistics()
        for ordinal, query in enumerate(queries):
            profile = cProfile.Profile()
            start = perf_counter()
            result = profile.runcall(scores_from_identities, directory / 'lexical.sqlite', selected,
                                     tokenize(query), population_cache=cache)
            seconds = perf_counter() - start
            scores, overlap, has_terms = result
            raw = json.dumps([scores.tolist(), sorted(overlap), bool(has_terms)], separators=(',', ':')).encode()
            stats = pstats.Stats(profile)
            top = sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)[:16]
            report['samples'].append({'size': len(selected), 'ordinal': ordinal, 'seconds': seconds,
                'statistics_hit': cache.hit, 'result_sha256': sha256(raw).hexdigest(),
                'profile': [{'function': str(key), 'calls': value[1], 'self_seconds': value[2],
                             'cumulative_seconds': value[3]} for key, value in top]})
            (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf8')
            print(json.dumps({k: v for k, v in report['samples'][-1].items() if k != 'profile'}), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.directory, args.output)
