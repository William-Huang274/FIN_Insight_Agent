"""Operator-reviewed source roles and durable, task-scoped annotation reuse.

Local qualification artifacts only: these records neither grant source access
nor publish chunks. A model proposal cannot self-approve by supplying a role.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sqlite3


def _hash(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf8")).hexdigest()


def source_anchor(packet: dict, element: dict) -> dict:
    source = packet["source"]
    if not source.get("source_digest") or not source.get("coordinate_space"):
        raise ValueError("source identity and coordinate space required")
    return {"source_digest": source["source_digest"],
            "coordinate_space": source["coordinate_space"],
            "original_node_id": source.get("original_node_id"),
            "start": element["start"], "end": element["end"],
            "text_sha256": sha256(element["text"].encode("utf8")).hexdigest()}


def reviewed_role(packet: dict, element_id: str, role: str, *, reviewer: str,
                  reason: str) -> dict:
    """Create an operator decision AFTER reading the source, not a classifier."""
    if role not in {"data_table", "layout_caption", "unknown"}:
        raise ValueError("unsupported source role")
    if not reviewer.strip() or not reason.strip():
        raise ValueError("reviewer and source-based reason required")
    element = next(e for e in packet["elements"] if e["id"] == element_id)
    if element["kind"] != "table":
        raise ValueError("physical table required")
    body = {"schema": "source-role-review.v1", "anchor": source_anchor(packet, element),
            "role": role, "reviewer": reviewer, "reason": reason}
    return {**body, "review_id": _hash(body)}


def verified_role(packet: dict, element: dict, trusted_reviews: dict) -> str:
    ref = packet.get("source_role_refs", {}).get(element["id"])
    if ref is None:
        return "unknown"
    if packet.get("schema") != "retrieval-annotation-packet.v3":
        raise ValueError("source roles require v3 packet")
    review = trusted_reviews.get(ref)
    if review is None:
        raise ValueError("role reference is not in trusted review store")
    body = {k: v for k, v in review.items() if k != "review_id"}
    if review.get("review_id") != ref or _hash(body) != ref:
        raise ValueError("role review changed")
    if review.get("schema") != "source-role-review.v1" or review.get("anchor") != source_anchor(packet, element):
        raise ValueError("role source binding changed")
    if review.get("role") not in {"data_table", "layout_caption", "unknown"}:
        raise ValueError("unsupported trusted role")
    return review["role"]


def implementation_digest() -> str:
    root = Path(__file__).parent
    return _hash({name: sha256((root/name).read_bytes()).hexdigest() for name in
                  ["retrieval_annotation_delta.py", "retrieval_annotation_reviews.py"]})


def task_input_key(packet: dict, task_id: str) -> str:
    task = next(t for t in packet["tasks"] if t["task_id"] == task_id)
    scope = set(task["scope_ids"])
    return _hash({"schema": packet["schema"],
                  "source": packet["source"], "task": task,
                  "elements": [e for e in packet["elements"] if e["id"] in scope],
                  "role_refs": {k: v for k, v in packet.get("source_role_refs", {}).items() if k in scope}})


def task_key(packet: dict, task_id: str) -> str:
    return _hash({"implementation": implementation_digest(),
                  "input_key": task_input_key(packet, task_id)})


class AnnotationReviewStore:
    """SQLite's transactions preserve accepted records; conflicts never overwrite."""
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS reviews(kind TEXT, key TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind,key))")
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def _put(self, kind: str, key: str, record: dict) -> None:
        payload = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO reviews VALUES(?,?,?)", (kind, key, payload))
            existing = self.db.execute("SELECT payload FROM reviews WHERE kind=? AND key=?", (kind, key)).fetchone()[0]
            if existing != payload:
                raise ValueError("conflicting reviewed record; original retained")

    def add_role(self, review: dict) -> None:
        body = {k: v for k, v in review.items() if k != "review_id"}
        if _hash(body) != review.get("review_id"):
            raise ValueError("invalid role receipt")
        self._put("role", review["review_id"], review)

    def roles(self) -> dict:
        return {key: json.loads(payload) for key, payload in
                self.db.execute("SELECT key,payload FROM reviews WHERE kind='role'")}

    def accept(self, packet: dict, result: dict, task_id: str, *, reviewer: str,
               reason: str) -> str:
        from scripts.engineering.retrieval_annotation_delta import digest, validate_delta
        # Preserve the original response binding, but validate this task alone:
        # another rejected task must not discard an independently reviewed fix.
        if (set(result) != {"packet_id", "packet_digest", "decisions"}
                or result["packet_id"] != packet["packet_id"]
                or result["packet_digest"] != digest(packet)):
            raise ValueError("original response binding mismatch")
        supplied = [d["task_id"] for d in result["decisions"]]
        expected = [t["task_id"] for t in packet["tasks"]]
        if (len(set(supplied)) != len(supplied) or len(set(expected)) != len(expected)
                or set(supplied) != set(expected) or task_id not in expected):
            raise ValueError("original task inventory mismatch")
        decision = next(d for d in result["decisions"] if d["task_id"] == task_id)
        isolated = deepcopy(packet)
        isolated["tasks"] = [t for t in packet["tasks"] if t["task_id"] == task_id]
        validate_delta(isolated, {"packet_id": packet["packet_id"], "packet_digest": digest(isolated),
                                  "decisions": [decision]}, trusted_roles=self.roles())
        if decision["status"] != "proposed" or not reviewer.strip() or not reason.strip():
            raise ValueError("only explicitly reviewed proposals can be accepted")
        key = task_key(packet, task_id)
        self._put("decision", key, {"key": key, "input_key": task_input_key(packet, task_id),
                                   "implementation": implementation_digest(),
                                   "decision": decision, "reviewer": reviewer,
                                   "reason": reason, "decision_digest": _hash(decision)})
        return key

    def reuse(self, packet: dict, task_id: str) -> dict | None:
        from scripts.engineering.retrieval_annotation_delta import digest, validate_delta
        key = task_key(packet, task_id)
        row = self.db.execute("SELECT payload FROM reviews WHERE kind='decision' AND key=?", (key,)).fetchone()
        if row is None:
            return None
        record = json.loads(row[0])
        if record.get("key") != key or _hash(record["decision"]) != record.get("decision_digest"):
            raise ValueError("accepted decision record changed")
        isolated = deepcopy(packet)
        isolated["tasks"] = [t for t in packet["tasks"] if t["task_id"] == task_id]
        validate_delta(isolated, {"packet_id": isolated["packet_id"], "packet_digest": digest(isolated),
                                 "decisions": [record["decision"]]}, trusted_roles=self.roles())
        return deepcopy(record["decision"])

    def prior_candidates(self, packet: dict, task_id: str) -> list[dict]:
        """Same input under older policies: evidence for review, never auto-reuse."""
        rows = self.db.execute("SELECT payload FROM reviews WHERE kind='decision' "
                               "AND json_extract(payload,'$.input_key')=?",
                               (task_input_key(packet, task_id),)).fetchall()
        return [json.loads(row[0]) for row in rows]
