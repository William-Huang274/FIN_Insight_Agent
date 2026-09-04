# Dell Agent Server — local demo boundary

This is the only supported serving stack for the Dell reference vertical:
LangGraph Agent Server `0.13.3`, LangSmith tracing, Redis and pgvector-backed
PostgreSQL. It does not provide a FastAPI, SQLite, direct-invoke or no-LangSmith
fallback.

## Security boundary

This Compose project is **not a production deployment**. Agent Server uses noop
authentication in this local setup. Loopback binding is the trust boundary:
only `127.0.0.1:${FINSIGHT_AGENT_SERVER_HOST_PORT:-18123}` is published, while PostgreSQL and Redis have no host
ports. Do not change the API binding to `0.0.0.0`, expose it through a reverse
proxy, or use it on a shared/untrusted host without a separately reviewed
authentication and production deployment design.

The Compose and Dockerfile contain no credential values. Put real values only
in the repository-root `.env`, which is excluded by both `.gitignore` and the
Dockerfile-specific deny-by-default build-context allowlist. The image copies
only `pyproject.toml`, `uv.lock`, `README.md`, Python source files below `src/`,
the packaged FIN identity and remote-create lifecycle SQL migrations, and five
exact non-secret control documents: the Dell foundation, structured-agent
configuration, physical-route candidate, Reviewed Evidence enrichment candidate,
and separate Owner data decision. The
allowlist re-excludes `__pycache__` and compiled Python artifacts after
admitting source directories. It does not copy a whole `src/` or `configs/`
tree. Local corpus rows, Reviewed Evidence bodies, S2 data, external captures,
reports, Git state and runtime artifacts are neither sent in the build context
nor copied into the image.

Compose uses `.env` only for explicit variable interpolation. Secret values are
passed only through the listed Agent Server/PostgreSQL environment fields. The
six `FINSIGHT_DELL_*_HOST_*` values below are used only as bind-mount sources and
are not injected into the container environment or receipts. The local file
must define exactly these five secrets for this stack:

```dotenv
LANGSMITH_API_KEY=<local secret>
FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD=<strong URL-safe local secret>
FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD=<distinct strong URL-safe local secret>
FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD=<distinct strong URL-safe local secret>
FINSIGHT_FIN_RUNTIME_OPERATOR_POSTGRES_PASSWORD=<fourth distinct strong URL-safe local secret>
```

Tracing is fixed to `true`, the LangSmith project is fixed to
`fin-insight-dell-reference-vertical`, and trace inputs/outputs are hidden by
the checked-in `LANGSMITH_HIDE_INPUTS=true` and
`LANGSMITH_HIDE_OUTPUTS=true` policy. This configuration is intended to hide
graph and tool payloads while retaining topology, timing, status and bounded
correlation metadata; only an exact live qualification trace can establish
that the pinned client observed that behavior for that attempt. It is not a
blanket privacy guarantee, and UUIDs/digests needed for correlation still leave
the workstation through LangSmith observability.
Server job concurrency is fixed to four in Compose; putting alternate values
for those names in `.env` does not override the checked-in policy. The
following source paths already have
workstation defaults and belong in `.env` only when the same digest-bound data
is stored somewhere else:

```dotenv
FINSIGHT_DELL_S1_NODES_HOST_PATH=Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/rag_mature_stack/retrieval_qualification/dell_rag_full_stack_preview_attempt_20260902_03/retrieval_nodes.jsonl
FINSIGHT_DELL_REVIEWED_BASE_PACK_HOST_PATH=D:/FIN_Insight_Agent/data/workbench_private/fin_0_1_3_s1_dell_direct_source_evidence/r4/successor/pack.json
FINSIGHT_DELL_REVIEWED_OVERLAY_HOST_PATH=Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/evidence_overlay/attempts/20260902T051005+0800-dell-fy27q2-sec-ex99-review-a01/reviewed-evidence-case-projection.json
FINSIGHT_DELL_S2_RESULT_HOST_PATH=Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/s2/s2_exact_period_contract_successor_20260902_r1/company_financial_fact_mart_result.json
FINSIGHT_DELL_S2_MART_HOST_PATH=Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/s2/s2_exact_period_contract_successor_20260902_r1/company_financial_facts.sqlite
FINSIGHT_DELL_EXTERNAL_PACK_HOST_ROOT=Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/external_exact_url_qualification/dell_external_exact_url_zero_model_20260902_r12
```

`DEEPSEEK_API_KEY` may remain in the ignored `.env` for a future separately
approved paid/model gate. The current zero-model Compose service deliberately
does not inject it into the API container. LangSmith tracing remains mandatory.

