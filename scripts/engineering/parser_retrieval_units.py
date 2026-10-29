"""Query-independent structured parser units for an isolated ablation.

These are derived coordinates, not replacements for original citation IDs.
Whole tables or row groups retain declared headers/captions and bounded,
explicitly unassigned adjacent source context. This does not infer ownership.
"""
from hashlib import sha256
import json


def split_text(text, limit=6000):
    """Return exhaustive original slices, never cut inside a word."""
    start = 0
    while start < len(text):
        end = min(len(text), start + limit)
        if end < len(text) and not text[end].isspace() and not text[end - 1].isspace():
            boundary = next((i for i in range(end, start, -1) if text[i - 1].isspace()), None)
            if boundary is None:
                boundary = next((i for i in range(end, len(text)) if text[i].isspace()), len(text))
            end = boundary
        yield start, end, text[start:end]
        start = end


def build_units(parsed, sample):
    if parsed['raw_sha256'] != sample['raw_sha256'] or parsed['status'] != 'parsed':
        raise ValueError('parsed_source_identity_mismatch')
    blocks = parsed['output']['blocks']
    units, pending, context = [], [], ''

    def emit(body, refs, kind, inherited='', own_headers=''):
        if not body.strip():
            return
        # Preserve layout elements in the parser ledger, not as evidence
        # vectors. Zero, dashes and non-Latin text are deliberately retained;
        # a dash may be an actual reported cell value, not layout whitespace.
        if kind == 'table' and not any(not c.isspace() and c != '|' for c in body):
            return
        identifier = sha256(json.dumps([sample['raw_sha256'], refs, body, inherited],
                                      ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        text = '\n'.join(x for x in [sample['title'], inherited, body] if x)
        if len(text.encode()) > 16384:
            raise ValueError('structure_requires_smaller_complete_row_group:' + identifier)
        units.append({'id': 'PARSED::' + identifier, 'document_id': sample['document_id'],
                      'source_sha256': sample['raw_sha256'], 'url': sample['url'],
                      'kind': kind, 'body': body, 'context': inherited,
                      # Only this table's parser-declared headers contribute
                      # lexical terms. Adjacent prose and document titles do not.
                      'lexical_input': '\n'.join(x for x in [own_headers, body] if x),
                      'embedding_input': text, 'input_sha256': sha256(text.encode()).hexdigest(),
                      'derived_references': refs, 'financial_semantics_inferred': False})

    def flush():
        if pending:
            emit('\n'.join(x[1] for x in pending), [x[0] for x in pending], 'prose', context)
            pending.clear()

    for number, block in enumerate(blocks):
        text = block['text']
        if not text.strip():
            continue
        if block['kind'] == 'heading':
            flush()
            context = text.strip()
            # The heading remains retrievable on its own score, not promoted.
            emit(text, [{'block': number, 'start': 0, 'end': len(text)}], 'heading')
        elif block['kind'] == 'table':
            # A separately parsed issuer heading must survive alongside the
            # caption. These are adjacent source blocks, not inferred facts.
            preceding = []
            context_omission = None
            for prior_number in range(number - 1, -1, -1):
                prior = blocks[prior_number]
                if prior['kind'] not in {'heading', 'text'}:
                    break
                if not prior['text'].strip():
                    continue
                if sum(len(v[1].encode()) for v in preceding) + len(prior['text'].encode()) > 6000:
                    context_omission = {'block': prior_number, 'reason': 'complete_adjacent_block_exceeds_context_budget'}
                    break
                preceding.append((prior_number, prior['text'].strip()))
                if len(preceding) == 8:
                    break
            preceding.reverse()
            table_context = '\n'.join(v[1] for v in preceding)
            caption_refs = [{'block': v[0], 'role': 'adjacent_source_context_not_inferred_fact'} for v in preceding]
            flush()
            headers = block.get('headers', [])
            rows = block.get('rows', []) + block.get('footer', [])
            head = '\n'.join(' | '.join(c['text'] for c in r) for r in headers)
            inherited = '\n'.join(x for x in [table_context, block.get('caption'), head] if x)
            group, start = [], 0
            for row_number, row in enumerate(rows):
                line = ' | '.join(c['text'] for c in row)
                if group and len(('\n'.join(group + [line]) + inherited).encode()) > 10000:
                    emit('\n'.join(group), [{'block': number, 'row_start': start,
                         'row_end': row_number, 'headers': bool(headers), 'caption_refs': caption_refs,
                         'context_omission': context_omission}], 'table', inherited, head)
                    group, start = [], row_number
                group.append(line)
            if group:
                emit('\n'.join(group), [{'block': number, 'row_start': start,
                     'row_end': len(rows), 'headers': bool(headers), 'caption_refs': caption_refs,
                     'context_omission': context_omission}], 'table', inherited, head)
            elif head.strip():
                emit(head, [{'block': number, 'header_only': True}], 'table', context)
        else:
            for a, b, part in split_text(text):
                if pending and len(('\n'.join(x[1] for x in pending) + part + context).encode()) > 10000:
                    flush()
                pending.append(({'block': number, 'start': a, 'end': b}, part))
    flush()
    return units
