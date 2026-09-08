"""Thin Qwen retrieval adapter using the installed OpenAI SDK.

No key discovery, index migration, retries, or financial evidence admission here.
Callers own authorization, task-scoped caching and usage accounting.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from openai import OpenAI


@dataclass(frozen=True)
class RetrievalResponse:
    values: list
    usage: dict[str, Any]
    request_id: str | None
    model: str


class QwenRetrieval:
    def __init__(self, api_key: str, *, embedding_model="text-embedding-v4",
                 rerank_model="qwen3-rerank", http_client=None):
        self.embedding_model = embedding_model
        self.rerank_model = rerank_model
        options = dict(api_key=api_key, max_retries=0, timeout=45)
        if http_client is not None:
            options["http_client"] = http_client
        self.embeddings = OpenAI(base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", **options)
        self.reranker = OpenAI(base_url="https://dashscope.aliyuncs.com/compatible-api/v1", **options)

    def close(self):
        self.embeddings.close()
        self.reranker.close()

    def embed(self, texts: list[str], *, dimensions=1024) -> RetrievalResponse:
        if not 1 <= len(texts) <= 10 or any(not t.strip() for t in texts):
            raise ValueError("embedding_requires_1_to_10_nonempty_texts")
        result = self.embeddings.embeddings.create(
            model=self.embedding_model, input=texts, dimensions=dimensions, encoding_format="float")
        rows = sorted(result.data, key=lambda row: row.index)
        if [r.index for r in rows] != list(range(len(texts))):
            raise ValueError("embedding_response_index_mismatch")
        vectors = [r.embedding for r in rows]
        if any(len(v) != dimensions or not all(math.isfinite(x) for x in v)
               or not any(v) for v in vectors):
            raise ValueError("embedding_response_invalid_vector")
        return RetrievalResponse(vectors, result.usage.model_dump(),
                                 getattr(result, "_request_id", None), result.model)

    def rerank(self, query: str, documents: list[str], *, top_n=None) -> RetrievalResponse:
        if not query.strip() or not 1 <= len(documents) <= 500 or any(not d.strip() for d in documents):
            raise ValueError("rerank_requires_query_and_1_to_500_documents")
        count = len(documents) if top_n is None else top_n
        if not 1 <= count <= len(documents):
            raise ValueError("rerank_invalid_top_n")
        result = self.reranker.post("/reranks", body={"model": self.rerank_model,
            "query": query, "documents": documents, "top_n": count}, cast_to=object)
        rows = result.get("results", [])
        indices = [r.get("index") for r in rows]
        if len(rows) != count or len(set(indices)) != count or any(
                type(i) is not int or not 0 <= i < len(documents) for i in indices):
            raise ValueError("rerank_response_index_mismatch")
        if any(not isinstance(r.get("relevance_score"), (float, int))
               or not math.isfinite(r["relevance_score"]) for r in rows):
            raise ValueError("rerank_response_invalid_score")
        return RetrievalResponse(rows, result.get("usage") or {},
                                 result.get("id") or result.get("request_id"), self.rerank_model)
