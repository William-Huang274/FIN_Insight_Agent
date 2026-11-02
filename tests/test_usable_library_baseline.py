import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]/"scripts/engineering"))
from freeze_usable_library_baseline import body_check, preferred


def candidate(sha, identity="same_url_version_unverified", **kwargs):
    return dict(current_sha256=sha,identity=identity,check={"rejected":False},**kwargs)


def test_error_body_removed_but_document_quoting_error_preserved():
    assert body_check(b'<title>Federal Register :: Request Access</title>')["rejected"]
    assert body_check(b'{"message":"Not Found","documentation_url":"https://example.test"}')["rejected"]
    assert not body_check(b'<title>Annual report</title>We received an access denied response.')["rejected"]
    assert not body_check(b'{"message":"Not Found","research_conclusion":"about errors"}')["rejected"]


def test_unknown_historical_version_does_not_block_unique_current_source():
    c=candidate("a")
    assert preferred([c])==(c,"unique_current_content")


def test_filename_alone_is_not_source_identity():
    assert preferred([candidate("a","filename_only")])[0] is None


def test_conflicting_undated_candidates_are_not_arbitrarily_selected():
    assert preferred([candidate("a"),candidate("b")])==(None,"conflicting_current_versions")


def test_dated_versions_can_form_new_baseline_but_ties_cannot():
    first=candidate("a",captured_at="2026-01-01T00:00:00Z")
    second=candidate("b",captured_at="2026-02-01T00:00:00Z")
    assert preferred([first,second])==(second,"latest_recorded_capture_new_baseline")
    first["captured_at"]=second["captured_at"]
    assert preferred([first,second])[0] is None


def test_rejected_alternative_does_not_remove_valid_body():
    bad=candidate("bad","exact_raw_digest");bad["check"]["rejected"]=True
    good=candidate("good")
    assert preferred([bad,good])[0] is good
