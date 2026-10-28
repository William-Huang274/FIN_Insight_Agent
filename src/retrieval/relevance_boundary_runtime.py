"""Freeze a validated relevance policy per navigator; never supply authority."""
from hashlib import sha256
import json
from pathlib import Path


def pipeline_identity(profile, model, instruction, table_completion):
    """Same implementation identity for serving and independently frozen evals.

    Source/query/ranking code changes invalidate calibration. Corpus identity
    is intentionally separate: validation requires disjoint source documents.
    """
    root = Path(__file__).resolve().parents[2]
    files = sorted(p for folder in ('src/retrieval', 'src/sec_agent/research_foundation')
                   for p in (root / folder).glob('*.py'))
    code = [[p.relative_to(root).as_posix(), sha256(p.read_bytes()).hexdigest()] for p in files]
    return {'profile':profile, 'model':model,
            'instruction_sha256':sha256((instruction or '').encode()).hexdigest(),
            'table_completion':table_completion,
            'implementation_sha256':sha256(json.dumps(code,separators=(',',':')).encode()).hexdigest()}


class ResultBoundary:
    def __init__(self, artifact, pipeline):
        from .relevance_boundary import partition
        self.pipeline = pipeline
        # Copy deployment data; changing the file cannot mutate a live session
        # or silently reuse a response cached under a different configuration.
        self.artifact = json.loads(json.dumps(artifact))
        self.digest = sha256(json.dumps(self.artifact,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        partition([], {}, self.artifact['calibration'], pipeline=self.pipeline,
                  validation=self.artifact['validation'], limit=1)

    def apply(self, rows, rerank_receipt, *, limit):
        from .relevance_boundary import partition
        if rerank_receipt.get('model') != self.pipeline['model']:
            raise ValueError('relevance_boundary_provider_mismatch')
        pairs = rerank_receipt.get('scores', [])
        scores = dict(pairs)
        if len(scores) != len(pairs):
            raise ValueError('relevance_boundary_duplicate_score')
        selected, receipt = partition(rows, scores, self.artifact['calibration'],
            pipeline=self.pipeline, validation=self.artifact['validation'], limit=limit)
        receipt['deployment_artifact_sha256'] = self.digest
        return selected, receipt


def configured_boundary(profile, reranker, table_completion):
    import os
    path = os.getenv('FINSIGHT_ORGANIZATION_RELEVANCE_BOUNDARY', '')
    if not path:
        return None
    if reranker is None or not getattr(reranker,'model',None):
        raise ValueError('relevance_boundary_requires_configured_reranker')
    raw = Path(path).read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('relevance_boundary_artifact_too_large')
    pipeline = pipeline_identity(profile, reranker.model, reranker.instruction, table_completion)
    return ResultBoundary(json.loads(raw), pipeline)