Use four distinct URL-safe PostgreSQL passwords. The first is bootstrap-admin
only, the second belongs to the non-superuser Agent Server role, the third
belongs to `fin_runtime_app`, which receives only schema usage plus
`SELECT`/`INSERT` and sequence access on `fin_runtime`, and the fourth belongs
to the independent `fin_runtime_operator` recovery authority. Never commit `.env`,
paste its contents into a receipt, or add a credential value to Compose. The
role bootstrap script runs automatically only for a fresh PostgreSQL volume;
reused volumes require the explicit replay below. PostgreSQL is not considered
healthy until all four PostgreSQL credentials authenticate over TCP and
the FIN identity and remote-create lifecycle schema matches a digest-pinned,
secret-free admitted catalog projection fingerprint. That projection covers
the version comment and the role, relation, column, default, constraint, index,
trigger, function-body, ownership, and grant surfaces consumed by this seam—not
every PostgreSQL catalog field. This prevents
an old, partial or silently drifted named volume that skipped
`docker-entrypoint-initdb.d` from appearing ready.

When intentionally reusing a volume, first stop or drain `langgraph-api` so the
v1.0 writer cannot race the write-incompatible v1.1 migration. The volume must
contain either the exact frozen v1.0 predecessor or the exact v1.1 catalog. Start
PostgreSQL alone, then run the reviewed credential bootstrap and digest-pinned
migrator explicitly:

```powershell
docker compose --env-file .env -f deploy/dell_agent_server/compose.yaml stop langgraph-api
docker compose --env-file .env -f deploy/dell_agent_server/compose.yaml up -d langgraph-postgres
docker compose --env-file .env -f deploy/dell_agent_server/compose.yaml exec -T langgraph-postgres /bin/sh /docker-entrypoint-initdb.d/010-create-runtime-roles.sh
docker compose --env-file .env -f deploy/dell_agent_server/compose.yaml exec -T langgraph-postgres /bin/sh /docker-entrypoint-initdb.d/025-install-fin-runtime-lifecycle-v1-1.sh
docker compose --env-file .env -f deploy/dell_agent_server/compose.yaml up -d
```

The first `up` may correctly report PostgreSQL as unhealthy until the two
explicit steps finish. The v1.1 installer has exactly three accepted routes:
an absent schema runs v1.0 then v1.1 in one transaction; an exact v1.0 catalog
runs only the reviewed v1.1 migration; and an exact v1.1 catalog is a no-op. It
refuses every unversioned, partial or drifted schema—including changed
constraints or function bodies—instead of stamping it as current. Existing v1.0
rows remain readable, but after migration every new final server-run binding
requires the durable PENDING/optional ORPHAN/RECONCILED lifecycle, so old writers
must not remain in service. Do not replace migration with deletion of the named
volume unless its contents have been separately audited and deletion has been
authorized.

The checked-in v1.1 installer and readiness script pin the catalog SHA-256
obtained from the pinned PostgreSQL image after the final 002 migration. The
v1.0 predecessor hash was independently captured after replaying the current
role bootstrap, including `fin_runtime_operator`, and before applying 002.
Both values come from the unchanged secret-free fingerprint query against real
PostgreSQL; they are not inferred from SQL text.
The bootstrap rejects short, non-URL-safe or reused passwords before sending
role DDL; its password-bearing session disables statement and error-parameter
logging before any secret-bearing SQL is sent.

## Runtime data mounts

Only the `langgraph-api` service receives data mounts. PostgreSQL and Redis do
not receive corpus or evidence files. Each mount uses Compose long syntax with
`read_only: true` and `create_host_path: false`; a missing or misspelled source
therefore fails instead of creating an empty host directory. The container sees
only stable Linux paths:

| Frozen resource | Container path | Expected SHA-256 / boundary |
| --- | --- | --- |
| S1 structured nodes | `/run/fin-insight/s1/retrieval_nodes.jsonl` | `f7fbf9f43a68933bad52146c3a8aa3c9a1b52bba81e4e804c2b05a0aff9d0817` / 1,025 nodes |
| Reviewed base pack | `/run/fin-insight/reviewed/base/pack.json` | `b28afc38da5d82d8656f81d9c4b382f0e0b664ba4f212370482f32649e1c73a1` / 55 evidence items |
| Reviewed overlay | `/run/fin-insight/reviewed/overlay/reviewed-evidence-case-projection.json` | `1479e49f0cde7166fe6474a74b666dfb646b31a5291f1317689aaa6bc8391eb9` / 6 evidence items |
| S2 result | `/run/fin-insight/s2/company_financial_fact_mart_result.json` | `dd2c92400de777867545de2c41b975d1f07ca6060f4ed431075b7081ab16ed82` / 1,319 observations |
| S2 SQLite mart | `/run/fin-insight/s2/company_financial_facts.sqlite` | `363780c076d0f8766c0ceaafdb8b93d308d339636504b2a263127bb6ca365ac4` / read-only query surface |
| Frozen external r12 attempt | `/run/fin-insight/external-r12` | whole 49-file attempt directory; `manifest.json` SHA-256 `db7eae9aaa8108faadbe7ff07404dd25414e0191b7f62af0c7a42b85a0938b94` |

