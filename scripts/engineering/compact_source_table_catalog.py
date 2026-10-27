"""Create a lossless compact catalog; retain every input artifact unchanged."""
import argparse
import json
from pathlib import Path
from retrieval.source_table_periods import digest
from retrieval.source_table_storage import pack, unpack, FORMAT


def compact_catalog(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    raw = source.read_bytes()
    catalog = json.loads(raw)
    if catalog.get('format') != 'source-table-period-catalog.v1':
        raise ValueError('compact_catalog_requires_original_catalog')
    destination.mkdir(parents=True, exist_ok=False)
    result = {'format':'source-table-period-catalog.v2',
              'library_sha256':catalog['library_sha256'], 'sources':{}}
    audit = {'source_catalog_sha256':digest(raw), 'originals_unchanged':True,
             'sources':[], 'provider_calls':0}
    for source_id, entry in catalog['sources'].items():
        path = (source.parent/entry['file']).resolve()
        if not path.is_relative_to(source.parent) or path == source:
            raise ValueError('compact_catalog_path_invalid')
        original = path.read_bytes()
        if digest(original) != entry['sha256']:
            raise ValueError('compact_catalog_original_changed')
        overlay = json.loads(original)
        packed = pack(overlay, original_bytes=original)
        # Preserve exact bytes, including JSON whitespace, for independent
        # recovery of the original catalog artifacts.
        if packed['sha256'] != entry['sha256'] or unpack(packed) != overlay:
            raise ValueError('compact_catalog_roundtrip_mismatch')
        payload = json.dumps(packed, ensure_ascii=False, separators=(',', ':')).encode()
        name = digest(source_id)+'.json'
        target = destination/name
        target.write_bytes(payload)
        if unpack(json.loads(target.read_bytes())) != overlay:
            raise ValueError('compact_catalog_saved_roundtrip_mismatch')
        result['sources'][source_id] = {**entry, 'file':name, 'sha256':digest(payload),
            'encoding':FORMAT, 'original_file_sha256':entry['sha256']}
        audit['sources'].append({'source_id':source_id, 'input':str(path),
            'original_sha256':entry['sha256'], 'output':name, 'output_sha256':digest(payload),
            'original_bytes':len(original), 'stored_bytes':len(payload)})
    if source.read_bytes() != raw:
        raise ValueError('compact_catalog_input_changed')
    encoded = json.dumps(result, ensure_ascii=False, indent=2).encode()
    (destination/'catalog.json').write_bytes(encoded)
    audit.update(status='completed', catalog_sha256=digest(encoded))
    (destination/'compaction-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2),encoding='utf8')
    return audit


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--catalog',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=compact_catalog(args.catalog,args.output)
    print(json.dumps({'status':result['status'],'sources':len(result['sources']),
        'original_bytes':sum(r['original_bytes'] for r in result['sources']),
        'stored_bytes':sum(r['stored_bytes'] for r in result['sources']),
        'catalog_sha256':result['catalog_sha256'],'provider_calls':0}))
