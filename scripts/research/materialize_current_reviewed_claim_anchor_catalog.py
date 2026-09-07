from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_REF = Path(
    "configs/runtime/fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json"
)
PROJECTION_CONFIG_REF = Path(
    "configs/runtime/fin_ia_0_1_3_current_research_evidence_pack_projection_v1_0.json"
)
DECISIONS_REF = Path(
    "configs/research/fin_ia_0_1_3_current_reviewed_claim_anchor_decisions_v1_0.json"
)
DEFAULT_OUTPUT_REF = Path(
    "configs/runtime/fin_ia_0_1_3_current_reviewed_claim_anchor_catalog_v1_0.json"
)
CATALOG_SCHEMA = "fin_ia_reviewed_evidence_anchor_catalog_v1_0"
CATALOG_STATUS = "reviewed_claim_surfaces_bound_to_current_evidence_items"


class AnchorMaterializationError(RuntimeError):
    pass


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AnchorMaterializationError(f"json_not_mapping:{path}")
    return value


def _canonical_digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _resource_path(resource_id: str) -> Path:
    registry = _json(ROOT / REGISTRY_REF)
    row = next(
        (
            item
            for item in registry.get("resources") or ()
            if item.get("resource_id") == resource_id
        ),
        None,
    )
    if not isinstance(row, Mapping):
        raise AnchorMaterializationError(f"runtime_resource_missing:{resource_id}")
    path = ROOT / str(row.get("repo_relative_path") or "")
    if not path.is_file():
        raise AnchorMaterializationError(f"runtime_resource_unavailable:{resource_id}")
    return path


def _safe_object_path(root: Path, object_key: str) -> Path:
    relative = PurePosixPath(object_key)
    if relative.is_absolute() or "\\" in object_key or ".." in relative.parts:
        raise AnchorMaterializationError("pack_object_key_invalid")
    path = root.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise AnchorMaterializationError("pack_object_escape") from exc
    if not path.is_file():
        raise AnchorMaterializationError(f"pack_object_unavailable:{object_key}")
    return path


def _current_packs() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    config = _json(ROOT / PROJECTION_CONFIG_REF)
    result = _json(_resource_path(str(config["source_result_resource_id"])))
    base = (ROOT / "data/workbench_private").resolve()
    default_root = (
        base / str(config["private_object_root_relative"])
    ).resolve()
    packs: dict[str, dict[str, Any]] = {}
    for case_key in config["published_case_keys"]:
        artifact = result["pack_artifacts"][case_key]
        override = str(artifact.get("private_object_root_relative") or "")
        object_root = (base / override).resolve() if override else default_root
        path = _safe_object_path(object_root, str(artifact["object_key"]))
        raw = path.read_bytes()
        if (
            hashlib.sha256(raw).hexdigest() != artifact["digest"]
            or len(raw) != int(artifact["byte_size"])
        ):
            raise AnchorMaterializationError(f"pack_artifact_drift:{case_key}")
        pack = json.loads(raw.decode("utf-8"))
        if (
            pack.get("case_key") != case_key
            or pack.get("pack_payload_digest")
            != result["pack_payload_digests"][case_key]
        ):
            raise AnchorMaterializationError(f"pack_binding_drift:{case_key}")
        packs[case_key] = pack
    return result, packs


def _structured_claims(
    path: Path,
    target_ids: set[str],
) -> dict[str, str]:
    values: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if "_CLAIM_" not in line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            target_id = str(row.get("object_id") or "")
            if target_id not in target_ids:
                continue
            claim_text = str(row.get("claim_text") or "")
            if not claim_text:
                raise AnchorMaterializationError(
                    f"structured_claim_text_missing:{target_id}"
                )
            values[target_id] = claim_text
            if set(values) == target_ids:
                break
    return values


