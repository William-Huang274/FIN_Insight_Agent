"""Bounded lossless storage for original table geometry, never new evidence."""
import base64
from hashlib import sha256
import json
import zlib

FORMAT = 'source-table-period-storage.v1'
MAX_BYTES = 128 * 1024 * 1024


def pack(overlay, *, original_bytes=None):
    if not isinstance(overlay, dict) or overlay.get('format') != 'source-table-periods.v1':
        raise ValueError('source_table_storage_overlay_invalid')
    raw = (json.dumps(overlay, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
           if original_bytes is None else original_bytes)
    if not isinstance(raw, bytes):
        raise ValueError('source_table_storage_original_bytes_invalid')
    if len(raw) > MAX_BYTES:
        raise ValueError('source_table_storage_size_limit')
    if original_bytes is not None and json.loads(raw) != overlay:
        raise ValueError('source_table_storage_original_bytes_mismatch')
    return {'format': FORMAT, 'encoding': 'zlib+base64', 'bytes': len(raw),
            'sha256': sha256(raw).hexdigest(),
            'payload': base64.b64encode(zlib.compress(raw)).decode('ascii')}


def unpack(value):
    if (not isinstance(value, dict) or set(value) != {'format','encoding','bytes','sha256','payload'}
            or value.get('format') != FORMAT or value.get('encoding') != 'zlib+base64'
            or type(value.get('bytes')) is not int or not 0 < value['bytes'] <= MAX_BYTES
            or not isinstance(value.get('sha256'), str) or len(value['sha256']) != 64
            or not isinstance(value.get('payload'), str) or len(value['payload']) > MAX_BYTES*2):
        raise ValueError('source_table_storage_contract_invalid')
    try:
        compressed = base64.b64decode(value['payload'], validate=True)
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed, value['bytes'] + 1)
        if (len(raw) != value['bytes'] or not decoder.eof or decoder.unused_data
                or decoder.unconsumed_tail or sha256(raw).hexdigest() != value['sha256']):
            raise ValueError('source_table_storage_digest_or_size_mismatch')
        result = json.loads(raw)
    except (TypeError, UnicodeError, zlib.error, ValueError) as error:
        raise ValueError('source_table_storage_decode_failed') from error
    if not isinstance(result, dict) or result.get('format') != 'source-table-periods.v1':
        raise ValueError('source_table_storage_overlay_invalid')
    return result
