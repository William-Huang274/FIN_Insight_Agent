import pytest
from financial_facts import load_company_fact_mart_policy, CompanyFactSourceError
from test_sec_companyfacts_snapshot import _minimal_s2_policy


def test_ingestion_does_not_require_evaluation_answers_but_acceptance_still_does():
    policy = _minimal_s2_policy()
    policy.pop("acceptance_qrels")
    assert load_company_fact_mart_policy(policy, require_acceptance_qrels=False).acceptance_qrels == ()
    with pytest.raises(CompanyFactSourceError, match="qrels_invalid"):
        load_company_fact_mart_policy(policy)
    policy["authority"]["typed_conflict_fails_closed"] = False
    with pytest.raises(CompanyFactSourceError, match="authority_invalid"):
        load_company_fact_mart_policy(policy, require_acceptance_qrels=False)
