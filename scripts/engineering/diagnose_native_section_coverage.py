"""Account for every unbound native section without promoting parser guesses."""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path


def diagnose(directory):
    summary=json.loads((directory/'summary.json').read_bytes())
    rows=[]; totals=Counter()
    for row in summary['rows']:
        if row['route']!='edgartools' or 'receipt' not in row:continue
        capture=Path(row['capture_directory']); receipt=json.loads((capture/'receipt.json').read_bytes())
        raw=(capture/'native.json.gz').read_bytes()
        output=(directory/'adapted'/row['source_sha256']/'document.json.gz').read_bytes()
        if sha256(raw).hexdigest()!=receipt['native_sha256'] or sha256(output).hexdigest()!=row['receipt']['artifact_sha256']:
            raise ValueError('diagnostic_input_changed')
        native=json.loads(gzip.decompress(raw))['native']; doc=json.loads(gzip.decompress(output))
        used={k for b in doc['blocks'] if len(b.get('native_section_binding',{}).get('candidates',[]))==1
              for k in b['native_section_binding']['candidates']}
        totals['originals']+=1
        totals['heading_table_boundary_adjustments']+=len(doc.get('native_boundary_adjustments',[]))
        for key, section in native['sections'].items():
            totals['native_sections']+=1
            if key in used:totals['sections_with_bound_blocks']+=1;continue
            text=' '.join(section['native_text'].split())
            reason=('native_text_is_navigation_label' if text.casefold()=='table of contents'
                    else 'native_text_empty' if not text else 'no_unique_complete_block_binding')
            totals[reason]+=1
            rows.append(dict(original_id=row['source_sha256'],title=row['title'],section=key,
                             detection_method=section['fields']['detection_method'],
                             native_text_excerpt=text[:600],native_text_sha256=sha256(section['native_text'].encode()).hexdigest(),
                             boundary=native.get('toc_boundaries',{}).get(key),reason=reason,
                             action='review_original_and_upstream_boundary_do_not_force_assignment'))
    return dict(counts=dict(totals),unbound_sections=rows,quality_pass=False,provider_calls=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=diagnose(a.directory)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['counts']))
