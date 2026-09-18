"""Bounded input adapters for method probes; preserve the production wire contract.

Only runtime navigation fields are supplied here. No JSON completion, financial
inference, citation guessing or implicit model retry.
"""
from copy import deepcopy
import json
from functools import lru_cache

from pydantic import Field, ValidationError, create_model

from sec_agent.agent_runtime.evidence_resolution import parsing_record
from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from .method_execution import Contract
from .method_review import (SubmittedMethodInspectionCheck, MethodFindingConfirmation,
                            SubmittedMethodReview)
from sec_agent.agent_runtime.case_review_agent import CaseReviewFinding, ReviewSourceCheck


class SubmissionRejected(ValueError):
    def __init__(self, receipt):
        super().__init__('method_submission_requires_local_correction')
        self.receipt = receipt


def target_directory(payload):
    return {f'T{i+1}-{canonical_sha256(t)[:10]}': deepcopy(t)
            for i, t in enumerate(payload.get('review_context', {}).get('targets', []))}


def source_directory(payload):
    """Select whole bounded delivered windows; never stitch, infer or search quotes."""
    result = {}
    for source in payload.get('review_evidence', []):
        body = source.get('body', '')
        if not body.strip() or len(body) > 6000 or not source.get('digest'):
            continue
        identity = {k: deepcopy(source.get(k)) for k in ('id', 'digest', 'source', 'locator')}
        ref = 'E-' + canonical_sha256({**identity, 'body': body})[:16]
        result[ref] = {'source_id': source['id'], 'quote': body,
                      'quote_span': {'source_digest': source['digest'], 'start': 0, 'end': len(body)}}
    return result


class SelectedSource(Contract):
    source_ref: str = Field(min_length=1, description='Select a current review_evidence source_ref. Runtime binds its entire bounded original window. You must assess whether it supports the relationship.')


def _project(name, model, omitted):
    fields = {k: (v.annotation, deepcopy(v)) for k, v in model.model_fields.items() if k not in omitted}
    fields['source_checks'] = (list[SelectedSource | ReviewSourceCheck], Field(max_length=64,
        description='Prefer source_ref for supplied bounded windows. Otherwise exact original quote/span, no ellipsis or paraphrase. Selection proves occurrence only, not support.'))
    fields['target_ref'] = (str, Field(min_length=1, description='Select the exact current runtime target_ref; runtime binds identity, version and location.'))
    return create_model(name, __base__=Contract, **fields)


CompactInspection = _project('CompactMethodInspection', SubmittedMethodInspectionCheck,
                             {'paper_id', 'paper_digest', 'field_path', 'target_quote'})
CompactFinding = _project('CompactMethodFinding', CaseReviewFinding, {'paper_id', 'problematic_quote'})
CompactConfirmation = _project('CompactMethodConfirmation', MethodFindingConfirmation,
                               {'paper_id', 'paper_digest', 'current_quote'})


class CompactReview(Contract):
    inspection_checks: list[CompactInspection] = Field(max_length=160)
    findings: list[CompactFinding] = Field(default_factory=list, max_length=80)
    finding_checks: list[CompactConfirmation] = Field(default_factory=list, max_length=80)


@lru_cache(maxsize=4)
def compact_schema(schema):
    if 'review' not in schema.model_fields:
        return schema
    return create_model('Compact'+schema.__name__, __base__=schema,
                        review=(CompactReview, Field(description='Check complete field meaning; runtime supplies navigation fields.')))


def _strict_object(raw):
    records=[]
    if isinstance(raw, dict):
        return deepcopy(raw), records
    if not isinstance(raw, str):
        raise ValueError('response_requires_json_object')
    text=raw.strip()
    lines=text.splitlines()
    if len(lines)>=3 and lines[0].lower() in {'```json','```'} and lines[-1]=='```':
        text='\n'.join(lines[1:-1])
        records.append(parsing_record('complete_outer_json_fence_v1',raw,text))
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:
                raise ValueError('duplicate_json_key:'+key)
            result[key]=value
        return result
    def constant(value):
        raise ValueError('non_json_constant:'+value)
    value=json.loads(text,object_pairs_hook=pairs,parse_constant=constant)
    if not isinstance(value,dict):
        raise ValueError('response_requires_json_object')
    return value,records


