from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.canonical_runtime.session import canonical_digest  # noqa: E402
from sec_agent.research.reviewed_evidence_anchor import (  # noqa: E402
    compile_reviewed_evidence_anchor_catalog,
)


PROGRAM_SCHEMA = "fin_ia_reviewed_anchor_catalog_successor_program_v1_0"
PROGRAM_STATUS = "approved_zero_call_reviewed_anchor_catalog_successor"
DEFAULT_PROGRAM = (
    "configs/research/"
    "fin_ia_0_1_3_s1_dell_direct_source_anchor_successor_program_v1_0.json"
)
DEFAULT_OUTPUT = (
    "configs/runtime/"
    "fin_ia_0_1_3_current_reviewed_claim_anchor_catalog_v1_6.json"
)


class AnchorCatalogSuccessorError(ValueError):
    """Raised when a reviewed anchor successor is not lineage-complete."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise AnchorCatalogSuccessorError(code)


def _mapping(value: object, code: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), code)
    return deepcopy(dict(value))


def _rows(value: object, code: str) -> list[dict[str, Any]]:
    _require(isinstance(value, list), code)
    return [_mapping(row, code) for row in value]


def _strings(value: object, code: str, *, allow_empty: bool = False) -> list[str]:
    _require(isinstance(value, list), code)
    rows = [str(row).strip() for row in value]
    _require(
        (allow_empty or bool(rows))
        and all(rows)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compile_anchor_catalog_successor(
    *,
    program: Mapping[str, Any],
    predecessor_catalog: Mapping[str, Any],
    target_pack: Mapping[str, Any],
    target_pack_artifact_digest: str,
) -> dict[str, Any]:
    payload = deepcopy(dict(program))
    _require(
        payload.get("schema_version") == PROGRAM_SCHEMA
        and payload.get("status") == PROGRAM_STATUS,
        "anchor_successor_program_header_invalid",
    )
    case_key = str(payload.get("case_key") or "").upper()
    _require(
        case_key
        and str(target_pack.get("case_key") or "").upper() == case_key,
        "anchor_successor_case_mismatch",
    )
    predecessor_binding = _mapping(
        payload.get("predecessor_catalog_binding"),
        "anchor_successor_predecessor_binding_missing",
    )
    _require(
        str(predecessor_catalog.get("catalog_digest") or "")
        == str(predecessor_binding.get("catalog_digest") or "")
        and canonical_digest(
            {
                key: value
                for key, value in dict(predecessor_catalog).items()
                if key != "catalog_digest"
            }
        )
        == str(predecessor_catalog.get("catalog_digest") or ""),
        "anchor_successor_predecessor_catalog_digest_invalid",
    )
    target_binding = _mapping(
        payload.get("target_pack_binding"),
        "anchor_successor_target_binding_missing",
    )
    target_payload_digest = str(target_pack.get("pack_payload_digest") or "")
    _require(
        target_payload_digest
        and target_payload_digest
        == str(target_binding.get("pack_payload_digest") or "")
        and str(target_pack_artifact_digest)
        == str(target_binding.get("artifact_digest") or ""),
        "anchor_successor_target_pack_binding_invalid",
    )

    target_items: dict[str, dict[str, Any]] = {}
    for raw in target_pack.get("evidence_items") or ():
        item = _mapping(raw, "anchor_successor_pack_item_invalid")
        if item.get("object_type") != "claim":
            continue
        digest = str(item.get("evidence_item_digest") or "")
        _require(
            digest and digest not in target_items,
            "anchor_successor_pack_evidence_digest_invalid",
        )
        target_items[digest] = item
    _require(target_items, "anchor_successor_target_claims_empty")

    predecessor_entries = _rows(
        predecessor_catalog.get("entries"),
        "anchor_successor_predecessor_entries_invalid",
    )
    predecessor_case_entries: dict[str, dict[str, Any]] = {}
    for entry in predecessor_entries:
        if str(entry.get("case_key") or "").upper() != case_key:
            continue
        digest = str(entry.get("evidence_item_digest") or "")
        _require(
            digest and digest not in predecessor_case_entries,
            "anchor_successor_predecessor_case_digest_invalid",
        )
        predecessor_case_entries[digest] = entry

    target_digests = set(target_items)
    predecessor_digests = set(predecessor_case_entries)
    new_digests = target_digests - predecessor_digests
    removed_digests = predecessor_digests - target_digests
    expected_removed = set(
        _strings(
            payload.get("expected_removed_evidence_item_digests") or [],
            "anchor_successor_expected_removed_invalid",
            allow_empty=True,
        )
    )
    _require(
        removed_digests == expected_removed,
        "anchor_successor_removed_evidence_set_mismatch",
    )

    decisions = _rows(
        payload.get("new_anchor_decisions"),
        "anchor_successor_decisions_invalid",
    )
    decisions_by_digest = {
        str(row.get("evidence_item_digest") or ""): row for row in decisions
    }
    _require(
        len(decisions_by_digest) == len(decisions)
        and set(decisions_by_digest) == new_digests,
        "anchor_successor_new_evidence_not_exhaustively_decided",
    )
    materials = {
        str(row.get("material_ref") or ""): _mapping(
            row, "anchor_successor_material_invalid"
        )
        for row in target_pack.get("source_materials") or ()
        if isinstance(row, Mapping)
    }

    new_entries: list[dict[str, Any]] = []
    for digest in sorted(new_digests):
        item = target_items[digest]
        decision = decisions_by_digest[digest]
        _require(
            str(decision.get("target_id") or "") == str(item.get("target_id") or "")
            and str(decision.get("source_record_id") or "")
            == str(item.get("source_record_id") or ""),
            "anchor_successor_decision_identity_mismatch",
        )
        material = materials.get(str(item.get("source_material_ref") or ""))
        _require(material is not None, "anchor_successor_source_material_missing")
        source_text = str(material.get("source_text") or "")
        anchor_text = str(decision.get("anchor_text") or "")
        _require(
            24 <= len(anchor_text) <= 800
            and source_text.count(anchor_text) == 1,
            "anchor_successor_anchor_surface_invalid",
        )
        start = source_text.index(anchor_text)
        new_entries.append(
            {
                "case_key": case_key,
                "target_id": str(item.get("target_id") or ""),
                "source_record_id": str(item.get("source_record_id") or ""),
                "evidence_item_digest": digest,
                "source_text_digest": str(material.get("source_text_digest") or ""),
                "anchor_kind": "reviewed_current_document_passage",
                "anchor_text": anchor_text,
                "anchor_start": start,
                "anchor_end": start + len(anchor_text),
                "anchor_digest": _sha256_text(anchor_text),
                "review_status": "reviewed_exact_source_surface",
            }
        )

    kept_entries = [
        entry
        for entry in predecessor_entries
        if str(entry.get("case_key") or "").upper() != case_key
        or str(entry.get("evidence_item_digest") or "") in target_digests
    ]
    entries = [*kept_entries, *new_entries]
    entries.sort(key=lambda row: (str(row["case_key"]), str(row["target_id"])))
    _require(
        len(entries) == len({
            (str(row["case_key"]), str(row["evidence_item_digest"]))
            for row in entries
        }),
        "anchor_successor_entry_identity_duplicate",
    )

    bindings = deepcopy(dict(predecessor_catalog.get("case_pack_bindings") or {}))
    _require(case_key in bindings, "anchor_successor_case_binding_missing")
    bindings[case_key] = {
        "artifact_digest": str(target_pack_artifact_digest),
        "pack_payload_digest": target_payload_digest,
    }
    catalog = compile_reviewed_evidence_anchor_catalog(
        case_pack_bindings=bindings,
        entries=entries,
        known_boundary=str(payload.get("known_boundary") or ""),
    )
    unsigned = {
        "schema_version": "fin_ia_reviewed_anchor_catalog_successor_result_v1_0",
        "status": "reviewed_anchor_catalog_successor_compiled",
        "case_key": case_key,
        "predecessor_catalog_digest": predecessor_catalog.get("catalog_digest"),
        "target_pack_payload_digest": target_payload_digest,
        "new_evidence_item_digests": sorted(new_digests),
        "removed_evidence_item_digests": sorted(removed_digests),
        "predecessor_entry_count": len(predecessor_entries),
        "successor_entry_count": len(entries),
        "catalog": catalog,
        "authority": {
            "new_evidence_created": False,
            "numeric_authority_granted": False,
            "candidate_text_promoted": False,
            "model_or_network_calls": 0,
        },
    }
    return {**unsigned, "successor_digest": canonical_digest(unsigned)}


def _resolve(ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AnchorCatalogSuccessorError(
            f"anchor_successor_json_object_required:{path.name}"
        )
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--program", default=DEFAULT_PROGRAM)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if _git_output("status", "--porcelain"):
        raise RuntimeError("anchor_successor_clean_worktree_required")
    program_path = _resolve(args.program)
    program = _json(program_path)
    predecessor_binding = _mapping(
        program.get("predecessor_catalog_binding"),
        "anchor_successor_predecessor_binding_missing",
    )
    target_binding = _mapping(
        program.get("target_pack_binding"),
        "anchor_successor_target_binding_missing",
    )
    predecessor_path = _resolve(str(predecessor_binding.get("ref") or ""))
    target_path = _resolve(str(target_binding.get("ref") or ""))
    _require(
        _relative(predecessor_path) == predecessor_binding.get("ref")
        and _sha256(predecessor_path) == predecessor_binding.get("sha256"),
        "anchor_successor_predecessor_file_binding_invalid",
    )
    _require(
        _relative(target_path) == target_binding.get("ref")
        and _sha256(target_path) == target_binding.get("artifact_digest"),
        "anchor_successor_target_file_binding_invalid",
    )
    result = compile_anchor_catalog_successor(
        program=program,
        predecessor_catalog=_json(predecessor_path),
        target_pack=_json(target_path),
        target_pack_artifact_digest=_sha256(target_path),
    )
    output = _resolve(args.output)
    if output.exists():
        raise FileExistsError(f"anchor_successor_output_exists:{_relative(output)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result["catalog"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "prepared_from_commit": _git_output("rev-parse", "HEAD"),
                "new_evidence_item_count": len(result["new_evidence_item_digests"]),
                "removed_evidence_item_count": len(
                    result["removed_evidence_item_digests"]
                ),
                "successor_entry_count": result["successor_entry_count"],
                "catalog_digest": result["catalog"]["catalog_digest"],
                "output": _relative(output),
                "successor_digest": result["successor_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
