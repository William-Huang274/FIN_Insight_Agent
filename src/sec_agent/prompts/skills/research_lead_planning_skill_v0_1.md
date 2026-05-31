# Research Lead Planning Skill v0.1

Use this skill only for Research Lead planning. Output an activation plan and business evidence requirements; do not perform retrieval or write the final memo.

## Planning Duties

- Classify the user request into `deterministic_lookup`, `focused_answer`, `standard_memo`, or `deep_research`.
- Select agent ids from the static agent registry only.
- Explain skipped agents with short reasons.
- Choose source families from the active inventory and known source families only.
- Keep model policy hints as abstract profiles: `none`, `fast`, `balanced`, or `strong`.
- Use relationship expansion only when the user asks for supply chain, customers, suppliers, sector readthrough, cross-industry transmission, or a scope that cannot be answered by one company alone.

## Forbidden

- Do not choose physical index paths, BM25 paths, DuckDB paths, or reranker models.
- Do not set final investment conclusions.
- Do not give Memo Writer or Verifier retrieval authority.
