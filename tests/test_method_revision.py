from copy import deepcopy

import pytest

from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from sec_agent.research_foundation.method_revision import (
    MethodRevision, revise_workpaper, revision_targets, TargetedMethodRevision,
    revise_targeted_workpaper,
)


def paper():
    return dict(obligation_id='O1',execution='completed',summary='Limited nominal comparison',
        steps=[dict(step_id='S2',status='completed',finding='Original table',source_ids=['P1'],
                    calculation_refs=['CALC::1'])],
        findings=[dict(statement='Source reports a link bandwidth',kind='factual',source_ids=['P1'],
                       public_basis='Source label',assumptions=[],alternative='Maybe not a link',would_change='')],
        unresolved=['Direction unspecified'],task_note=dict(changes=[],blockers=[],next_action='Review'))


def revision(path='/findings/0/alternative',value=''):
    return MethodRevision(changes=[dict(path=path,value=value,reason='Read the original label')],review_note='Keep valid results')


def test_revision_preserves_source_calculations_and_original_and_records_actual_change():
    original=paper();saved=deepcopy(original)
    result,audit=revise_workpaper(original,canonical_sha256(original),revision(),{'/findings/0/alternative'})
    assert original==saved
    assert result.steps[0].calculation_refs==['CALC::1']
    assert result.findings[0].source_ids==['P1']
    assert result.summary==original['summary']
    assert result.findings[0].alternative==''
    assert len(result.task_note.changes)==1
    assert audit['changes'][0]['before']=='Maybe not a link'
    assert not audit['accepted'] and audit['requires_evidence_and_semantic_review']


def test_stale_or_unapproved_patch_cannot_modify_paper():
    original=paper()
    with pytest.raises(ValueError,match='stale'):
        revise_workpaper(original,'wrong',revision(),{'/findings/0/alternative'})
    with pytest.raises(ValueError,match='authorized'):
        revise_workpaper(original,canonical_sha256(original),revision(),{'/summary'})
    with pytest.raises(ValueError,match='identity'):
        revise_workpaper(original,canonical_sha256(original),revision('/obligation_id','O2'),{'/obligation_id'})


def test_invalid_whole_result_is_not_saved_as_valid_revision():
    original=paper()
    with pytest.raises(ValueError):
        revise_workpaper(original,canonical_sha256(original),revision('/summary',''),{'/summary'})
    assert original['summary']


def test_duplicate_overlapping_and_noop_edits():
    original=paper();digest=canonical_sha256(original)
    r=revision();r.changes.append(r.changes[0])
    with pytest.raises(ValueError,match='unique'):
        revise_workpaper(original,digest,r,{'/findings/0/alternative'})
    r=revision('/findings',original['findings']);r.changes.extend(revision().changes)
    with pytest.raises(ValueError,match='overlapping'):
        revise_workpaper(original,digest,r,{'/findings','/findings/0/alternative'})
    result,audit=revise_workpaper(original,digest,revision('/summary',original['summary']),{'/summary'})
    assert audit['changes']==[] and result.task_note.changes==[]


def test_content_selected_revision_does_not_require_model_array_index():
    original=paper()
    original['findings'].append({**deepcopy(original['findings'][0]), 'statement':'Second distinct hypothesis'})
    paths={'/findings/0/statement','/findings/1/statement'}
    targets=revision_targets(original,paths)
    ref=next(k for k,v in targets.items() if v['current_value']=='Second distinct hypothesis')
    request=TargetedMethodRevision(changes=[dict(target_ref=ref,value='Second qualified hypothesis',reason='Clarify its condition')],review_note='Keep first finding')
    candidate,audit=revise_targeted_workpaper(original,canonical_sha256(original),request,paths)
    assert candidate.findings[0].statement==original['findings'][0]['statement']
    assert candidate.findings[1].statement=='Second qualified hypothesis'
    assert audit['changes'][0]['path']=='/findings/1/statement'
    assert audit['runtime_parsing'][0]['origin']=='runtime_compatibility_parse'
    assert not audit['accepted']


def test_target_menu_cannot_survive_version_change_or_grant_new_paths():
    original=paper();paths={'/summary'}
    ref=next(iter(revision_targets(original,paths)))
    request=TargetedMethodRevision(changes=[dict(target_ref=ref,value='Changed',reason='Review')],review_note='Local')
    changed=deepcopy(original);changed['summary']='New saved version'
    with pytest.raises(ValueError,match='unknown_or_stale'):
        revise_targeted_workpaper(changed,canonical_sha256(changed),request,paths)
    with pytest.raises(ValueError,match='unknown_or_stale'):
        revise_targeted_workpaper(original,canonical_sha256(original),request,{'/unresolved'})
    request.changes.append(request.changes[0])
    with pytest.raises(ValueError,match='unique'):
        revise_targeted_workpaper(original,canonical_sha256(original),request,paths)
