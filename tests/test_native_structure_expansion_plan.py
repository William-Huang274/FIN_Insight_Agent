import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('expansion', Path(__file__).parents[1]/'scripts/engineering/build_native_structure_expansion_plan.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def binding(oid='a', doc='d', route='edgartools', **extra):
    return dict(original_id=oid, document_id=doc, route=route, artifact_path='old.gz', artifact_sha256='hash', **extra)


def test_every_binding_including_missing_originals_and_aliases_stays_accounted():
    rows, missing, summary = module.build([binding(), binding(doc='alias'), binding(None, 'missing')], digest=lambda _: 'hash')
    assert summary['accounted_bindings'] == summary['source_bindings'] == 3
    assert len(rows) == 1 and rows[0]['bindings'] == ['d', 'alias']
    assert len(missing) == 1
    assert rows[0]['admission_state'] == 'ready_for_candidate_adaptation'
    assert rows[0]['quality_state'] == 'insufficient_evidence'


def test_clean_documents_have_review_checks_and_prior_execution_does_not_grant_quality():
    rows, _, _ = module.build([binding()], [{'source_sha256':'a', 'status':'adapted_requires_quality_review'}], digest=lambda _: 'hash')
    assert rows[0]['review_stratum'] == 'no_current_diagnostic'
    assert 'heading_precision_and_recall' in rows[0]['required_checks']
    assert rows[0]['quality_state'] == 'insufficient_evidence'


def test_baseline_conflicts_and_digest_changes_block_only_affected_original():
    aliases = [binding(), dict(binding(doc='alias'), artifact_sha256='other'), binding('b','b')]
    rows, _, _ = module.build(aliases, digest=lambda _: 'hash')
    assert rows[0]['admission_state'] == 'baseline_repair_required'
    assert 'conflicting_baseline_digests' in rows[0]['baseline_problems']
    assert 'baseline_digest_mismatch' in rows[0]['baseline_problems']
    assert rows[1]['admission_state'] == 'ready_for_candidate_adaptation'


def test_all_routes_remain_separate_and_unsupported_not_silently_dropped():
    routes=['edgartools','markdown_or_plain_text','trafilatura_xml','pypdf_text_diagnostic','structured_json','new_parser']
    rows, _, summary = module.build([binding(str(i),str(i),r) for i,r in enumerate(routes)], digest=lambda _: 'hash')
    assert [r['lane'] for r in rows] == ['sec','markdown','web','pdf','structured','unsupported']
    assert summary['states']['ready_for_candidate_adaptation'] == 2
    assert summary['available_originals'] == 6
    assert not summary['candidate_adaptation_executed']


def test_missing_baseline_is_retained_as_failure():
    def missing(_): raise FileNotFoundError('gone')
    rows, _, _ = module.build([binding()], digest=missing)
    assert rows[0]['baseline_problems'] == ['baseline_unreadable:FileNotFoundError']
