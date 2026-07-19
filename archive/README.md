# Repository Archive

This directory preserves code and artifacts removed from the active package or public entrypoint surface.

Archive rules:

- archive only after whole-repository runtime/test/doc reference review;
- record the replacement path and reason in the archive-local README;
- archived code is not installed, imported, tested, or maintained as current runtime;
- do not use archive for generated outputs, private data, indexes, databases, or caches;
- restoring archived code requires moving it back into an owned module, adding tests, and updating the repository architecture inventory.
