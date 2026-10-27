"""Source-bound inline XBRL periods and HTML cell geometry.

Replay the legacy visible-text projection exactly. Do not infer fiscal periods
from filing dates, merge contexts, or turn displayed numbers into NumericFacts.
Only an offline producer receives archived bytes; runtime consumes a publication
bound overlay and verifies its coordinates against the unchanged source text.
"""
from hashlib import sha256
import re

FORMAT = 'source-table-periods.v1'
MARKER = '[TABLE: original cell order; merged cells require original view]'


def digest(value):
    return sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def _local(tag):
    return tag.name.split(':')[-1].lower()


def _contexts(soup):
    result = {}
    for context in soup.find_all(lambda t: _local(t) == 'context'):
        identifier = context.get('id')
        if not identifier or identifier in result:
            raise ValueError('source_context_identity_invalid')
        period = context.find(lambda t: _local(t) == 'period')
        entity = context.find(lambda t: _local(t) == 'identifier')
        dates = {}
        if period:
            for kind in ('instant', 'startdate', 'enddate'):
                values = period.find_all(lambda t: _local(t) == kind)
                if len(values) == 1:
                    dates[kind] = values[0].get_text(strip=True)
        from datetime import date
        valid = set(dates) in ({'instant'}, {'startdate', 'enddate'})
        try:
            for value in dates.values():
                date.fromisoformat(value)
            if 'startdate' in dates and dates['startdate'] > dates['enddate']:
                valid = False
        except ValueError:
            valid = False
        if not entity or not valid:
            result[identifier] = {'status':'unresolved_context'}
            continue
        dimensions = [{'dimension': t.get('dimension'), 'value':t.get_text(' ',strip=True)}
                      for t in context.find_all(lambda t: _local(t) in {'explicitmember','typedmember'})]
        result[identifier] = {'status':'explicit_xbrl_period', 'dates':dates,
            'entity':entity.get_text(strip=True), 'entity_scheme':entity.get('scheme'),
            'dimensions':dimensions}
    return result


def _grid(table):
    """Keep DOM coordinates and spans; no ordinal zip of nonempty cells."""
    occupied, cells = {}, []
    rows = [r for r in table.find_all('tr') if r.find_parent('table') is table]
    if len(rows) > 10000:
        raise ValueError('source_table_geometry_exceeds_limit')
    for y, row in enumerate(rows):
        x = 0
        for ordinal, cell in enumerate(row.find_all(['td','th'],recursive=False)):
            while (y,x) in occupied:
                x += 1
            try:
                height, width = int(cell.get('rowspan',1)), int(cell.get('colspan',1))
            except ValueError:
                raise ValueError('source_table_span_invalid') from None
            if not 1 <= height <= 1000 or not 1 <= width <= 1000 or y+height>len(rows) or x+width>1000:
                raise ValueError('source_table_span_invalid')
            if len(occupied)+height*width>200000:
                raise ValueError('source_table_geometry_exceeds_limit')
            for yy in range(y,y+height):
                for xx in range(x,x+width):
                    if (yy,xx) in occupied:
                        raise ValueError('source_table_span_overlap')
                    occupied[yy,xx] = len(cells)
            cells.append((cell, {'row':y,'column':x,'rowspan':height,'colspan':width,'cell_ordinal':ordinal}))
            x += width
    return cells


