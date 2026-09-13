import httpx
import pytest

from retrieval.qwen_api import QwenRetrieval


def client(handler):
    return QwenRetrieval("synthetic-test-credential", http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_sdk_wire_and_embedding_index_order():
    import json
    def handler(request):
        assert request.url.path == "/compatible-mode/v1/embeddings"
        body = json.loads(request.content)
        assert body["dimensions"] == 2
        assert body["input"] == ["first", "second"]
        return httpx.Response(200, json={"object": "list", "model": "text-embedding-v4",
            "data": [{"index": 1, "object": "embedding", "embedding": [0, 1]},
                     {"index": 0, "object": "embedding", "embedding": [1, 0]}],
            "usage": {"prompt_tokens": 2, "total_tokens": 2}})
    api = client(handler)
    result = api.embed(["first", "second"], dimensions=2)
    assert result.values == [[1, 0], [0, 1]]
    assert result.usage["total_tokens"] == 2
    api.close()


def test_rerank_sdk_wire_and_no_retry():
    requests = []
    def handler(request):
        requests.append(request)
        assert request.url.path == "/compatible-api/v1/reranks"
        return httpx.Response(429, json={"error": {"message": "quota", "type": "rate_limit"}})
    api = client(handler)
    with pytest.raises(Exception):
        api.rerank("query", ["document"])
    assert len(requests) == 1
    api.close()


def test_duplicate_rerank_indices_rejected():
    api = client(lambda request: httpx.Response(200, json={"results": [
        {"index": 0, "relevance_score": .9}, {"index": 0, "relevance_score": .7}]}))
    with pytest.raises(ValueError, match="index_mismatch"):
        api.rerank("query", ["a", "b"])
    api.close()
