from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts/engineering'))
from source_display_purpose import purposes


def test_hidden_text_is_not_assumed_to_be_machine_metadata():
    raw = b'<html><body><div hidden><p>Important source content.</p></div></body></html>'
    evidence = purposes(raw)['/html/body/div/p']
    assert evidence['purpose'] == 'undetermined_hidden_content'
    assert evidence['candidate_policy'] == 'retained_pending_purpose_review'


def test_declared_xbrl_hidden_wins_over_outer_display_state():
    raw = b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body><div style="display:none"><ix:hidden><p>100</p></ix:hidden></div></body></html>'
    assert purposes(raw)['/html/body/div/ix:hidden/p']['purpose'] == 'inline_xbrl_metadata'


def test_unique_explicit_control_proves_collapsed_content_not_metadata():
    raw = b'<html><body><button aria-controls="p" aria-expanded="false">Expand</button><div id="p" hidden><p>Operating evidence.</p></div></body></html>'
    result = purposes(raw)['/html/body/div/p']
    assert result['purpose'] == 'interactive_disclosure' and result['candidate_policy'] == 'body_content'
    changed = raw.replace(b'</body>', b'<div id="p"></div></body>')
    assert purposes(changed)['/html/body/div[1]/p']['purpose'] == 'undetermined_hidden_content'


def test_framework_contract_needs_group_controller_and_content():
    raw = b'<html><body><ul uk-accordion><li><a class="uk-accordion-title">Study details</a><div class="uk-accordion-content" hidden><p>Evidence.</p></div></li></ul></body></html>'
    path = '/html/body/ul/li/div/p'
    result = purposes(raw)[path]
    assert result['purpose'] == 'interactive_disclosure' and result['basis'] == 'uikit_original_accordion_structure'
    changed = raw.replace(b' uk-accordion', b'')
    assert purposes(changed)[path]['purpose'] == 'undetermined_hidden_content'


def test_hidden_numeric_value_is_not_a_page_number_without_page_geometry():
    raw = b'<html><body><div><div style="display:none">100</div></div></body></html>'
    path = '/html/body/div/div'
    assert purposes(raw)[path]['purpose'] == 'undetermined_hidden_content'
    changed = raw.replace(b'</div></div>', b'</div><div style="break-after:page"><hr></div></div>')
    assert purposes(changed)[path+'[1]']['purpose'] == 'layout_page_marker'


def test_plain_continuation_and_responsive_classes_do_not_supply_hidden_proof():
    raw = b'<html><body><ix:continuation><p>Evidence.</p></ix:continuation><p class="hidden">More.</p></body></html>'
    assert purposes(raw) == {}


def test_repair_preserves_all_text_and_chapter_identity_and_rechecks_original():
    from copy import deepcopy
    from hashlib import sha256
    import pytest
    from source_display_purpose import repair, verify
    raw = b'<html><body><button aria-expanded="false" aria-controls="p">Open</button><div id="p" hidden><p>Useful evidence.</p></div></body></html>'
    sid = sha256(raw).hexdigest() + ':/html/body/div/p'
    document = dict(source_sha256=sha256(raw).hexdigest(), source_containers=[dict(id=sid, text='Useful evidence.', excluded_navigation=True)],
        blocks=[dict(kind='text', text='Useful evidence.', source_container_id=sid, chapter_ids=['original'])],
        chapter_tree=[dict(id='original')], pre_chunks=[])
    updated, proofs = repair(document, raw)
    assert proofs and not updated['source_containers'][0]['excluded_navigation']
    assert updated['blocks'] == document['blocks'] and updated['chapter_tree'] == document['chapter_tree']
    verify(updated, raw)
    assert repair(updated, raw)[0] == updated
    changed = deepcopy(updated); changed['source_containers'][0]['excluded_navigation'] = True
    with pytest.raises(ValueError):
        verify(changed, raw)
    with pytest.raises(ValueError):
        repair(document, raw + b' ')


def test_uncertain_content_is_retained_as_context_and_page_markers_as_structure():
    from hashlib import sha256
    from source_display_purpose import repair, verify
    raw = b'<html><body><p hidden>Evidence</p><div><div style="display:none">1</div><div style="break-after:page"><hr></div></div></body></html>'
    h = sha256(raw).hexdigest()
    ids = [h + ':/html/body/p', h + ':/html/body/div/div[1]']
    document = dict(source_sha256=h, source_containers=[dict(id=sid, text=text) for sid, text in zip(ids, ['Evidence', '1'])],
        blocks=[dict(kind='text', text=text, source_container_id=sid) for sid, text in zip(ids, ['Evidence', '1'])])
    updated, _ = repair(document, raw)
    assert [b['candidate_role'] for b in updated['blocks']] == ['attached_context_candidate', 'retained_structure']
    assert [b['text'] for b in updated['blocks']] == ['Evidence', '1']
    verify(updated, raw)


def test_hidden_fact_text_is_linked_context_not_discarded_or_a_financial_inference():
    raw = b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body><ix:nonnumeric name="ecd:Text" contextref="c1"><table style="display:none"><tr><td>Important footnote</td></tr></table></ix:nonnumeric></body></html>'
    result = purposes(raw)['/html/body/ix:nonnumeric/table']
    assert result['purpose'] == 'inline_xbrl_fact_representation'
    assert result['fact']['context_ref'] == 'c1' and not result['financial_semantics_inferred']


def test_explicit_encoded_video_frame_does_not_become_a_transcript():
    raw = b'<html><body><div hidden><div data-video-embed-field-modal="&lt;iframe src=&quot;https://example.org/video&quot;&gt;&lt;/iframe&gt;"></div><p>Video title.</p></div></body></html>'
    result = purposes(raw)['/html/body/div/p']
    assert result['purpose'] == 'embedded_media_caption' and not result['transcript_available']
    assert result['candidate_policy'] == 'media_caption_context'
    changed = raw.replace(b'https://example.org/video', b'https://[')
    assert purposes(changed)['/html/body/div/p']['purpose'] == 'undetermined_hidden_content'


def test_framework_navigation_needs_its_own_component_evidence():
    raw = b'<html><body><div data-uk-navbar="true" class="uk-navbar-dropdown" hidden><a href="/topics">Topics</a><p>Menu label</p></div></body></html>'
    assert purposes(raw)['/html/body/div/p']['purpose'] == 'interactive_navigation'
    assert purposes(raw.replace(b' data-uk-navbar="true"', b''))['/html/body/div/p']['purpose'] == 'undetermined_hidden_content'


def test_explicit_navigation_role_wins_over_generic_expand_control():
    raw = b'<html><body><button aria-expanded="false" aria-controls="m">Open</button><div id="m" role="menu" hidden><p>Navigation label</p></div></body></html>'
    result = purposes(raw)['/html/body/div/p']
    assert result['purpose'] == 'interactive_navigation' and result['candidate_policy'] == 'retained_navigation'


def test_native_catalog_consumes_collapsed_body_purpose_and_preserves_metadata():
    from hashlib import sha256
    from source_structure_contract import source_containers
    from source_display_purpose import verify
    raw = b'<html><body><ul uk-accordion><li><a class="uk-accordion-title">Details</a><div class="uk-accordion-content" hidden><p>Research evidence.</p></div></li></ul></body></html>'
    rows = source_containers(raw)
    row = next(r for r in rows if r['text'] == 'Research evidence.')
    assert not row['excluded_navigation'] and row['source_display_purpose']['purpose'] == 'interactive_disclosure'
    verify(dict(source_sha256=sha256(raw).hexdigest(),source_containers=rows),raw)
