"""Lossless, version-bound judgment navigation, not generated summaries."""
from copy import deepcopy

from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256


def judgment_directory(outputs, review_state=None):
    """Keep author qualifiers/alternatives and backing steps together.

    Legacy findings have no explicit step linkage: carry all parent steps rather
    than guess which qualification can be dropped. Review is a model verdict,
    never a machine assertion of financial truth.
    """
    checks=(review_state or {}).get('checks',{})
    directory={}
    for output in outputs:
        result=output['result'];paper=output['obligation']['obligation_id'];digest=canonical_sha256(result)
        for i,finding in enumerate(result.get('findings',[])):
            selected=finding.get('basis_step_ids',[])
            steps=[s for s in result['steps'] if not selected or s['step_id'] in selected]
            missing=set(selected)-{s['step_id'] for s in steps}
            pointer=dict(paper_id=paper,paper_digest=digest,field_path=f'/findings/{i}/statement')
            ref='J-'+canonical_sha256(pointer)[:16]
            check=checks.get(paper+':'+pointer['field_path'])
            current=check if check and check['paper_digest']==digest else None
            source_ids=set(finding.get('source_ids',[]))|{sid for s in steps for sid in s.get('source_ids',[])}
            sources=[{k:v for k,v in e.items() if k!='body'} for e in output.get('review_evidence',[]) if e['id'] in source_ids]
            directory[ref]=dict(judgment_ref=ref,**pointer,finding=deepcopy(finding),basis_steps=deepcopy(steps),
                basis_selection='author_step_links' if selected else 'all_parent_steps_legacy_no_link',
                missing_basis_step_ids=sorted(missing),source_pointers=deepcopy(sources),
                source_ids=sorted(source_ids),scope=deepcopy(output['obligation']),
                review_status=current['status'] if current else 'not_reviewed_current_version',
                contract_errors=deepcopy(output.get('contract_errors',[])),
                financial_semantics_checked_by_runtime=False,
                reuse_rule='Read finding and all attached conditions, basis steps and source scope together; a checked status is a model verdict, not proof.')
    return directory


def select_judgments(refs, directory):
    if len(refs)!=len(set(refs)) or any(ref not in directory for ref in refs):
        raise ValueError('unknown_stale_or_duplicate_judgment_ref')
    selected=[deepcopy(directory[ref]) for ref in refs]
    if any(j['missing_basis_step_ids'] for j in selected):
        raise ValueError('judgment_basis_step_missing')
    return selected


HANDOFF_GUIDANCE = (
    ' judgment_context中的主张连同作者条件、反证、相关步骤和来源范围一起阅读，不能只复制statement。'
    ' 后续任务要复用某条判断时，在judgment_refs选择它的当前引用，并在dependency_ids包含该原任务。'
    '旧主张未指定步骤时runtime保留全部父任务步骤，不代表所有步骤都已证明该主张。'
    '独立statement本身仍须保留决定含义的主体、期间、单位及必要限定；不能依赖别处补回。'
    '新结果可用findings[].basis_step_ids选择本任务中已写出的相关步骤，避免重抄；不编造编号。'
    '引用目录和checked状态只提供导航/先前模型意见，不替代当前语义检查。')