The whole external attempt directory is required because its manifest binds
relative artifact paths and validates every referenced file. Do not replace any
of these mounts with a whole-drive mount, a repository-wide private-data mount,
or a Docker socket. `FIN_REPO_ROOT` and all data paths passed to the application
are fixed container paths; host `D:/` and `Z:/` values must never enter model
context, LangSmith traces, MCP receipts or user-visible errors.

The two Reviewed mounts jointly preserve all 61 audited items. The separate
Owner decision admits only the 56-item executable index; the five ambiguous
items remain in the audit projection and must not become runtime candidates.

These mounts only make the approved bytes reachable. Runtime loaders must still
verify their exact digests, counts and authority before opening MCP. Reviewed,
local and captured external text may later be sent to a model or LangSmith only
under the separate model/paid/privacy authority; the Owner data decision alone
does not grant that authority.

## Bounded zero-model r8 qualification

The checked-in r8 probe is an acceptance harness around this same server; it is
not a second serving runtime. It uses an explicit qualification Compose overlay,
a separately named `finsight-dell-qualification-20260904-r8a3` project/fresh
volume, the official FIN client, the real Evidence and Finance
MCP lanes, native interrupt/resume, restart/readback, resumable SSE and one
LangSmith project. Run it only from a clean commit:

```powershell
.\.venv\Scripts\python.exe scripts\qualification\agent_server_r8\qualify_live_r8.py
```

For this fresh disposable qualification project, the runner treats
`FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD` as local secret material and derives
four distinct 64-character URL-safe PostgreSQL role passwords in memory. It
does not rewrite `.env`, print a value, or persist a value in the attempt
receipt. Normal manual/product Compose use still requires the four explicit
passwords documented above.

The runner is intentionally fail-preserving: it never uses `down -v`, removes a
volume, overwrites a prior attempt, or retries a create whose outcome is
unknown. It also never injects `DEEPSEEK_API_KEY`. A passing r8 proves only the
single local zero-model attempt described by its receipt. It does not prove
distributed exactly-once, delayed orphan recovery, Redis loss/replacement,
multi-worker HA, product multi-agent execution, model quality, frontend HITL,
or production security. LangSmith remains a real outbound observability path;
the runner requires input/output hiding and verifies the exact r8 traces, while
the bounded run identifiers/digests needed for trace correlation remain
metadata. The base Compose profile remains `product`; the explicit overlay is
qualification-only and must not be used as the product default.

For the pinned Agent Server 0.13.3 semantics, a graph invocation that reaches a
dynamic interrupt has a successful **run** and an interrupted **thread**. The
r8 probe therefore requires the START run to be `success` while the thread is
`interrupted`, the current state has exactly
`next=["qualification_interrupt"]`, and the one qualification interrupt is
present. After RESUME it requires both runs to be `success`, the thread to be
`idle`, and the current state to have no next node or interrupt. These are
different state layers and must not be collapsed into one status field.

The pinned `langsmith==0.12.1` query client must be called without an explicit
`limit`: that public iterator follows server cursors, while a supplied limit is
both sent to `/runs/query` and used as a total client-side cutoff. The r8 probe
consumes one overflow sentinel and admits at most two exact roots and 100 spans
per trace. It also treats exactly one non-root `qualification_interrupt`
`GraphInterrupt` in the START trace as expected LangGraph control flow; every
other trace error remains fatal. This does not claim blanket trace privacy.
The receipt claims only observed input/output hiding, no credential or host/data
locator exposure, and zero unexpected span errors. Normal container traceback
code paths and the bounded correlation metadata can remain visible in the
developer-only LangSmith project.

The current bounded acceptance is fresh attempt
`20260904T060948+0800-zero-model-r8` on source commit
`a76163abf97a7f43031d200c6ac5e05cbe8a677c`. Its immutable PASS receipt is
`Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/agent_server_control_plane/attempts/20260904T060948+0800-zero-model-r8/receipts/dell-agent-server-live-r8-qualification.json`
(file SHA-256
`dd937f332f75903489819d40df0960f5f0e94453c1d0dd721857d1361b5777d4`).
This supersedes r7 only for the bounded zero-model live control-plane claims;
it does not authorize a model, paid successor, product multi-agent run, HITL or
report.

## Local invocation

Run Compose from the repository root and name the ignored env file explicitly:

```powershell
docker compose --env-file .env -f deploy/dell_agent_server/compose.yaml config --quiet
docker compose --env-file .env -f deploy/dell_agent_server/compose.yaml up --build
```

The first command safely validates configuration without rendering secrets to
stdout. Do not run bare `docker compose config` against the real `.env`, because
its rendered output contains resolved credentials. The second command performs a real
image build and service start and therefore must only be run when Docker and the
required local credentials are available. This checked-in configuration alone
does not prove that Agent Server, LangSmith tracing, persistence or restart
parity has passed a live qualification.

Even after the services start, successful bind mounting alone does not authorize
a model, provider, paid call, Evidence admission, S2 write, publication or
public-information-gap claim. Those refusals are part of the single runtime
path; they are not fallbacks.
