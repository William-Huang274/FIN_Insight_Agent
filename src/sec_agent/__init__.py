"""Version-neutral FIN 0.1.3 runtime package.

The package root intentionally has no eager imports.  Product and operator
entrypoints import their owned modules explicitly so importing ``sec_agent``
cannot revive an archived agent graph as a side effect.
"""

__all__: list[str] = []
