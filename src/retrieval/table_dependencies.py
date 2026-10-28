"""Original-coordinate table dependencies, not inferred financial facts.

Keep explicit header bands and marked row notes. Ambiguous geometry abstains;
file years, neighboring tables and unmarked prose never supply missing units.
"""
from collections import defaultdict
from hashlib import sha256
import re

POLICY = 'original-table-dependencies.v1'
NUMBER = re.compile(r'^[\s$€£¥()+−\-\d,.%]+$')
UNIT = re.compile(r'\b(?:in (?:thousands|millions|billions)|per (?:common )?share|percent|dollars|USD|EUR|GBP)\b|单位|千元|百万元|亿元', re.I)
MARKER = re.compile(r'\(([a-z]|\d{1,3})\)', re.I)


def _span(text, start, end, role):
    return {'role': role, 'source_char_start': start, 'source_char_end': end,
            'content_sha256': sha256(text[start:end].encode()).hexdigest()}


def dependencies(text, tables):
    """Return row spans with exact dependencies; no query/label access."""
    output = []
    for index, table in enumerate(tables):
        if table.get('status') != 'original_geometry_verified':
            continue
        groups = defaultdict(list)
        for cell in table['cells']:
            groups[cell['row']].append(cell)
        data = []
        for number, cells in groups.items():
            nonempty = [c for c in cells if c['text'].strip()]
            if not nonempty:
                continue
            label = nonempty[0]['text'].strip()
            if (re.search(r'[A-Za-z\u3400-\u9fff]', label)
                    and not NUMBER.fullmatch(label)
                    and any(NUMBER.fullmatch(c['text'].strip())
                            and re.search(r'\d', c['text'])
                            and not re.fullmatch(r'(?:19|20)\d{2}', c['text'].strip())
                            for c in nonempty[1:])):
                data.append(number)
        if not data:
            continue
        header = [c for c in table['cells'] if c['row'] < min(data) and c['text'].strip()]
        repeated = [r for r, values in groups.items() if r > min(data)
            and sum(bool(re.fullmatch(r'(?:19|20)\d{2}',c['text'].strip())) for c in values)>=2]
        # Header bands retain all columns (including merged headings). This
        # is context, not a fabricated numeric-to-year assignment.
        context = []
        from .table_captions import is_unit_caption
        prefix=text[:table['source_char_start']].rstrip()
        caption=prefix.rsplit('\n',1)[-1] if prefix else ''
        if is_unit_caption(caption):
            start=len(prefix)-len(caption)
            context.append(_span(text,start,len(prefix),'unit_statement'))
        if header:
            context.append(_span(text, min(c['source_char_start'] for c in header),
                                 max(c['source_char_end'] for c in header), 'header_band'))
        for c in header:
            if UNIT.search(c['text']):
                context.append(_span(text, c['source_char_start'], c['source_char_end'], 'unit_statement'))
        notes = {}
        previous = table['source_char_end']
        # An explicit referenced marker in a contiguous plain-text note has
        # the same ownership as a one-row HTML note. Stop at any other prose,
        # heading or table; do not search ahead for a convenient matching note.
        while (note := re.match(r'\s*\(([a-z]|\d{1,3})\)[ \t]+[^\n]+',text[previous:],re.I)):
            lo=previous+len(note[0])-len(note[0].lstrip())
            hi=previous+note.end()
            notes.setdefault(note[1].lower(),[]).append(_span(text,lo,hi,'marked_footnote'))
            previous=hi
        for following in tables[index+1:]:
            if text[previous:following['source_char_start']].strip():
                break
            nonempty = [c for c in following['cells'] if c['text'].strip()]
            if (following.get('status') != 'original_geometry_verified' or not nonempty
                    or len({c['row'] for c in nonempty}) != 1):
                break
            match = MARKER.fullmatch(nonempty[0]['text'].strip())
            if not match or len(nonempty) < 2:
                break
            marker = match[1].lower()
            # Duplicate markers are ambiguous; never choose one silently.
            notes.setdefault(marker, []).append(_span(text, following['source_char_start'],
                                                      following['source_char_end'], 'marked_footnote'))
            previous = following['source_char_end']
        identity = {key:table[key] for key in ('source_char_start','source_char_end','content_sha256')}
        for number in data:
            cells = [c for c in groups[number] if c['text'].strip()]
            start, end = min(c['source_char_start'] for c in cells), max(c['source_char_end'] for c in cells)
            required = list(context)
            # Include the exact row label if chunking split it from the value.
            required.append(_span(text,cells[0]['source_char_start'],cells[0]['source_char_end'],'row_label'))
            # Accounting parentheses are signs, not numeric note references.
            markers = sorted(set(m.lower() for c in cells
                                 if not NUMBER.fullmatch(c['text'].strip())
                                 for m in MARKER.findall(c['text'])))
            unresolved = []
            if any(r < number for r in repeated):
                required = [s for s in required if s['role']=='row_label']
                unresolved.append('repeated_header_requires_column_binding')
            for marker in markers:
                if len(notes.get(marker, [])) == 1:
                    required.extend(notes[marker])
                else:
                    unresolved.append('marked_footnote:'+marker)
            if not header:
                unresolved.append('header_band')
            if not any(UNIT.search(c['text']) for c in [*header,*cells]) and not any(s['role']=='unit_statement' for s in required):
                unresolved.append('unit_not_explicitly_bound')
            output.append({'table':identity,'row_start':start,'row_end':end,
                'required':required,'unresolved':unresolved,
                'semantics':'structural_context_not_fact_period_or_unit_inference'})
    return output
