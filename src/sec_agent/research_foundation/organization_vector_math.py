"""Bounded temporary arrays for exact organization vector validation/scoring.

The caller owns authorization, immutable release integrity and candidate IDs.
Blocks preserve the authorized row order; there is no sampling or ANN shortcut.
"""
import numpy as np


BLOCK_ROWS = 4096


def _blocks(matrix, positions=None):
    count = len(matrix) if positions is None else len(positions)
    for start in range(0, count, BLOCK_ROWS):
        stop = min(start + BLOCK_ROWS, count)
        yield start, matrix[start:stop] if positions is None else matrix[positions[start:stop]]


def _unit(block):
    return (np.isfinite(block).all()
            and np.allclose(np.linalg.norm(block.astype(np.float64), axis=1),
                            1., rtol=1e-5, atol=1e-6))


def unit_vectors(matrix, positions=None):
    return all(_unit(block) for _, block in _blocks(matrix, positions))


def cosine_scores(matrix, positions, query):
    """Only score selected rows; validate the same block used in each dot product."""
    scores = np.empty(len(positions), dtype=np.float32)
    for start, block in _blocks(matrix, positions):
        if not _unit(block):
            raise ValueError('organization_retrieval_invalid_prepared_vectors')
        scores[start:start + len(block)] = block @ query
    return scores
