from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
for candidate in (ROOT, SRC_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ingestion.official_source_capture import (  # noqa: E402
    materialize_response_body_capture,
)
from ingestion.pdf_layout import parse_captured_pdf_layout  # noqa: E402
from retrieval.financial_objects import content_digest  # noqa: E402
from retrieval.pdf_layout_objects import compile_pdf_layout_document  # noqa: E402


RESULT_SCHEMA_VERSION = "fin_ia_official_pdf_layout_pipeline_result_v1_0"


def _resolve(value: Path) -> Path:
    return value.resolve() if value.is_absolute() else (ROOT / value).resolve()


def _repo_ref(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_mapping_required:{path.name}")
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def execute(
    *,
    response_capture_path: Path,
    source_spec_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    if output_root.exists():
        raise ValueError("official_pdf_layout_output_already_exists")
    output_root.mkdir(parents=True, exist_ok=False)
    capture = _read_json(response_capture_path)
    spec = _read_json(source_spec_path)
    if not (
        spec.get("status")
        == "qualification_source_parser_contract_frozen_before_parse"
        and spec.get("page_selection_policy") == "all_pages"
        and spec.get("ocr_policy") == "automatic_low_native_text_pages"
        and spec.get("candidate_is_not_evidence") is True
        and spec.get("numeric_fact_authority") is False
        and str(capture.get("route_id") or "") == str(spec.get("route_id") or "")
        and str(capture.get("case_key") or "") == str(spec.get("case_key") or "")
        and str(capture.get("final_url") or "") == str(spec.get("source_url") or "")
    ):
        raise ValueError("official_pdf_layout_source_binding_invalid")

    body = materialize_response_body_capture(
        capture, output_root=output_root / "raw_bodies"
    )
    raw_path = Path(str(body["body_path"]))
    reader = PdfReader(raw_path, strict=False)
    page_count = len(reader.pages)
    if page_count < 1:
        raise ValueError("official_pdf_layout_page_count_invalid")
    parse_capture = {
        "schema_version": body["schema_version"],
        "task_id": spec["program_id"],
        "plan_id": spec["route_id"],
        "case_key": spec["case_key"],
        "ticker": spec["ticker"],
        "company_name": spec["company"],
        "report_type": spec["document_type"],
        "title": spec["title"],
        "publication_date": spec["publication_date"],
        "period_end": spec["period_end"],
        "fiscal_year": spec["fiscal_year"],
        "source_url": spec["source_url"],
        "document_path": _repo_ref(raw_path),
        "sha256": body["body_sha256"],
        "byte_count": body["body_bytes"],
        "pdf_page_count": page_count,
    }
    parsed = parse_captured_pdf_layout(
        parse_capture,
        repository_root=ROOT,
        selected_page_numbers=tuple(range(1, page_count + 1)),
    )
    parsed_path = output_root / "parsed_layout.json"
    _write_json(parsed_path, parsed)
    parsed_sha256 = hashlib.sha256(parsed_path.read_bytes()).hexdigest()
    parent, children, object_set = compile_pdf_layout_document(
        parsed,
        source_spec=spec,
        parsed_ref=_repo_ref(parsed_path),
        parsed_sha256=parsed_sha256,
    )
    _write_json(output_root / "document_parent.json", parent)
    _write_jsonl(output_root / "financial_objects.jsonl", children)
    _write_json(output_root / "object_set.json", object_set)
    quality = dict(parsed["quality_receipt"])
    result_body = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "official_pdf_layout_candidates_materialized",
        "program_id": spec["program_id"],
        "route_id": spec["route_id"],
        "source_spec_ref": _repo_ref(source_spec_path),
        "source_spec_sha256": hashlib.sha256(source_spec_path.read_bytes()).hexdigest(),
        "response_capture_ref": _repo_ref(response_capture_path),
        "response_capture_sha256": hashlib.sha256(
            response_capture_path.read_bytes()
        ).hexdigest(),
        "raw_body_sha256": body["body_sha256"],
        "page_count": page_count,
        "parsed_layout_ref": _repo_ref(parsed_path),
        "parsed_layout_sha256": parsed_sha256,
        "document_parent_id": parent["document_id"],
        "financial_object_count": len(children),
        "extraction_modes": quality["extraction_modes"],
        "page_statuses": quality["page_statuses"],
        "low_confidence_material_token_count": quality[
            "low_confidence_material_token_count"
        ],
        "candidate_is_not_evidence": True,
        "numeric_fact_authority": False,
        "network_calls": 0,
        "model_calls": 0,
    }
    result = {**result_body, "result_digest": content_digest(result_body)}
    _write_json(output_root / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse a capture-first official PDF into layout-aware candidates."
    )
    parser.add_argument("--response-capture", type=Path, required=True)
    parser.add_argument("--source-spec", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = execute(
        response_capture_path=_resolve(args.response_capture),
        source_spec_path=_resolve(args.source_spec),
        output_root=_resolve(args.output_root),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
