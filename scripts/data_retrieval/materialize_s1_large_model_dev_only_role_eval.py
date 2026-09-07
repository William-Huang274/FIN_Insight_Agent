from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.query_plan import canonical_digest  # noqa: E402


SOURCE = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_financial_role_eval_set_v1_1.json"
)
OUTPUT = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_large_model_dev_only_role_eval_v1_0.json"
)
ALLOWED_CASE_KEYS = {"DELL", "MU", "NVDA"}
FORBIDDEN_CASE_KEYS = {"COST", "ANET", "ASML", "ORCL"}


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("s1_dev_only_role_eval_source_object_required")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        output = []
        for key, item in value.items():
            output.extend(_strings(key))
            output.extend(_strings(item))
        return output
    if isinstance(value, list):
        output = []
        for item in value:
            output.extend(_strings(item))
        return output
    return []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize a DELL/MU/NVDA development-only role-eval projection "
            "without copying hidden holdout rows or bindings."
        )
    )
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--output", default=OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_path = _resolve(args.source)
    source = _read_json(source_path)
    source_queries = source.get("queries")
    if not isinstance(source_queries, list):
        raise ValueError("s1_dev_only_role_eval_queries_missing")
    queries = [
        dict(query)
        for query in source_queries
        if isinstance(query, Mapping)
        and query.get("split") == "primary_three_case"
        and query.get("case_key") in ALLOWED_CASE_KEYS
    ]
    case_keys = sorted({str(query.get("case_key")) for query in queries})
    query_ids = [str(query.get("query_id")) for query in queries]
    if len(queries) != 18:
        raise ValueError("s1_dev_only_role_eval_query_count_invalid")
    if set(case_keys) != ALLOWED_CASE_KEYS:
        raise ValueError("s1_dev_only_role_eval_case_inventory_invalid")
    if len(query_ids) != len(set(query_ids)) or any(not value for value in query_ids):
        raise ValueError("s1_dev_only_role_eval_query_ids_invalid")
    copied_strings = _strings(queries)
    if "holdout_unseen_case" in copied_strings:
        raise ValueError("s1_dev_only_role_eval_holdout_split_leaked")
    leaked_case_keys = sorted(
        value for value in FORBIDDEN_CASE_KEYS if value in copied_strings
    )
    if leaked_case_keys:
        raise ValueError(
            "s1_dev_only_role_eval_forbidden_case_leaked:"
            + ",".join(leaked_case_keys)
        )

    unsigned = {
        "schema_version": "fin_ia_s1_large_model_dev_only_role_eval_v1_0",
        "status": "development_only_projection_ready",
        "recorded_at": "2026-08-24",
        "source_audit_binding": {
            "path": source_path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(source_path),
            "source_was_used_only_to_materialize_this_projection": True,
            "source_must_not_be_loaded_by_large_model_development_runner": True,
        },
        "selection_contract": {
            "required_split": "primary_three_case",
            "allowed_case_keys": sorted(ALLOWED_CASE_KEYS),
            "forbidden_case_keys": sorted(FORBIDDEN_CASE_KEYS),
            "holdout_rows_copied": False,
            "heldout_pack_bindings_copied": False,
            "source_bound_inputs_copied": False,
        },
        "case_inventory": case_keys,
        "query_count": len(queries),
        "query_ids": query_ids,
        "queries": queries,
        "calls": {"network": 0, "provider": 0, "model": 0},
        "authority": {
            "development_only": True,
            "blind_or_holdout_qualification_authorized": False,
            "s1_qualification_authorized": False,
            "runtime_promotion_authorized": False,
        },
    }
    output = {**unsigned, "result_digest": canonical_digest(unsigned)}
    _write_json(_resolve(args.output), output)
    print(
        json.dumps(
            {
                "status": output["status"],
                "query_count": output["query_count"],
                "case_inventory": output["case_inventory"],
                "calls": output["calls"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
