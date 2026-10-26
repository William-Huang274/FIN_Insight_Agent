from copy import deepcopy
from hashlib import sha256
import pytest
from scripts.engineering.organization_rerank_comparison import instruction_plan


def test_instruction_plan_binds_text_and_code_without_changing_candidate_contract(tmp_path):
    path=tmp_path/'instruction.txt';raw=b'Rank evidence answering the question.';path.write_bytes(raw)
    plan={'samples':[{'query_sha256':'q','candidate_ids':['a','b']}],
          'TokenBudgetBasis':{'input_scale':{'requests_max':40}}}
    before=deepcopy(plan['samples'])
    text,implementations=instruction_plan(plan,path)
    assert text==raw.decode() and plan['samples']==before
    assert plan['instruction_sha256']==sha256(raw).hexdigest()
    assert len(implementations)==3
    assert plan['TokenBudgetBasis']['input_scale']['requests_max']==40


@pytest.mark.parametrize('raw',[b' ',b'x'*4097])
def test_invalid_instruction_rejected_before_run(tmp_path,raw):
    path=tmp_path/'instruction.txt';path.write_bytes(raw)
    with pytest.raises(ValueError,match='outside_budget'):instruction_plan({},path)
