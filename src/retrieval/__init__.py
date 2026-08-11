"""Shared text normalization used by the admitted index builders.

Historical BM25, dense and fusion query implementations are deliberately not
re-exported here.  They have not been promoted into the FIN 0.1.3 product
runtime and live in the versioned archive.
"""

from .text import tokenize

__all__ = ["tokenize"]
