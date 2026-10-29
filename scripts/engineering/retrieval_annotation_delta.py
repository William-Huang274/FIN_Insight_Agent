"""Validate source-bound annotation proposals without rewriting source ownership.

Offline qualification only. The returned overlay is pending human review, never
an accepted chunk catalog or an authorization to publish an index.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json


class ContractError(ValueError):
    """A proposal cannot be safely attached to this immutable packet."""


def digest(value: dict) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _ids(value: list, allowed: set, label: str) -> list:
    _check(isinstance(value, list) and bool(value), f"{label}: empty or invalid IDs")
    _check(all(isinstance(x, str) for x in value), f"{label}: non-string ID")
    _check(len(set(value)) == len(value), f"{label}: duplicate IDs")
    _check(set(value) <= allowed, f"{label}: out-of-scope ID")
    return value


def validate_delta(packet: dict, result: dict) -> dict:
    """Return a separate pending overlay; preserve every original source element.

    Tasks are operator-prepared source scopes, not model-generated instructions.
    Content sufficiency and semantic correctness require a separate review.
    """
    _check(packet.get("schema") == "retrieval-annotation-packet.v2", "packet schema")
    _check(set(result) == {"packet_id", "packet_digest", "decisions"}, "result fields")
    _check(result["packet_id"] == packet["packet_id"], "packet identity")
    _check(result["packet_digest"] == digest(packet), "packet digest mismatch")
    elements = packet["elements"]
    element_ids = [e["id"] for e in elements]
    _check(len(set(element_ids)) == len(element_ids), "duplicate source elements")
    by_id = {e["id"]: e for e in elements}
    positions = {eid: i for i, eid in enumerate(element_ids)}
    last_end = -1
    for e in elements:
        _check(isinstance(e["text"], str) and type(e["start"]) is int
               and type(e["end"]) is int, "invalid source element")
        _check(e["start"] >= last_end and e["end"] - e["start"] == len(e["text"]),
               "source coordinates")
        last_end = e["end"]
    tasks = packet["tasks"]
    _check(len({t["task_id"] for t in tasks}) == len(tasks), "duplicate input tasks")
    decisions = result["decisions"]
    _check(isinstance(decisions, list), "decisions must be a list")
    _check(len(decisions) == len(tasks), "missing or extra decisions")
    _check(len({d["task_id"] for d in decisions}) == len(decisions), "duplicate decisions")
    by_task = {t["task_id"]: t for t in tasks}
    _check({d["task_id"] for d in decisions} == set(by_task), "decision task mismatch")
    proposed = []
    touched: set[str] = set()
    unresolved = []
    for d in decisions:
        task = by_task[d["task_id"]]
        kind = task["kind"]
        _check(kind in {"footnote", "context", "partition"}, "unknown task kind")
        scope = _ids(task["scope_ids"], set(by_id), "task scope")
        _check(scope == sorted(scope, key=positions.get), "unordered task scope")
        if d.get("status") == "unresolved":
            _check(set(d) == {"task_id", "status", "reason"}, "unresolved fields")
            _check(isinstance(d["reason"], str) and 0 < len(d["reason"].strip()) <= 600,
                   "missing or excessive unresolved reason")
            unresolved.append(deepcopy(d))
            continue
        _check(d.get("status") == "proposed", "invalid decision status")
        if kind == "partition":
            _check(set(d) == {"task_id", "status", "groups"}, "partition fields")
            _check(isinstance(d["groups"], list) and bool(d["groups"]), "empty groups")
            flat = []
            for group in d["groups"]:
                flat.extend(_ids(group, set(scope), "partition group"))
            _check(flat == scope, "partition must preserve ordered exact coverage")
            ownership = {eid: i for i, group in enumerate(d["groups"]) for eid in group}
            for joined in task.get("keep_together", []):
                joined = _ids(joined, set(scope), "protected source grouping")
                _check(len({ownership[eid] for eid in joined}) == 1,
                       "partition separates source-confirmed heading/body")
            touched.update(scope)
        else:
            _check(set(d) == {"task_id", "status", "links"}, "link fields")
            _check(isinstance(d["links"], list) and bool(d["links"]), "empty links")
            allowed_targets = set(_ids(task["target_ids"], set(scope), "task targets"))
            seen_targets = set()
            for link in d["links"]:
                _check(set(link) == {"support_ids", "target_id"}, "link fields")
                target = link["target_id"]
                _check(isinstance(target, str) and target in allowed_targets,
                       "link target outside task")
                _check(target not in seen_targets, "duplicate target")
                seen_targets.add(target)
                support = _ids(link["support_ids"], set(scope), "link support")
                _check(target not in support, "self link")
                _check(all(by_id[e]["kind"] != "table" for e in support),
                       "table cannot masquerade as caption/footnote")
                _check(by_id[target]["kind"] == "table", "target is not table")
                _check(support == sorted(support, key=positions.get), "unordered support")
                if kind == "footnote":
                    _check(support == task["support_ids"], "footnote body changed")
                touched.update(support)
                touched.add(target)
        proposed.append(deepcopy(d))
    return {
        "schema": "retrieval-annotation-overlay.v2",
        "packet_id": packet["packet_id"], "packet_digest": digest(packet),
        "source": deepcopy(packet["source"]),
        "elements": deepcopy(elements),
        "coverage": [{"element_id": eid, "state": "proposal_pending_review"
                      if eid in touched else "retained_unreviewed"} for eid in element_ids],
        "proposals": proposed, "unresolved": unresolved,
        "semantic_accepted": False, "publication_allowed": False,
    }
