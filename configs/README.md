# Application configuration

These files provide maintained application defaults and source examples. Credentials, dataset-specific permission records, indexes, reports and run history belong to the deployment's own storage.

| Directory | Purpose |
| --- | --- |
| `sources/` | SEC company/earnings selection and industry API contracts; customize companies and dates before capture |
| `retrieval/` | Financial question facets, typed query routing and source intake rules |
| `financial_facts/` | Reusable metric definitions; source bindings and the research cutoff are supplied when materializing a captured snapshot |
| `research/` | Role/model budgets, research-session settings and a reference research template |
| `control_plane/` | Optional Dagster persistence configuration |

For a newly captured CompanyFacts snapshot, use `scripts/data_retrieval/materialize_companyfacts_snapshot.py` with explicit `--snapshot`, `--as-of` and a new `--output` directory. It generates a dataset policy from the reusable financial rules and verified capture bindings.

Reference-case research additionally needs a verified external resource package; see [deployment](../deploy/agent_server/README.md). Templates do not grant permission to reuse somebody else's data or certify a new company's financial definitions.

`materialize_companyfacts_snapshot.py` creates a source-bound policy and database from an explicit captured snapshot. `build_company_financial_mart.py --policy <generated-policy.json>` rebuilds that dataset and evaluates only checks included in its policy. Without supplied checks the result remains `acceptance_pending`; it is not a reference-case approval. Generated results belong under `data/` or an external directory.
