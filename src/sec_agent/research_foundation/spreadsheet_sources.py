"""Read public XLSX originals with openpyxl; never evaluate formulas or links."""
from datetime import date, datetime
from io import BytesIO
import json
from zipfile import ZipFile


XLSX_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def spreadsheet_publication_day(text):
    """Explicit edition title in a sheet masthead, never forecast columns/metadata."""
    import re
    from .publication_metadata import explicit_day
    days, row_count = [], 0
    for line in text.splitlines():
        if line.startswith('Sheet: '):
            row_count = 0
            continue
        row_count += 1
        if row_count > 5:
            continue
        match = re.fullmatch(r'[A-Z]+\d+: (".*") \[format=[^\n]*\]', line)
        if not match:
            continue
        try:
            value = json.loads(match[1])
        except ValueError:
            continue
        stamp = re.fullmatch(r'[^\n]{0,80}\bconsensus\s*[-–—:]\s*(.{8,40})', value, re.I)
        if stamp:
            day = explicit_day(stamp[1])
            if day:
                days.append(day)
    return max(days, default=None)


def spreadsheet_text(body, *, maximum_characters=2_000_000):
    from openpyxl import load_workbook
    from .external_sources import ExternalSourceError
    try:
        with ZipFile(BytesIO(body)) as z:
            entries = z.infolist()
            if (len(entries) > 2000 or sum(i.file_size for i in entries) > 50_000_000
                    or '[Content_Types].xml' not in z.namelist()):
                raise ExternalSourceError('capture_spreadsheet_archive_limits')
        formulas = load_workbook(BytesIO(body), read_only=True, data_only=False, keep_links=False)
        cached = load_workbook(BytesIO(body), read_only=True, data_only=True, keep_links=False)
        parts = ['Spreadsheet original. Cell addresses and number formats retained. Formulas are not executed; cached results may be absent or stale.']
        size, cells = len(parts[0]), 0
        try:
            if len(formulas.worksheets) > 100:
                raise ExternalSourceError('capture_spreadsheet_sheet_limit')
            for sheet in formulas:
                if (sheet.max_row or 0) * (sheet.max_column or 0) > 200_000:
                    raise ExternalSourceError('capture_spreadsheet_cell_limit')
                parts.append('Sheet: ' + sheet.title + ' [state=' + sheet.sheet_state + ']')
                for row, saved in zip(sheet.iter_rows(), cached[sheet.title].iter_rows()):
                    values = []
                    for cell, stored in zip(row, saved):
                        cells += 1
                        if cells > 200_000:
                            raise ExternalSourceError('capture_spreadsheet_cell_limit')
                        if cell.value is None:
                            continue
                        value = cell.value
                        if isinstance(value, (date, datetime)):
                            value = value.isoformat()
                        if cell.data_type == 'f':
                            value = {'formula': value, 'cached_result': stored.value,
                                     'execution': 'not_evaluated'}
                        rendered = json.dumps(value, ensure_ascii=False, default=str)
                        values.append(f'{cell.coordinate}: {rendered} [format={cell.number_format}]')
                    if values:
                        line = ' | '.join(values)
                        size += len(line)
                        if size > maximum_characters:
                            raise ExternalSourceError('capture_spreadsheet_text_too_large')
                        parts.append(line)
            return '\n'.join(parts)
        finally:
            formulas.close()
            cached.close()
    except ExternalSourceError:
        raise
    except Exception as exc:
        raise ExternalSourceError('capture_spreadsheet_unreadable') from exc
