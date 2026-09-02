from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ingestion.structured_document_adapter import (  # noqa: E402
    StructuredDocumentError,
    StructuredSourceDescriptor,
    build_structured_document_tree,
)


RESULT_SCHEMA = "fin_ia_dell_structured_rag_slice_result_v1_0"


class StructuredSliceMaterializationError(ValueError):
    """Frozen input or output constraints were violated."""


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StructuredSliceMaterializationError(
            f"{label}_json_invalid:{path}"
        ) from exc
    if not isinstance(value, dict):
        raise StructuredSliceMaterializationError(f"{label}_shape_invalid:{path}")
    return value


def _require_file(path: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise StructuredSliceMaterializationError(f"{label}_unavailable:{resolved}")
    return resolved


def _load_plan(path: Path) -> dict[str, Any]:
    value = _read_json(_require_file(path, label="plan"), label="plan")
    if value.get("schema_version") != "fin_ia_dell_structured_rag_slice_plan_v1_0":
        raise StructuredSliceMaterializationError("structured_slice_plan_schema_invalid")
    profiles = value.get("parser_profiles")
    generic = value.get("generic_chunking")
    sec_chunking = value.get("sec_chunking")
    if (
        not isinstance(profiles, Mapping)
        or not isinstance(generic, Mapping)
        or not isinstance(sec_chunking, Mapping)
    ):
        raise StructuredSliceMaterializationError("structured_slice_plan_contract_invalid")
    return value


def _attempt_sources(
    attempt_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    root = attempt_root.expanduser().resolve()
    config_path = _require_file(root / "input_config.json", label="attempt_config")
    manifest_path = _require_file(root / "manifest.json", label="attempt_manifest")
    config = _read_json(config_path, label="attempt_config")
    manifest = _read_json(manifest_path, label="attempt_manifest")
    capture_plan = config.get("capture_plan")
    declared = capture_plan.get("sources") if isinstance(capture_plan, Mapping) else None
    observed = manifest.get("sources")
    if not isinstance(declared, list) or not isinstance(observed, list):
        raise StructuredSliceMaterializationError("attempt_source_contract_invalid")
    return declared, observed, {
        "attempt_root": root.as_posix(),
        "input_config_path": config_path.as_posix(),
        "input_config_sha256": _sha256_file(config_path),
        "manifest_path": manifest_path.as_posix(),
        "manifest_sha256": _sha256_file(manifest_path),
    }


def _parser_profile(plan: Mapping[str, Any], source: Mapping[str, Any]) -> str:
    profiles = plan["parser_profiles"]
    route_overrides = profiles.get("route_overrides")
    defaults = profiles.get("defaults")
    route_id = str(source.get("route_id") or "")
    if isinstance(route_overrides, Mapping) and route_id in route_overrides:
        return str(route_overrides[route_id])
    kind = str(source.get("document_kind") or "")
    if not isinstance(defaults, Mapping) or kind not in defaults:
        raise StructuredSliceMaterializationError(
            f"parser_profile_missing:{route_id}"
        )
    return str(defaults[kind])


def _git_binding() -> dict[str, str]:
    def run(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=REPOSITORY_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        return completed.stdout.strip()

    return {
        "branch": run("branch", "--show-current"),
        "commit": run("rev-parse", "HEAD"),
        "tree": run("write-tree"),
    }


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    payload = b"".join(_canonical_bytes(row) for row in rows)
    path.write_bytes(payload)
    return {
        "path": path.as_posix(),
        "sha256": _sha256_file(path),
        "record_count": len(rows),
        "bytes": len(payload),
    }


def _manual_review_queue(
    documents: Sequence[Mapping[str, Any]],
    chunks: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    by_route: dict[str, list[Mapping[str, Any]]] = {}
    for chunk in chunks:
        by_route.setdefault(str(chunk["route_id"]), []).append(chunk)
    for document in documents:
        route_id = str(document["route_id"])
        route_chunks = by_route.get(route_id, [])
        selected: list[Mapping[str, Any]] = []
        if route_chunks:
            selected.append(route_chunks[0])
        selected.extend(
            chunk
            for chunk in route_chunks
            if chunk.get("contains_table")
            and chunk not in selected
        )
        selected.extend(
            chunk
            for chunk in route_chunks
            if chunk.get("contains_image")
            and chunk not in selected
        )
        first_by_section: dict[str, Mapping[str, Any]] = {}
        for chunk in route_chunks:
            first_by_section.setdefault(str(chunk["parent_section_id"]), chunk)
        selected.extend(
            chunk for chunk in first_by_section.values() if chunk not in selected
        )
        for chunk in selected[:8]:
            queue.append(
                {
                    "route_id": route_id,
                    "chunk_id": chunk["chunk_id"],
                    "section_path": chunk["section_path"],
                    "page_start": chunk["page_start"],
                    "page_end": chunk["page_end"],
                    "contains_table": chunk["contains_table"],
                    "contains_image": chunk["contains_image"],
                    "review_state": "pending_human_file_and_chunk_review",
                }
            )
    return queue


def materialize_structured_slice(
    *,
    plan_path: Path,
    knowledge_attempt_roots: Sequence[Path],
    output_root: Path,
    attempt_id: str,
    supplemental_parent_paths: Mapping[str, Path] | None = None,
    supplemental_capture_paths: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    plan_path = _require_file(plan_path, label="plan")
    plan = _load_plan(plan_path)
    if not knowledge_attempt_roots:
        raise StructuredSliceMaterializationError("knowledge_attempt_roots_empty")
    if len(knowledge_attempt_roots) != int(plan["scope"]["input_attempt_count"]):
        raise StructuredSliceMaterializationError("knowledge_attempt_count_drift")

    declared_by_route: dict[str, dict[str, Any]] = {}
    observed_by_route: dict[str, dict[str, Any]] = {}
    input_attempts: list[dict[str, Any]] = []
    for attempt_root in knowledge_attempt_roots:
        declared, observed, binding = _attempt_sources(attempt_root)
        input_attempts.append(binding)
        for source in declared:
            if not isinstance(source, dict):
                raise StructuredSliceMaterializationError("declared_source_invalid")
            route_id = str(source.get("route_id") or "")
            if route_id in declared_by_route:
                raise StructuredSliceMaterializationError(
                    f"declared_route_duplicate:{route_id}"
                )
            declared_by_route[route_id] = source
        for source in observed:
            if not isinstance(source, dict):
                raise StructuredSliceMaterializationError("observed_source_invalid")
            route_id = str(source.get("route_id") or "")
            if route_id in observed_by_route:
                raise StructuredSliceMaterializationError(
                    f"observed_route_duplicate:{route_id}"
                )
            observed_by_route[route_id] = source

    if len(declared_by_route) > int(plan["scope"]["maximum_declared_sources"]):
        raise StructuredSliceMaterializationError("declared_source_ceiling_exceeded")
    if set(observed_by_route) != set(declared_by_route):
        raise StructuredSliceMaterializationError("declared_observed_route_drift")

    local_bodies: dict[str, tuple[Path, str, str]] = {}
    for route_id, observed in observed_by_route.items():
        if observed.get("status") != "parsed":
            continue
        body_path = _require_file(
            Path(str(observed.get("raw_body_path") or "")),
            label=f"raw_body:{route_id}",
        )
        expected_digest = str(observed.get("raw_body_sha256") or "").lower()
        if _sha256_file(body_path) != expected_digest:
            raise StructuredSliceMaterializationError(
                f"raw_body_digest_drift:{route_id}"
            )
        local_bodies[route_id] = (body_path, expected_digest, "current_capture")

    supplemental_bindings: list[dict[str, Any]] = []
    supplemental_parent_paths = dict(supplemental_parent_paths or {})
    supplemental_capture_paths = dict(supplemental_capture_paths or {})
    supplemental_by_route: dict[str, dict[str, Any]] = {}
    supplemental_specs = plan.get("supplemental_local_sources")
    if supplemental_specs:
        if not isinstance(supplemental_specs, list):
            raise StructuredSliceMaterializationError("supplemental_source_plan_invalid")
        for raw_spec in supplemental_specs:
            if not isinstance(raw_spec, dict):
                raise StructuredSliceMaterializationError(
                    "supplemental_source_plan_invalid"
                )
            spec = dict(raw_spec)
            route_id = str(spec.get("route_id") or "")
            if route_id in supplemental_by_route or route_id not in declared_by_route:
                raise StructuredSliceMaterializationError(
                    "supplemental_source_route_invalid"
                )
            if route_id not in supplemental_capture_paths:
                raise StructuredSliceMaterializationError(
                    f"supplemental_source_binding_missing:{route_id}"
                )
            supplemental_by_route[route_id] = spec
            capture_path = _require_file(
                supplemental_capture_paths[route_id],
                label=f"supplemental_capture:{route_id}",
            )
            expected_digest = str(
                spec.get("expected_capture_sha256") or ""
            ).lower()
            if _sha256_file(capture_path) != expected_digest:
                raise StructuredSliceMaterializationError(
                    f"supplemental_capture_digest_drift:{route_id}"
                )
            binding: dict[str, Any] = {
                "route_id": route_id,
                "source_url": spec.get("source_url"),
                "capture_path": capture_path.as_posix(),
                "capture_sha256": expected_digest,
                "reuse_reason": spec.get("reason"),
            }
            expected_parent_schema = spec.get("expected_parent_schema")
            if expected_parent_schema:
                if route_id not in supplemental_parent_paths:
                    raise StructuredSliceMaterializationError(
                        f"supplemental_parent_binding_missing:{route_id}"
                    )
                parent_path = _require_file(
                    supplemental_parent_paths[route_id],
                    label=f"supplemental_parent:{route_id}",
                )
                parent = _read_json(parent_path, label="supplemental_parent")
                if (
                    parent.get("schema_version") != expected_parent_schema
                    or str(parent.get("capture_sha256") or "").lower()
                    != expected_digest
                    or str(parent.get("source_url") or "")
                    != spec.get("source_url")
                ):
                    raise StructuredSliceMaterializationError(
                        f"supplemental_parent_binding_invalid:{route_id}"
                    )
                binding.update(
                    {
                        "parent_path": parent_path.as_posix(),
                        "parent_sha256": _sha256_file(parent_path),
                    }
                )
            local_bodies[route_id] = (
                capture_path,
                expected_digest,
                "prior_immutable_official_capture",
            )
            supplemental_bindings.append(binding)

    if len(local_bodies) > int(plan["scope"]["maximum_parsed_sources"]):
        raise StructuredSliceMaterializationError("parsed_source_ceiling_exceeded")

    root = output_root.expanduser().resolve() / attempt_id
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise StructuredSliceMaterializationError(
            "structured_slice_attempt_already_exists"
        ) from exc

    documents: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    generic = plan["generic_chunking"]
    sec_chunking = plan["sec_chunking"]
    for route_id in sorted(local_bodies):
        body_path, digest, origin = local_bodies[route_id]
        metadata_by_route = plan.get("source_metadata")
        if (
            not isinstance(metadata_by_route, Mapping)
            or route_id not in metadata_by_route
            or not isinstance(metadata_by_route[route_id], Mapping)
        ):
            raise StructuredSliceMaterializationError(
                f"source_metadata_missing:{route_id}"
            )
        source_mapping = {
            **declared_by_route[route_id],
            **dict(metadata_by_route[route_id]),
        }
        if route_id in supplemental_by_route:
            source_mapping["stable_url"] = supplemental_by_route[route_id][
                "source_url"
            ]
        try:
            source = StructuredSourceDescriptor.from_mapping(
                source_mapping,
                raw_body_sha256=digest,
            )
            profile = _parser_profile(plan, source_mapping)
            if route_id in supplemental_by_route:
                supplemental = supplemental_by_route[route_id]
                if (
                    str(supplemental.get("parser_profile") or "") != profile
                    or supplemental.get("numeric_authority") is not False
                    or supplemental.get("candidate_is_not_evidence") is not True
                ):
                    raise StructuredSliceMaterializationError(
                        f"supplemental_source_contract_invalid:{route_id}"
                    )
            tree = build_structured_document_tree(
                source=source,
                body=body_path.read_bytes(),
                parser_profile=profile,
                generic_split_length_words=int(generic["split_length"]),
                generic_split_overlap_words=int(generic["split_overlap"]),
                generic_split_threshold_words=int(generic["split_threshold"]),
                sec_chunk_size_tokens=int(sec_chunking["chunk_size_tokens"]),
                sec_chunk_overlap_tokens=int(
                    sec_chunking["chunk_overlap_tokens"]
                ),
                sec_max_table_tokens=int(
                    sec_chunking["maximum_table_tokens"]
                ),
            )
            tree["document"]["local_body_origin"] = origin
            documents.append(tree["document"])
            sections.extend(tree["sections"])
            blocks.extend(tree["blocks"])
            chunks.extend(tree["chunks"])
        except (OSError, StructuredDocumentError, ValueError) as exc:
            failures.append(
                {
                    "route_id": route_id,
                    "failure_code": f"structured_parse_failure:{type(exc).__name__}",
                    "detail": str(exc),
                    "raw_body_sha256": digest,
                }
            )

    declared_unavailable = [
        {
            "route_id": route_id,
            "capture_status": observed.get("capture_status"),
            "failure_code": observed.get("failure_code"),
            "status": observed.get("status"),
            "public_information_gap": False,
        }
        for route_id, observed in sorted(observed_by_route.items())
        if route_id not in local_bodies
    ]

    artifacts = {
        "documents": _write_jsonl(root / "documents.jsonl", documents),
        "sections": _write_jsonl(root / "sections.jsonl", sections),
        "blocks": _write_jsonl(root / "blocks.jsonl", blocks),
        "chunks": _write_jsonl(root / "chunks.jsonl", chunks),
    }
    review_queue = _manual_review_queue(documents, chunks)
    review_queue_path = root / "manual_review_queue.json"
    review_queue_path.write_bytes(_pretty_bytes(review_queue))
    artifacts["manual_review_queue"] = {
        "path": review_queue_path.as_posix(),
        "sha256": _sha256_file(review_queue_path),
        "record_count": len(review_queue),
        "bytes": review_queue_path.stat().st_size,
    }

    result = {
        "schema_version": RESULT_SCHEMA,
        "status": (
            "STRUCTURED_CORPUS_MATERIALIZED_REVIEW_REQUIRED"
            if documents and not failures
            else "STRUCTURED_CORPUS_PARTIAL_REVIEW_REQUIRED"
            if documents
            else "STRUCTURED_CORPUS_FAILED"
        ),
        "attempt_id": attempt_id,
        "case_id": plan["case_id"],
        "plan": {
            "path": plan_path.as_posix(),
            "sha256": _sha256_file(plan_path),
        },
        "implementation": {
            "materializer": {
                "path": Path(__file__).resolve().as_posix(),
                "sha256": _sha256_file(Path(__file__).resolve()),
            },
            "adapter": {
                "path": (
                    REPOSITORY_ROOT
                    / "src"
                    / "ingestion"
                    / "structured_document_adapter.py"
                ).as_posix(),
                "sha256": _sha256_file(
                    REPOSITORY_ROOT
                    / "src"
                    / "ingestion"
                    / "structured_document_adapter.py"
                ),
            },
            "python": sys.version,
        },
        "git": _git_binding(),
        "inputs": input_attempts,
        "supplemental_bindings": supplemental_bindings,
        "declared_source_count": len(declared_by_route),
        "locally_available_source_count": len(local_bodies),
        "parsed_document_count": len(documents),
        "structured_parse_failure_count": len(failures),
        "declared_unavailable_source_count": len(declared_unavailable),
        "section_count": len(sections),
        "block_count": len(blocks),
        "chunk_count": len(chunks),
        "table_block_count": sum(row["block_kind"] == "table" for row in blocks),
        "image_reference_count": sum(
            len(row["image_references"]) for row in blocks
        ),
        "parser_profile_counts": dict(
            sorted(Counter(row["parser_profile"] for row in documents).items())
        ),
        "failures": failures,
        "declared_unavailable_sources": declared_unavailable,
        "artifacts": artifacts,
        "authority": plan["authority"],
        "manual_review_complete": False,
        "retrieval_promotion_authorized": False,
        "mcp_runtime_mutated": False,
        "model_calls": 0,
        "network_calls": 0,
    }
    result_path = root / "result.json"
    result_path.write_bytes(_pretty_bytes(result))
    result["result_path"] = result_path.as_posix()
    result["result_sha256"] = _sha256_file(result_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument(
        "--knowledge-attempt-root", type=Path, action="append", required=True
    )
    parser.add_argument("--supplemental-parent", action="append", default=[])
    parser.add_argument("--supplemental-capture", action="append", default=[])
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()
    def bindings(values: Sequence[str], label: str) -> dict[str, Path]:
        result: dict[str, Path] = {}
        for value in values:
            route_id, separator, path = value.partition("=")
            if not separator or not route_id.strip() or not path.strip():
                raise StructuredSliceMaterializationError(
                    f"{label}_binding_invalid"
                )
            if route_id.strip() in result:
                raise StructuredSliceMaterializationError(
                    f"{label}_binding_duplicate"
                )
            result[route_id.strip()] = Path(path.strip())
        return result

    result = materialize_structured_slice(
        plan_path=args.plan,
        knowledge_attempt_roots=args.knowledge_attempt_root,
        output_root=args.output_root,
        attempt_id=args.attempt_id,
        supplemental_parent_paths=bindings(
            args.supplemental_parent, "supplemental_parent"
        ),
        supplemental_capture_paths=bindings(
            args.supplemental_capture, "supplemental_capture"
        ),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["parsed_document_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
