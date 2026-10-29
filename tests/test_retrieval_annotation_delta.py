from copy import deepcopy

import pytest

from scripts.engineering.retrieval_annotation_delta import ContractError, digest, validate_delta


def fixture():
    elements = []
    offset = 0
    for eid, kind, text in [("H", "line", "Cash (millions)"),
                            ("T", "table", "Cash | 10 (1)"),
                            ("F", "line", "(1) Restricted cash excluded."),
                            ("P", "line", "27")]:
        elements.append(dict(id=eid, kind=kind, start=offset, end=offset+len(text), text=text))
        offset += len(text) + 1
    packet = dict(schema="retrieval-annotation-packet.v2", packet_id="sample",
                  source={"source_digest": "fixture"}, elements=elements,
                  tasks=[dict(task_id="foot", kind="footnote", scope_ids=["H", "T", "F"],
                              support_ids=["F"], target_ids=["T"])])
    result = dict(packet_id="sample", packet_digest=digest(packet), decisions=[
        dict(task_id="foot", status="proposed", links=[dict(support_ids=["F"], target_id="T")])])
    return packet, result


def test_overlay_cannot_omit_untasked_page_or_rewrite_original():
    p, r = fixture()
    before = deepcopy(p)
    overlay = validate_delta(p, r)
    assert overlay["elements"] == p["elements"] and p == before
    assert overlay["coverage"][-1] == {"element_id": "P", "state": "retained_unreviewed"}
    assert not overlay["semantic_accepted"] and not overlay["publication_allowed"]
    overlay["elements"][0]["text"] = "mutation"
    assert p == before


@pytest.mark.parametrize("mutation", ["missing_task", "duplicate_task", "foreign_id", "self_link",
                                    "rewrite", "omit_body", "wrong_source", "extra_units"])
def test_reject_unsafe_proposals(mutation):
    p, r = fixture()
    if mutation == "missing_task": r["decisions"] = []
    if mutation == "duplicate_task": r["decisions"] *= 2
    if mutation == "foreign_id": r["decisions"][0]["links"][0]["target_id"] = "OTHER:T"
    if mutation == "self_link": r["decisions"][0]["links"][0]["support_ids"] = ["T"]
    if mutation == "rewrite": r["decisions"][0]["text"] = "Cash is 100"
    if mutation == "omit_body": r["decisions"][0]["links"][0]["support_ids"] = ["H"]
    if mutation == "wrong_source": p["elements"][0]["text"] = "Cash (thousands)"
    if mutation == "extra_units": r["units"] = []
    with pytest.raises(ContractError): validate_delta(p, r)


def test_unresolved_retains_source_and_does_not_become_reviewed():
    p, r = fixture()
    r["decisions"] = [dict(task_id="foot", status="unresolved", reason="Referenced table absent")]
    overlay = validate_delta(p, r)
    assert overlay["elements"] == p["elements"]
    assert all(x["state"] == "retained_unreviewed" for x in overlay["coverage"])
    assert len(overlay["unresolved"]) == 1


@pytest.mark.parametrize("groups,valid", [([["H"], ["F"]], True),
                                        ([["H"]], False), ([["F"], ["H"]], False),
                                        ([["H", "F"], ["F"]], False)])
def test_partition_is_local_ordered_and_lossless(groups, valid):
    p, r = fixture()
    p["tasks"] = [dict(task_id="paragraph", kind="partition", scope_ids=["H", "F"])]
    r["packet_digest"] = digest(p)
    r["decisions"] = [dict(task_id="paragraph", status="proposed", groups=groups)]
    if valid:
        assert validate_delta(p, r)["elements"] == p["elements"]
    else:
        with pytest.raises(ContractError): validate_delta(p, r)


@pytest.mark.parametrize("groups,valid", [([["H", "F"]], True), ([["H"], ["F"]], False)])
def test_source_confirmed_heading_attachment_must_survive_partition(groups, valid):
    p, r = fixture()
    p["tasks"] = [dict(task_id="paragraph", kind="partition", scope_ids=["H", "F"],
                      keep_together=[["H", "F"]])]
    r["packet_digest"] = digest(p)
    r["decisions"] = [dict(task_id="paragraph", status="proposed", groups=groups)]
    if valid:
        assert validate_delta(p, r)["elements"] == p["elements"]
    else:
        with pytest.raises(ContractError, match="heading/body"): validate_delta(p, r)
