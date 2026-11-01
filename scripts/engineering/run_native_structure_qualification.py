"""Expand frozen native adaptation checks serially, retaining all scope rows.

The input plan is a scope selection, never a quality gold set. Unsupported
routes stay in the denominator. Resume requires identical code and inputs.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import shutil

HERE = Path(__file__).resolve().parent


def run_child(command, log, timeout):
    """Keep a failed/timeout attempt visible; never retry implicitly."""
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=timeout)
        output = result.stdout + result.stderr
        status = result.returncode
    except subprocess.TimeoutExpired as exc:
        def decode(value):
            return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''
        output = decode(exc.stdout) + decode(exc.stderr) + '\nqualification_child_timeout\n'
        status = 124
    log.write_text(output, encoding='utf-8')
    return status


def route(row):
    old = row['route']
    if old == 'edgartools': return 'edgartools', True
    if old == 'markdown_or_plain_text': return 'markdown', True
    if old == 'trafilatura_xml': return 'trafilatura', False
    return None, False


def identity(manifest, plan):
    files = ['native_document_capture.py', 'native_document_adaptation.py',
             'finalize_structure_prechunks.py', 'run_native_structure_qualification.py',
             'document_structure_audit.py', 'probe_document_parsers.py',
             'source_structure_contract.py', 'restore_parser_paragraphs.py',
             'refine_document_chapters.py', 'validate_source_structure_audit.py']
    return dict(manifest_sha256=sha256(manifest.read_bytes()).hexdigest(),
                plan_sha256=sha256(plan.read_bytes()).hexdigest(),
                code={name:sha256((HERE/name).read_bytes()).hexdigest() for name in files},
                python=sys.executable, scope='frozen_selection_not_full_library_quality')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reuse-captures',type=Path)
    p.add_argument('--minimum-free-mib', type=int, default=2048)
    p.add_argument('--child-timeout-seconds', type=int, default=600)
    a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    if a.minimum_free_mib < 0 or a.child_timeout_seconds <= 0:
        raise ValueError('invalid_resource_limit')
    stamp=identity(a.manifest,a.plan);stamp['reuse_captures']=str(a.reuse_captures) if a.reuse_captures else None
    path=a.output/'identity.json'
    if path.exists() and json.loads(path.read_bytes()) != stamp:
        raise ValueError('native_qualification_resume_identity_changed')
    path.write_text(json.dumps(stamp,indent=2),encoding='utf-8')
    plan=[json.loads(l) for l in a.plan.read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    results=[]
    def save(stop_reason=None):
        summary=dict(planned_originals=len(plan),processed_rows=len(results),
                     pending_originals=len(plan)-len(results),stop_reason=stop_reason,
                     statuses=dict(Counter(r['status'] for r in results)),rows=results,
                     full_library_quality_pass=False,provider_calls=0,published=False)
        temp=a.output/'summary.tmp'
        temp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(a.output/'summary.json')
    save('running')
    for row in plan:
        source=row['original_id']; parser, can_adapt=route(row)
        result=dict(source_sha256=source,family=row['family'],title=row['title'],route=parser)
        if parser is None:
            result['status']='existing_route_retained_not_native_adapted'
            results.append(result); save(); continue
        capture=(a.reuse_captures or (a.output/'captures'))/source; projection=a.output/'adapted'/source
        result['capture_directory']=str(capture)
        receipt=capture/'receipt.json'
        if shutil.disk_usage(a.output).free < a.minimum_free_mib * 1024 * 1024:
            save('insufficient_output_disk_space'); return 3
        if not receipt.exists():
            if a.reuse_captures:
                result['status']='native_capture_failed';results.append(result);save();continue
            command=[sys.executable,str(HERE/'native_document_capture.py'),'--manifest',str(a.manifest),
                     '--id',source,'--route',parser,'--compare-fin','--output',str(capture)]
            if capture.exists():
                result['status']='native_capture_incomplete_attempt_requires_review'
                results.append(result); save(); continue
            code=run_child(command,a.output/(source+'.capture.log'),a.child_timeout_seconds)
            if code != 0:
                result.update(status='native_capture_failed',child_exit_code=code)
                results.append(result);save();continue
        if not receipt.exists() or json.loads(receipt.read_bytes())['status']!='captured':
            result['status']='native_capture_failed'; results.append(result); save(); continue
        native_receipt=json.loads(receipt.read_bytes())
        if (native_receipt['source_sha256']!=source or native_receipt['manifest_sha256']!=stamp['manifest_sha256']
                or native_receipt['implementation_sha256']!=stamp['code']['native_document_capture.py']):
            raise ValueError('native_qualification_capture_identity_changed')
        for name,key in [('native.json.gz','native_sha256'),('fin-comparison.json.gz','fin_comparison_sha256')]:
            if sha256((capture/name).read_bytes()).hexdigest()!=native_receipt[key]:
                raise ValueError('native_qualification_resume_artifact_changed')
        if not can_adapt:
            result['status']='native_captured_adaptation_pending'
        else:
            adapted_receipt=projection/'receipt.json'
            if not adapted_receipt.exists():
                if projection.exists():
                    result['status']='native_adaptation_incomplete_attempt_requires_review'
                    results.append(result);save();continue
                command=[sys.executable,str(HERE/'native_document_adaptation.py'),
                         '--capture',str(capture),'--output',str(projection),
                         '--baseline-artifact',row['artifact_path'],'--baseline-sha256',row['artifact_sha256']]
                code=run_child(command,a.output/(source+'.adapt.log'),a.child_timeout_seconds)
                if code != 0:
                    result.update(status='adaptation_failed',child_exit_code=code)
                    results.append(result);save();continue
            if adapted_receipt.exists():
                record=json.loads(adapted_receipt.read_bytes())
                if sha256((projection/'document.json.gz').read_bytes()).hexdigest()!=record['artifact_sha256']:
                    raise ValueError('native_qualification_resume_projection_changed')
                result.update(status='adapted_requires_quality_review',receipt=record)
            else:
                result['status']='adaptation_failed'
        results.append(result); save()
        print(json.dumps(dict(completed=len(results),total=len(plan),id=source,status=result['status'])),flush=True)
    save('completed')
    return int(any('failed' in r['status'] or 'incomplete_attempt' in r['status'] for r in results))


if __name__=='__main__':raise SystemExit(main())
