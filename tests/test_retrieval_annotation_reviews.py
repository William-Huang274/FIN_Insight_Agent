from copy import deepcopy

import pytest

from scripts.engineering.retrieval_annotation_delta import digest, validate_delta
from scripts.engineering.retrieval_annotation_reviews import AnnotationReviewStore, reviewed_role
import scripts.engineering.retrieval_annotation_reviews as reviews


def source_fixture():
    packet = {"schema": "retrieval-annotation-packet.v3", "packet_id": "local",
              "source": {"source_digest": "original", "coordinate_space": "document"},
              "elements": [{"id": "A", "kind": "table", "text": "(d) Exhibits", "start": 0, "end": 12},
                           {"id": "B", "kind": "table", "text": "Number | Description", "start": 13, "end": 33},
                           {"id": "C", "kind": "line", "text": "page", "start": 34, "end": 38}],
              "tasks": [{"task_id": "caption", "kind": "context", "scope_ids": ["A", "B"], "target_ids": ["B"]}]}
    role = reviewed_role(packet, "A", "layout_caption", reviewer="primary",
                         reason="Original source shows one section-label row, not observations.")
    packet["source_role_refs"] = {"A": role["review_id"]}
    result = {"packet_id": "local", "packet_digest": digest(packet), "decisions": [
        {"task_id": "caption", "status": "proposed", "links": [{"support_ids": ["A"], "target_id": "B"}]}]}
    return packet, result, role


def test_reviewed_layout_preserves_original_physical_kind_and_coordinates():
    p, r, role = source_fixture()
    out = validate_delta(p, r, trusted_roles={role["review_id"]: role})
    assert out["elements"] == p["elements"]
    assert out["elements"][0]["kind"] == "table"
    assert not out["publication_allowed"]


@pytest.mark.parametrize("change", ["untrusted", "source", "coordinate", "text", "alter_review", "data_table"])
def test_no_self_attested_or_stale_layout_roles(change):
    p, r, role = source_fixture()
    trusted = {role["review_id"]: role}
    if change == "untrusted": trusted = {}
    if change == "source": p["source"]["source_digest"] = "different"
    if change == "coordinate": p["elements"][0]["start"] = 1
    if change == "text": p["elements"][0]["text"] = "Cash balance"
    if change == "alter_review": role["role"] = "data_table"
    if change == "data_table":
        role = reviewed_role(p, "A", "data_table", reviewer="primary", reason="Verified data, not caption")
        p["source_role_refs"]["A"] = role["review_id"]
        trusted = {role["review_id"]: role}
    r["packet_digest"] = digest(p)
    with pytest.raises(ValueError): validate_delta(p, r, trusted_roles=trusted)


def test_reviewed_reuse_survives_restart_and_unrelated_task_edit(tmp_path):
    p, r, role = source_fixture()
    path = tmp_path/"reviews.sqlite"
    store = AnnotationReviewStore(path)
    store.add_role(role)
    key = store.accept(p, r, "caption", reviewer="primary", reason="Read both source elements")
    store.close()
    store = AnnotationReviewStore(path)
    p["elements"][-1]["text"] = "next"
    p["tasks"].append({"task_id": "later", "kind": "partition", "scope_ids": ["C"]})
    assert store.reuse(p, "caption") == r["decisions"][0]
    assert store.reuse(p, "later") is None
    assert key
    store.close()


@pytest.mark.parametrize("change", ["source", "scope", "policy"])
def test_reuse_requires_exact_source_scope_and_policy(tmp_path, monkeypatch, change):
    p, r, role = source_fixture()
    store = AnnotationReviewStore(tmp_path/"reviews.sqlite")
    store.add_role(role)
    store.accept(p, r, "caption", reviewer="primary", reason="Checked")
    if change == "source": p["source"]["source_digest"] = "new revision"
    if change == "scope": p["tasks"][0]["scope_ids"].append("C")
    if change == "policy": monkeypatch.setattr(reviews, "implementation_digest", lambda: "new-policy")
    assert store.reuse(p, "caption") is None
    if change == "policy":
        assert len(store.prior_candidates(p, "caption")) == 1
    else:
        assert store.prior_candidates(p, "caption") == []
    store.close()


def test_conflicting_review_cannot_overwrite_and_unresolved_cannot_be_accepted(tmp_path):
    p, r, role = source_fixture()
    store = AnnotationReviewStore(tmp_path/"reviews.sqlite")
    store.add_role(role)
    store.accept(p, r, "caption", reviewer="primary", reason="Checked")
    other = deepcopy(r)
    other["decisions"][0] = {"task_id": "caption", "status": "unresolved", "reason": "Missing geometry"}
    with pytest.raises(ValueError): store.accept(p, other, "caption", reviewer="primary", reason="Checked")
    with pytest.raises(ValueError, match="conflicting"):
        store.accept(p, r, "caption", reviewer="other", reason="Different approval")
    assert store.reuse(p, "caption") == r["decisions"][0]
    store.close()


def test_good_task_survives_another_rejected_task_without_rebinding_response(tmp_path):
    p, r, role = source_fixture()
    p['tasks'].append({'task_id': 'other', 'kind': 'context', 'scope_ids': ['A', 'B'], 'target_ids': ['B']})
    r['decisions'].append({'task_id': 'other', 'status': 'proposed', 'links': []})
    r['packet_digest'] = digest(p)
    store = AnnotationReviewStore(tmp_path/'reviews.sqlite')
    store.add_role(role)
    with pytest.raises(ValueError): validate_delta(p, r, trusted_roles=store.roles())
    store.accept(p, r, 'caption', reviewer='primary', reason='This relationship independently checked')
    assert store.reuse(p, 'caption') == r['decisions'][0]
    with pytest.raises(ValueError): store.accept(p, r, 'other', reviewer='primary', reason='Invalid')
    assert store.reuse(p, 'other') is None
    r['packet_digest'] = 'unbound'
    with pytest.raises(ValueError, match='binding'):
        store.accept(p, r, 'caption', reviewer='primary', reason='Must not accept rebound response')
    store.close()
