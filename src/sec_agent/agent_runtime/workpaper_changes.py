"""Mechanical version/position records; never infer that a finding is resolved."""
from copy import deepcopy
from difflib import SequenceMatcher

from .research_graph_contracts import canonical_sha256


FIELDS = ("thesis", "mechanism", "narrative_markdown", "counterevidence", "what_would_change", "open_gaps", "task_note")


def workpaper_changes(before, after):
    old = {c["claim_id"]: c for c in before.get("claims", [])}
    new = {c["claim_id"]: c for c in after.get("claims", [])}
    changed = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
    locations = []
    for field in FIELDS:
        left, right = before.get(field), after.get(field)
        if left == right:
            continue
        row = {"path": "/" + field, "before_digest": canonical_sha256(left), "after_digest": canonical_sha256(right)}
        if isinstance(left, str) and isinstance(right, str):
            row["spans"] = [{"before": [a, b], "after": [c, d]} for op, a, b, c, d in
                SequenceMatcher(None, left, right, autojunk=False).get_opcodes() if op != "equal"]
        locations.append(row)
    return {"baseline_digest": canonical_sha256(before), "current_digest": canonical_sha256(after),
        "changed_claim_ids": changed, "locations": locations,
        "semantic_status": "not_independently_verified",
        "notice": "Runtime-observed changes only. Read the current full field and related source/claim bindings before judgment; offsets are navigation, not isolated review scope."}


def paper_versions(artifacts):
    return {p["paper_id"]: canonical_sha256(artifacts.read_paper(p["paper_id"])) for p in artifacts.catalog()["papers"]}


def confirmation_context(artifacts, revisions, feedback):
    current = artifacts.with_revisions(revisions)
    return {"paper_version_digests": paper_versions(current), "findings_to_confirm": deepcopy(feedback),
        "changes": {pid: workpaper_changes(artifacts.read_paper(pid), current.read_paper(pid)) for pid in revisions},
        "author_responses": {pid: deepcopy(row.get("finding_responses", [])) for pid, row in revisions.items()},
        "instruction": "Independently check each assigned finding against current workpaper and original sources. Author responses are claims, not closure. Inspect changed text, citation bindings and consequential related explanations; reuse unchanged research. Record newly introduced issues together. Necessary unchecked dependencies mean incomplete. Do not infer absence from a failed or incomplete read."}
