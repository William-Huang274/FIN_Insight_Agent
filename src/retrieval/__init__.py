"""Provider-neutral retrieval contracts and deterministic local candidates."""

from .candidate_retriever import load_candidate_corpus, retrieve_query_plan
from .contracts import load_financial_research_kernel
from .financial_objects import (
    attach_legacy_aliases,
    compile_parsed_sec_capture,
    compile_raw_sec_html_capture,
    normalize_legacy_candidate,
    project_market_snapshot,
    validate_source_object_manifest,
)
from .query_plan import compile_query_facet_plan
from .official_pdf_objects import compile_official_pdf_document
from .text import tokenize

__all__ = [
    "compile_query_facet_plan",
    "compile_official_pdf_document",
    "attach_legacy_aliases",
    "compile_parsed_sec_capture",
    "compile_raw_sec_html_capture",
    "load_candidate_corpus",
    "load_financial_research_kernel",
    "normalize_legacy_candidate",
    "project_market_snapshot",
    "retrieve_query_plan",
    "tokenize",
    "validate_source_object_manifest",
]
