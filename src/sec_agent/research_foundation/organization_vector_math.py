"""Bounded temporary arrays for exact organization vector validation/scoring.

The caller owns authorization, immutable release integrity and candidate IDs.
Blocks preserve the authorized row order; there is no sampling or ANN shortcut.
"""
import numpy as np
import mmap


BLOCK_ROWS = 4096


def _mapped_block(matrix, positions, start, stop):
    """Return owned selected data; don't pin all scanned pages in one mapping.

    A root read-only np.load mapping supplies validated shape/dtype/offset. Each
    temporary mapping dies before the caller validates/scores its owned block.
    Subviews and mutable mappings deliberately retain the ordinary NumPy path.
    """
    mapped = np.memmap(matrix.filename, mode='r', dtype=matrix.dtype,
                       offset=matrix.offset, shape=matrix.shape, order='C')
    if positions is None:
        return np.array(mapped[start:stop], copy=True)
    # Advanced integer indexing owns a copy, never a view of the mapped file.
    return mapped[positions[start:stop]]


def _blocks(matrix, positions=None):
    count = len(matrix) if positions is None else len(positions)
    remap = (isinstance(matrix, np.memmap) and isinstance(matrix.base, mmap.mmap)
             and matrix.mode == 'r' and matrix.flags.c_contiguous)
    for start in range(0, count, BLOCK_ROWS):
        stop = min(start + BLOCK_ROWS, count)
        block = (_mapped_block(matrix, positions, start, stop) if remap else
                 matrix[start:stop] if positions is None else matrix[positions[start:stop]])
        yield start, block


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


def verified_cosine_scores(matrix, positions, query):
    """Score a release already checked for unit vectors and immutable identity.

    Only the frozen-release loader's caller may use this path. It must check
    file identity before and after scoring. Unverified/legacy inputs continue
    to use cosine_scores; no tool argument can select this function.
    """
    scores = np.empty(len(positions), dtype=np.float32)
    for start, block in _blocks(matrix, positions):
        scores[start:start + len(block)] = block @ query
    if not np.isfinite(scores).all():
        raise ValueError('organization_retrieval_invalid_prepared_vectors')
    return scores