def build_overlay(raw, *, raw_sha256, source_digest):
    """Produce an overlay only if the full historical projection replays.

    ContextRef associates a displayed cell value with its actual instant or
    duration. It does not establish the user's target company, measure, or FY.
    Non-XBRL cells remain unresolved even when a nearby year looks plausible.
    """
    if digest(raw) != raw_sha256:
        raise ValueError('source_raw_digest_mismatch')
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw, 'html.parser')
    contexts = _contexts(soup)
    for tag in list(soup.find_all('ix:header')):
        tag.decompose()
    for tag in soup(['script','style','noscript']):
        tag.decompose()
    candidates = []
    nested_skipped = 0
    # Nested presentation tables are replayed below but not given cell bindings.
    for ordinal, table in enumerate(soup.find_all('table')):
        if table.find('table') or table.find_parent('table'):
            nested_skipped += 1
            continue
        try:
            grid = _grid(table)
            geometry_error = None
        except ValueError as error:
            geometry_error = str(error)
            # ContextRef is independent of visual layout. Keep original DOM
            # row/cell order and explicit contexts, but do not invent columns.
            grid = [(cell, {'row':y,'column':None,'rowspan':None,'colspan':None,'cell_ordinal':i})
                for y,row in enumerate(table.find_all('tr'))
                for i,cell in enumerate(row.find_all(['td','th'],recursive=False))]
        cells = []
        for cell, position in grid:
            facts = []
            for fact in cell.find_all(['ix:nonfraction','ix:fraction']):
                context = contexts.get(fact.get('contextref'), {'status':'missing_context'})
                facts.append({'text':fact.get_text(' ',strip=True),'concept':fact.get('name'),
                    'context_ref':fact.get('contextref'), 'unit_ref':fact.get('unitref'),
                    'scale':fact.get('scale'), 'sign':fact.get('sign'), 'format':fact.get('format'),
                    'decimals':fact.get('decimals'), 'period':context})
            cells.append({**position, 'text':cell.get_text(' ',strip=True),'facts':facts,
                'geometry_status':geometry_error or 'original_geometry_verified'})
        candidates.append((table,ordinal,cells,geometry_error))
    # Byte-for-byte compatibility with the old fallback; never replace old text.
    for tag in list(soup.find_all(lambda t:t.name.startswith('ix:'))):
        tag.unwrap()
    metadata = {id(table):(ordinal,cells,error) for table,ordinal,cells,error in candidates}
    replayed = []
    for table in reversed(soup.find_all('table')):
        lines = []
        for row in table.find_all('tr'):
            cells = row.find_all(['td','th'],recursive=False)
            if cells:
                lines.append(' | '.join(c.get_text(' ',strip=True) for c in cells))
        if lines:
            rendered = MARKER+'\n'+'\n'.join(lines)+'\n[/TABLE]'
            if id(table) in metadata:
                ordinal,cells,error = metadata[id(table)]
                replayed.append((ordinal,rendered,cells,error))
            table.replace_with('\n'+rendered+'\n')
    text = soup.get_text('\n',strip=True)
    if digest(text) != source_digest:
        raise ValueError('source_legacy_projection_mismatch')
    output, cursor = [], 0
    for ordinal, rendered, cells, error in sorted(replayed):
        start = text.find(rendered,cursor)
        if start < 0:
            raise ValueError('source_table_projection_mismatch')
        end = start+len(rendered); cursor=end
        positions = {}
        offset = start+len(MARKER)+1
        for row_number,line in enumerate(rendered.splitlines()[1:-1]):
            cell_offset = offset
            for cell_number,part in enumerate(line.split(' | ')):
                positions[row_number,cell_number] = (cell_offset, cell_offset+len(part))
                cell_offset += len(part)+3
            offset += len(line)+1
        verified = []
        for cell in cells:
            lo,hi = positions.get((cell['row'],cell['cell_ordinal']),(-1,-1))
            if lo < 0 or text[lo:hi] != cell['text']:
                error = 'cell_text_or_delimiter_ambiguous'; verified=[]; break
            verified.append({**cell,'source_char_start':lo,'source_char_end':hi})
        output.append({'source_char_start':start,'source_char_end':end,'content_sha256':digest(rendered),
            'html_table_ordinal':ordinal,'status':error or 'original_geometry_verified', 'cells':verified})
    return {'format':FORMAT,'raw_sha256':raw_sha256,'source_digest':source_digest,'tables':output,
        'nested_tables_without_bindings':nested_skipped,
        'scope':'original_geometry_and_explicit_contextref_only_not_numeric_fact_authority'}


def validate_overlay(bundle):
    overlay = bundle.get('table_period_context')
    if overlay is None:
        return []
    text = bundle.get('text','')
    if (overlay.get('format') != FORMAT or overlay.get('source_digest') != digest(text)
            or not re.fullmatch('[0-9a-f]{64}',overlay.get('raw_sha256',''))):
        raise ValueError('table_period_overlay_source_mismatch')
    previous = 0
    for table in overlay['tables']:
        a,b = table['source_char_start'],table['source_char_end']
        if not previous<=a<b<=len(text) or digest(text[a:b])!=table['content_sha256']:
            raise ValueError('table_period_overlay_table_mismatch')
        previous=b
        for cell in table['cells']:
            lo,hi = cell['source_char_start'],cell['source_char_end']
            if not a<=lo<=hi<=b or text[lo:hi]!=cell['text']:
                raise ValueError('table_period_overlay_cell_mismatch')
    return overlay['tables']


def enrich_from_catalog(bundle):
    """Optional server-pinned producer catalog, never a request-supplied path.

    A new capture/publication binds the enrichment. Old saved versions remain
    unchanged. Missing catalog entries retain explicit unresolved table status.
    """
    import json
    import os
    from pathlib import Path
    path = os.environ.get('FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG')
    expected = os.environ.get('FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG_SHA256')
    if not path and not expected:
        return bundle
    if not path or not expected:
        raise ValueError('table_period_catalog_configuration_incomplete')
    path = Path(path).resolve()
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise ValueError('table_period_catalog_digest_mismatch')
    catalog = json.loads(raw)
    if (catalog.get('format') != 'source-table-period-catalog.v1'
            or catalog.get('library_sha256') != bundle['library_sha256']):
        raise ValueError('table_period_catalog_library_mismatch')
    entry = catalog['sources'].get(bundle['source']['id'])
    if entry is None:
        return bundle
    target = (path.parent/entry['file']).resolve()
    if not target.is_relative_to(path.parent) or target == path:
        raise ValueError('table_period_catalog_path_invalid')
    payload = target.read_bytes()
    if digest(payload) != entry['sha256'] or entry['source_digest'] != bundle['source']['digest']:
        raise ValueError('table_period_catalog_source_mismatch')
    result = {**bundle, 'table_period_context':json.loads(payload)}
    validate_overlay(result)
    return result
