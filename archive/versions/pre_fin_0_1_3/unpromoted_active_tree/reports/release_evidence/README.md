# FIN 0.1 Release Evidence

This directory stores small, durable, reviewable evidence used by FIN 0.1 release decisions. It is intentionally tracked in Git.

Raw browser screenshots, server logs, SQLite stores, provider responses and temporary run directories belong under `.codex_runtime/` or ignored report/output directories. A file here must identify its scope, input identity, execution counts, boundary and decision; it must not contain secrets or customer data.

Evidence in this directory can support a gate decision but is not itself release or production authority.
