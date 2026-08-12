"""Provider-neutral retrieval contracts and deterministic local candidates."""

from .candidate_retriever import load_candidate_corpus, retrieve_query_plan
from .contracts import load_financial_research_kernel
from .query_plan import compile_query_facet_plan
from .text import tokenize

__all__ = [
    "compile_query_facet_plan",
    "load_candidate_corpus",
    "load_financial_research_kernel",
    "retrieve_query_plan",
    "tokenize",
]