def decode_submission(raw, schema, directory=None, sources=None):
    """Return a wire object plus audit, or an immutable rejected candidate receipt."""
    directory=directory or {}
    sources=sources or {}
    normalized=None;records=[]
    try:
        normalized,records=_strict_object(raw)
        review=normalized.get('review')
        if isinstance(review,dict):
            for section in ('inspection_checks','findings','finding_checks'):
                for i,row in enumerate(review.get(section,[]) if isinstance(review.get(section,[]),list) else []):
                    if not isinstance(row,dict):
                        continue
                    checks=row.get('source_checks', [])
                    for j,check in enumerate(checks if isinstance(checks,list) else []):
                        if not isinstance(check,dict) or 'source_ref' not in check:
                            continue
                        ref=check['source_ref']
                        if not isinstance(ref,str) or ref not in sources:
                            raise ValueError(f'unknown_or_stale_source_ref:/review/{section}/{i}/source_checks/{j}')
                        # The original remains in delivered evidence. Persist a
                        # digest-bound span, not another copy in every review row.
                        selected=sources[ref]
                        binding={'source_id':selected['source_id'], 'quote':'',
                                 'quote_span':selected['quote_span']}
                        if any(k!='source_ref' and (k not in binding or v!=binding[k]) for k,v in check.items()):
                            raise ValueError(f'explicit_source_binding_conflict:/review/{section}/{i}/source_checks/{j}')
                        before=deepcopy(check)
                        check.clear();check.update(deepcopy(binding))
                        records.append(parsing_record('current_delivered_source_window_v1',before,deepcopy(check),
                            field_path=f'/review/{section}/{i}/source_checks/{j}',source_ref=ref,
                            entire_window_selected=True,claim_support_not_inferred=True))
                    if 'target_ref' not in row:
                        continue
                    ref=row['target_ref']
                    if not isinstance(ref,str) or ref not in directory:
                        raise ValueError(f'unknown_or_stale_target_ref:/review/{section}/{i}/target_ref')
                    target=directory[ref]
                    bindings={'paper_id':target['paper_id']}
                    if section=='inspection_checks':
                        bindings.update(paper_digest=target['paper_digest'],field_path=target['field_path'],target_quote=target['text'][:1500])
                    elif section=='findings':
                        bindings['problematic_quote']=target['text'][:6000]
                    else:
                        bindings.update(paper_digest=target['paper_digest'],current_quote=target['text'][:4000])
                    if any(k in row and row[k]!=v for k,v in bindings.items()):
                        raise ValueError(f'explicit_navigation_conflict:/review/{section}/{i}')
                    before=deepcopy(row)
                    row.pop('target_ref');row.update(bindings)
                    records.append(parsing_record('current_review_target_binding_v1',before,deepcopy(row),
                        field_path=f'/review/{section}/{i}',target_ref=ref,
                        target_digest=canonical_sha256(target),entire_field_requires_review=True))
        value=schema.model_validate(normalized)
    except (ValueError, TypeError) as exc:
        if isinstance(exc, ValidationError):
            errors=[{'location':'/'+ '/'.join(str(p) for p in e['loc']),
                     'code':e['type'],'detail':e['msg']} for e in exc.errors(include_input=False,include_url=False)]
        elif isinstance(exc,json.JSONDecodeError):
            errors=[{'location':'/', 'code':'invalid_json','detail':exc.msg,'line':exc.lineno,'column':exc.colno}]
        else:
            errors=[{'location':'/', 'code':'submission_binding_or_format','detail':str(exc)}]
        raise SubmissionRejected({'status':'candidate_saved_not_accepted','raw_response':deepcopy(raw),
            'candidate':normalized,'candidate_digest':canonical_sha256(normalized) if normalized is not None else None,
            'target_directory':deepcopy(directory),'errors':errors,'runtime_parsing':records,
            'source_directory':deepcopy(sources),
            'executed':False,'automatic_retry':False,'financial_semantics_checked':False}) from None
    return value,{'status':'schema_valid_not_financial_acceptance','runtime_parsing':records,
                  'raw_response':deepcopy(raw),'normalized_digest':canonical_sha256(value.model_dump(mode='json'))}


def amend_candidate(receipt, candidate_digest, replacements):
    """Explicit local field supplement, restricted to schema-error locations.

    Returns another candidate only. The caller must revalidate the whole action
    against the original target directory before any dispatch or acceptance.
    """
    candidate=deepcopy(receipt['candidate'])
    if (candidate is None or candidate_digest!=receipt['candidate_digest']
            or canonical_sha256(candidate)!=candidate_digest):
        raise ValueError('stale_or_unparsed_candidate')
    allowed={e['location'] for e in receipt['errors'] if e['location']!='/' and e['code']!='extra_forbidden'}
    if not replacements or not set(replacements)<=allowed:
        raise ValueError('supplement_only_explicit_error_fields')
    for path,value in replacements.items():
        parts=path.lstrip('/').split('/');parent=candidate
        for key in parts[:-1]:
            parent=parent[int(key)] if isinstance(parent,list) else parent[key]
        key=int(parts[-1]) if isinstance(parent,list) else parts[-1]
        parent[key]=deepcopy(value)
    return candidate,parsing_record('explicit_local_submission_supplement_v1',receipt['candidate'],candidate,
        original_candidate_digest=candidate_digest,changed_paths=list(replacements),
        accepted=False,requires_full_revalidation=True)


async def invoke_submission(call, actor, payload, schema, record, *, compact=False):
    task=deepcopy(payload)
    directory=target_directory(task) if compact else {}
    sources=source_directory(task) if compact else {}
    if directory:
        task['submission_targets']=[{'target_ref':ref,**target} for ref,target in directory.items()]
        task['instructions'] += (' 复核提交选择submission_targets的target_ref即可，runtime填入paper_id/digest、字段位置和原句。'
            '须审阅对应整个字段；该引用不是已核事实。不要自己输出这些被托管的定位字段。')
        for source in task.get('review_evidence', []):
            matches=[ref for ref,binding in sources.items() if binding['source_id']==source['id'] and binding['quote']==source['body']]
            if len(matches)==1:
                source['source_ref']=matches[0]
        task['instructions'] += (' source_checks优先只选review_evidence中source_ref，runtime绑定该完整原文窗口及摘要/范围，'
            '无需抄长ID、引句或字符偏移。必须自行读原文判断是否支持，选择不代表支持；不得拼接省略号伪装连续引文。')
    # Adapters must preserve raw responses and return raw text/dict without an
    # earlier schema validation. Provider failures remain provider failures.
    raw=await call(actor,task,compact_schema(schema) if directory else schema)
    try:
        result,receipt=decode_submission(raw,schema,directory,sources)
    except SubmissionRejected as exc:
        exc.receipt['actor']=actor;record('submission_rejected',exc.receipt)
        raise
    record('submission_parsed',{'actor':actor,**receipt})
    return result
