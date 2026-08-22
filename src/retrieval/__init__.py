"""Provider-neutral retrieval contracts and deterministic local candidates."""

from .candidate_retriever import load_candidate_corpus, retrieve_query_plan
from .contracts import load_financial_research_kernel
from .external_source_ladder import (
    EXTERNAL_FETCH_SHORTLIST_SCHEMA_VERSION,
    EXTERNAL_LOCATOR_BUNDLE_SCHEMA_VERSION,
    EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION,
    SAFE_PROVIDER_REQUEST_SCHEMA_VERSION,
    ExternalSourceLadderError,
    build_external_fetch_shortlist,
    canonicalize_external_url,
    compile_safe_provider_request,
    normalize_tencent_search_response,
    validate_external_source_ladder_plan,
)
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
from .public_context_source import (
    PUBLIC_CONTEXT_CANDIDATE_SCHEMA_VERSION,
    PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION,
    PUBLIC_PDF_SOURCE_OBJECT_SCHEMA_VERSION,
    PUBLICATION_DATE_RECEIPT_SCHEMA_VERSION,
    PublicContextSourceError,
    adjudicate_publication_date_from_capture,
    compile_public_context_candidate,
    compile_public_html_source_object,
    compile_public_pdf_source_object,
)
from .public_context_evidence import (
    PUBLIC_CONTEXT_EVIDENCE_PLAN_SCHEMA_VERSION,
    PUBLIC_CONTEXT_EVIDENCE_RESULT_SCHEMA_VERSION,
    PublicContextEvidenceError,
    adjudicate_public_context_evidence,
)
from .source_use_policy import (
    SOURCE_USE_POLICY_SCHEMA_VERSION,
    SourceUseClass,
    SourceUsePolicy,
    SourceUsePolicyError,
    evaluate_source_claim_use,
)
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
    "PUBLIC_CONTEXT_CANDIDATE_SCHEMA_VERSION",
    "PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION",
    "PUBLIC_PDF_SOURCE_OBJECT_SCHEMA_VERSION",
    "PUBLICATION_DATE_RECEIPT_SCHEMA_VERSION",
    "PublicContextSourceError",
    "adjudicate_publication_date_from_capture",
    "compile_public_context_candidate",
    "compile_public_html_source_object",
    "compile_public_pdf_source_object",
    "PUBLIC_CONTEXT_EVIDENCE_PLAN_SCHEMA_VERSION",
    "PUBLIC_CONTEXT_EVIDENCE_RESULT_SCHEMA_VERSION",
    "PublicContextEvidenceError",
    "adjudicate_public_context_evidence",
    "retrieve_query_plan",
    "SOURCE_USE_POLICY_SCHEMA_VERSION",
    "SourceUseClass",
    "SourceUsePolicy",
    "SourceUsePolicyError",
    "evaluate_source_claim_use",
    "tokenize",
    "validate_source_object_manifest",
    "EXTERNAL_FETCH_SHORTLIST_SCHEMA_VERSION",
    "EXTERNAL_LOCATOR_BUNDLE_SCHEMA_VERSION",
    "EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION",
    "SAFE_PROVIDER_REQUEST_SCHEMA_VERSION",
    "ExternalSourceLadderError",
    "build_external_fetch_shortlist",
    "canonicalize_external_url",
    "compile_safe_provider_request",
    "normalize_tencent_search_response",
    "validate_external_source_ladder_plan",
]
