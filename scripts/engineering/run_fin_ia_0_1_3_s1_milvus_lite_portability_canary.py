from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import site
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.s1_internal_supplemental_dense_execution import (  # noqa: E402
    MilvusIndexWriter,
)


def _distribution_fingerprint(distribution_name: str) -> dict[str, Any]:
    distribution = importlib.metadata.distribution(distribution_name)
    rows: list[dict[str, Any]] = []
    for relative in sorted(distribution.files or [], key=lambda value: str(value)):
        relative_text = str(relative).replace("\\", "/")
        if "__pycache__" in relative_text or relative_text.endswith((".pyc", ".pyo")):
            continue
        absolute = Path(distribution.locate_file(relative))
        if not absolute.is_file():
            continue
        payload = absolute.read_bytes()
        rows.append(
            {
                "path": relative_text,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    aggregate_payload = json.dumps(
        rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "distribution": distribution_name,
        "version": distribution.version,
        "file_count": len(rows),
        "total_bytes": sum(row["bytes"] for row in rows),
        "tree_sha256": hashlib.sha256(aggregate_payload).hexdigest(),
    }


def _manifest_source_observation() -> dict[str, Any]:
    import milvus_lite.storage.manifest as manifest_module

    path = Path(manifest_module.__file__).resolve()
    payload = path.read_bytes()
    text = payload.decode("utf-8", errors="replace")
    if "os.replace(" in text:
        primitive = "os.replace"
    elif "os.rename(" in text:
        primitive = "os.rename"
    else:
        primitive = "unknown"
    return {
        "path": str(path),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "commit_primitive": primitive,
    }


def _canary_row() -> dict[str, Any]:
    return {
        "vector_id": "FIN013_S1_MILVUS_PORTABILITY_CANARY::narrative_chunk",
        "embedding": [1.0, 0.0, 0.0, 0.0],
        "evidence_id": "FIN013_S1_MILVUS_PORTABILITY_CANARY",
        "ticker": "DELL",
        "form_type": "10-K",
        "source_tier": "canary_not_evidence",
        "item_code": "CANARY",
        "category_slug": "dependency_portability",
        "period_type": "canary",
        "vector_kind": "narrative_chunk",
        "vector_role": "dependency_qualification",
        "semantic_scope": "not_research_content",
        "intent_tags": ["milvus_lite", "double_flush", "reopen"],
        "relationship_role": "none",
        "object_type": "canary",
        "preview": "Synthetic dependency qualification row; never eligible for Evidence.",
        "fiscal_year": 2026,
        "contains_table": False,
    }


def run_canary(db_path: Path) -> dict[str, Any]:
    if db_path.exists():
        raise RuntimeError(f"canary_database_preexists:{db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    collection_name = "fin_ia_0_1_3_s1_milvus_portability_canary"
    dependency_dir = site.getsitepackages()[0]
    writer = MilvusIndexWriter(uri=str(db_path), dependency_dir=dependency_dir)
    writer.begin(collection_name=collection_name, embedding_dim=4)
    acknowledged = writer.insert([_canary_row()])
    count_before_close = writer.count()
    writer.finalize()
    writer_calls = dict(writer.calls)
    writer.close()

    from pymilvus import MilvusClient

    reopened = MilvusClient(uri=str(db_path))
    try:
        has_collection = reopened.has_collection(collection_name=collection_name)
        stats = reopened.get_collection_stats(collection_name=collection_name)
        rows = reopened.query(
            collection_name=collection_name,
            filter=(
                'vector_id == '
                '"FIN013_S1_MILVUS_PORTABILITY_CANARY::narrative_chunk"'
            ),
            output_fields=["vector_id", "evidence_id", "ticker", "source_tier"],
        )
    finally:
        close = getattr(reopened, "close", None)
        if callable(close):
            close()

    count_after_reopen = int((stats or {}).get("row_count") or 0)
    success = (
        acknowledged == 1
        and count_before_close == 1
        and writer_calls
        == {
            "database_create": 1,
            "collection_create": 1,
            "insert_batches": 1,
            "inserted_vectors": 1,
            "flush": 2,
            "count": 1,
        }
        and has_collection
        and count_after_reopen == 1
        and len(rows) == 1
        and rows[0].get("source_tier") == "canary_not_evidence"
    )
    if not success:
        raise RuntimeError("milvus_lite_portability_canary_invariant_failed")

    return {
        "schema_version": "fin_ia_0_1_3_s1_milvus_lite_portability_canary_result_v1_0",
        "contract_ref": "fin_0_1_3.S1.milvus_lite_portability_canary:v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "terminal_succeeded_dependency_qualification_only",
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "architecture": platform.machine(),
            "database_path": str(db_path),
        },
        "dependency_fingerprints": {
            "pymilvus": _distribution_fingerprint("pymilvus"),
            "milvus_lite": _distribution_fingerprint("milvus-lite"),
            "manifest_source": _manifest_source_observation(),
        },
        "observed_calls": writer_calls,
        "verification": {
            "insert_acknowledged": acknowledged,
            "count_before_close": count_before_close,
            "collection_exists_after_reopen": has_collection,
            "count_after_reopen": count_after_reopen,
            "metadata_query_rows": len(rows),
            "metadata_query_identity": rows[0].get("vector_id"),
            "double_flush_proven": writer_calls["flush"] == 2,
            "close_reopen_proven": True,
        },
        "external_calls": {
            "network": 0,
            "provider": 0,
            "llm": 0,
            "bge_model_load": 0,
            "embedding_vectors": 0,
            "historical_milvus_write": 0,
            "evidence_promotion": 0,
        },
        "known_boundary": (
            "This one-row synthetic canary qualifies dependency persistence only. "
            "It does not authorize or prove the 410-vector replacement build, "
            "ranking, reranking, Evidence, external retrieval, or release."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_canary(args.db_path.resolve())
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
