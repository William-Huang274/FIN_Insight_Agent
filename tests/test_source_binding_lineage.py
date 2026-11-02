import importlib.util
import base64
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("lineage", Path(__file__).parents[1] / "scripts/engineering/audit_source_binding_lineage.py")
lineage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lineage)


def test_related_official_page_with_wrong_document_number_is_rejected():
    assert lineage.candidate_relation({"document_number": "2026-12345"}, "https://govinfo.gov/one.pdf",
        "https://www.federalregister.gov/documents/2026/06/23/2026-54321/notice") == "rejected_document_number_mismatch"


def test_same_regulatory_number_does_not_prove_representation_or_version():
    assert lineage.candidate_relation({"document_number": "2026-12345"}, "https://govinfo.gov/one.pdf",
        "https://www.federalregister.gov/documents/2026/06/23/2026-12345/notice") == "same_document_alternate_representation"


def test_sec_directory_is_not_filing_original():
    assert lineage.candidate_relation({}, "https://www.sec.gov/Archives/edgar/data/100/000100000026000021/a.htm",
        "https://www.sec.gov/Archives/edgar/data/100/000100000026000021/index.json") == "filing_directory_not_document"


def test_clean_text_digest_is_not_raw_identity():
    value = "a" * 64
    assert lineage.raw_hints({"digest": value, "source_digest": value}, []) == []
    assert lineage.raw_hints({"acquisition_manifest": {"sha256": value}}, []) == [value]


def test_same_url_and_filename_candidates_never_prove_original():
    candidates = [{"identity": "filename_only"}, {"identity": "same_url_version_unverified"}]
    assert lineage.select_status(candidates, False)[0] == "candidate_version_unverified"


def test_derivative_links_to_parent_without_impersonating_original():
    candidates = [{"identity": "exact_raw_digest", "sha256": "b" * 64}]
    assert lineage.select_status(candidates, True)[0] == "derivative_parent_recovered"
    assert lineage.select_status(candidates, False)[0] == "historical_original_recovered"


def test_unlocated_original_preserves_explicit_processing_state():
    assert lineage.select_status([], False) == ("derivative_preserved_original_unlocated", [])


def test_recorded_path_keeps_version_uncertainty():
    assert lineage.select_status([{"identity": "recorded_archive_path"}], False)[0] == "recorded_archive_version_unverified"


def test_matching_hash_of_block_page_does_not_recover_original():
    check = lineage.inspect_payload(b"<html><title>Federal Register :: Request Access</title></html>")
    assert check["rejected"]
    assert lineage.select_status([{"identity":"exact_raw_digest", "content_check":check}], False)[0] == "derivative_preserved_original_unlocated"


def test_nested_visual_original_hash_is_parent_evidence():
    value = "c" * 64
    assert lineage.raw_hints({"visual_verification":{"original_pdf_sha256":value,"transcription_sha256":"d"*64}}, []) == [value]


def test_readme_api_must_match_public_url_and_decoded_content():
    body = b"# Readme\nA complete source."
    row = {"url":"https://github.com/team/repo/blob/main/README.md","source_digest":lineage.digest(body)}
    payload = {"html_url":row["url"],"content":base64.b64encode(body).decode()}
    assert lineage.decoded_readme_matches(json.dumps(payload).encode(), row)
    payload["html_url"] += "?other-version"
    assert not lineage.decoded_readme_matches(json.dumps(payload).encode(), row)
    payload["html_url"] = row["url"]
    payload["content"] = base64.b64encode(b"new text").decode()
    assert not lineage.decoded_readme_matches(json.dumps(payload).encode(), row)


def test_fr_identity_uses_header_not_other_document_reference():
    check = lineage.inspect_payload(b"[FR Doc No: 2026-12345] Also refers to 2026-54321.")
    assert check["fr_document_numbers"] == ["2026-12345"]
    assert not check["rejected"]


def test_primary_and_exhibit_file_mappings_do_not_cross_bind():
    item = {"filing_url":"https://sec.example/a/main.htm", "exhibit_url":"https://sec.example/a/ex99.htm"}
    urls = set(item.values())
    assert lineage.metadata_file_urls(item,"local_html_path","/raw/ex99.htm",urls) == {item["exhibit_url"]}
    assert lineage.metadata_file_urls(item,"local_primary_path","/raw/main.htm",urls) == {item["filing_url"]}
    assert lineage.metadata_file_urls(item,"local_html_path","/raw/unknown.htm",urls) == set()