def compile_catalog() -> dict[str, Any]:
    decisions = _json(ROOT / DECISIONS_REF)
    if not (
        decisions.get("schema_version")
        == "fin_ia_reviewed_claim_anchor_decisions_v1_0"
        and decisions.get("status")
        == "reviewed_manual_overrides_for_non_structured_or_truncated_claims"
    ):
        raise AnchorMaterializationError("anchor_decisions_contract_invalid")
    manual = {
        str(row["target_id"]): str(row["anchor_text"])
        for row in decisions["manual_anchors"]
    }
    if len(manual) != len(decisions["manual_anchors"]):
        raise AnchorMaterializationError("manual_anchor_duplicate")

    result, packs = _current_packs()
    claim_target_ids = {
        str(item["target_id"])
        for pack in packs.values()
        for item in pack["evidence_items"]
        if item.get("object_type") == "claim"
    }
    structured_target_ids = claim_target_ids - set(manual)
    structured_path = ROOT / str(decisions["structured_claim_catalog_ref"])
    structured = _structured_claims(structured_path, structured_target_ids)
    missing = structured_target_ids - set(structured)
    if missing:
        raise AnchorMaterializationError(
            "structured_claim_targets_missing:" + ",".join(sorted(missing))
        )
    unused_manual = set(manual) - claim_target_ids
    if unused_manual:
        raise AnchorMaterializationError(
            "manual_anchor_targets_unused:" + ",".join(sorted(unused_manual))
        )

    bindings: dict[str, dict[str, str]] = {}
    entries: list[dict[str, Any]] = []
    for case_key in sorted(packs):
        pack = packs[case_key]
        artifact = result["pack_artifacts"][case_key]
        bindings[case_key] = {
            "artifact_digest": str(artifact["digest"]),
            "pack_payload_digest": str(pack["pack_payload_digest"]),
        }
        materials = {
            str(row["material_ref"]): row for row in pack["source_materials"]
        }
        for item in pack["evidence_items"]:
            if item.get("object_type") != "claim":
                continue
            target_id = str(item["target_id"])
            source = materials[str(item["source_material_ref"])]
            source_text = str(source["source_text"])
            anchor_text = (
                manual[target_id]
                if target_id in manual
                else structured[target_id]
            )
            if not 24 <= len(anchor_text) <= 800:
                raise AnchorMaterializationError(
                    f"claim_anchor_capacity_invalid:{case_key}:{target_id}"
                )
            occurrences = source_text.count(anchor_text)
            if occurrences != 1:
                raise AnchorMaterializationError(
                    f"claim_anchor_occurrence_invalid:{case_key}:{target_id}:{occurrences}"
                )
            start = source_text.index(anchor_text)
            entries.append(
                {
                    "case_key": case_key,
                    "target_id": target_id,
                    "source_record_id": str(item["source_record_id"]),
                    "evidence_item_digest": str(item["evidence_item_digest"]),
                    "source_text_digest": str(source["source_text_digest"]),
                    "anchor_kind": (
                        "reviewed_current_document_passage"
                        if target_id in manual
                        else "structured_claim_text"
                    ),
                    "anchor_text": anchor_text,
                    "anchor_start": start,
                    "anchor_end": start + len(anchor_text),
                    "anchor_digest": _sha256_text(anchor_text),
                    "review_status": "reviewed_exact_source_surface",
                }
            )
    entries.sort(key=lambda row: (row["case_key"], row["target_id"]))
    body = {
        "schema_version": CATALOG_SCHEMA,
        "status": CATALOG_STATUS,
        "case_pack_bindings": bindings,
        "entries": entries,
        "authority": {
            "anchor_is_verbatim_source_substring": True,
            "anchor_is_not_new_evidence": True,
            "reviewer_business_meaning_is_not_source_text": True,
            "generic_prefix_may_not_replace_claim_anchor": True,
            "claim_anchor_binding_fails_closed": True,
            "model_or_network_calls": 0,
        },
        "known_boundary": (
            "This catalog binds exact source-visible surfaces for every reviewed "
            "claim object in the current DELL, MU and NVDA packs. Long source_segment "
            "objects still use bounded document-prefix projection and require a "
            "separate reviewed passage contract before they may be treated as "
            "claim-level training or causal authority."
        ),
    }
    return {**body, "catalog_digest": _canonical_digest(body)}


def _render(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / DEFAULT_OUTPUT_REF)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = compile_catalog()
    rendered = _render(payload)
    output = args.output.resolve()
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
            raise AnchorMaterializationError("reviewed_anchor_catalog_drift")
        print(
            json.dumps(
                {
                    "status": "reviewed_anchor_catalog_current",
                    "entries": len(payload["entries"]),
                    "catalog_digest": payload["catalog_digest"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": "reviewed_anchor_catalog_materialized",
                "output": output.relative_to(ROOT).as_posix(),
                "entries": len(payload["entries"]),
                "catalog_digest": payload["catalog_digest"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
