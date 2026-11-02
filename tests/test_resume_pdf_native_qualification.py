import hashlib
import json
import gzip
import pytest

from resume_pdf_native_qualification import verify_receipt


def fixture_receipt(tmp_path):
    oid='source'
    page=tmp_path/oid/'pages'/'00001.json.gz'
    page.parent.mkdir(parents=True)
    page.write_bytes(b'page-evidence')
    receipt=dict(engineering_pass=True,source_sha256=oid,planned_pages=1,
                 pages=[dict(page=1,artifact_sha256=hashlib.sha256(page.read_bytes()).hexdigest())])
    (tmp_path/oid/'receipt.json').write_text(json.dumps(receipt))
    return oid,page,receipt


def test_resume_rejects_changed_page(tmp_path):
    oid,page,_=fixture_receipt(tmp_path)
    assert verify_receipt(tmp_path,oid)['planned_pages']==1
    page.write_bytes(b'changed')
    with pytest.raises(ValueError,match='pdf_page_digest_changed'):verify_receipt(tmp_path,oid)


def test_resume_rejects_incomplete_page_sequence(tmp_path):
    oid,_,receipt=fixture_receipt(tmp_path)
    receipt['pages'][0]['page']=2
    (tmp_path/oid/'receipt.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match='pdf_page_identity_mismatch'):verify_receipt(tmp_path,oid)


def test_final_audit_verifies_reused_parent_page_and_complete_inventory(tmp_path):
    from audit_native_record_layout_results import audit
    parent=tmp_path/'parent';parent.mkdir()
    oid,page,receipt=fixture_receipt(parent)
    page.write_bytes(gzip.compress(json.dumps(dict(page=1,errors=[],table_layout_model_enabled=False)).encode()))
    receipt['pages'][0]['artifact_sha256']=hashlib.sha256(page.read_bytes()).hexdigest()
    receipt['parser_version']='2.0'
    (parent/oid/'receipt.json').write_text(json.dumps(receipt))
    inventory=tmp_path/'inventory.jsonl'
    inventory.write_text(json.dumps(dict(lane='pdf',original_id=oid)))
    root=tmp_path/'continuation';root.mkdir()
    (root/'identity.json').write_text(json.dumps(dict(parent_identity=dict(inventory_sha256=hashlib.sha256(inventory.read_bytes()).hexdigest()))))
    (root/'final-audit.json').write_text(json.dumps(dict(engineering_pass=True)))
    (root/'summary.json').write_text(json.dumps(dict(rows=[dict(id=oid,receipt=str(parent/oid/'receipt.json'))])))
    assert audit(root,inventory,'pdf')['counts']['pages']==1
    page.write_bytes(b'changed reused original')
    with pytest.raises(ValueError,match='pdf_page_digest_changed'):audit(root,inventory,'pdf')
