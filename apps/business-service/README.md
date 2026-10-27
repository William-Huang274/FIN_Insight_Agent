# FinSight research intake

## Current delivery boundary

The organization project browser supports input preparation, initial orientation,
explicit continuation and reconciliation when the OIDC BFF, resource spaces,
organization runtime and start feature gate are configured. Current-reader report,
citation and export access is separate from creator-only execution permission.
See the [browser workflow and staged acceptance](../../docs/engineering/organization_research_browser.zh-CN.md)
for the current acceptance gaps. This does not switch an existing deployment.
The migration notes below describe incremental schema responsibilities, not the
current availability of the complete workflow.

Optional Spring Boot 3.5 / Java 21 business service. PostgreSQL owns project
research requests and submission receipts; the existing Python BFF owns login,
current project authorization and native research access. Agent Server remains
the executor. This service has no model SDK, retrieval implementation or billing
ledger. Research intake supports personal projects on one BFF host. Flyway V2 also
adds organization resource spaces, membership, publication access and audit records;
it does not turn existing personal research projects into shared projects.

Flyway V3 adds new organization project metadata, project members and revisioned
management. Java is their sole authority; Python still owns legacy personal
projects. Project membership does not grant space access. Flyway V4 adds project
references to same-organization team publications with current project AND source
authorization, revisioned changes and audit. V4 alone does not enable shared research.
Flyway V5 adds immutable organization research input preparations. Current project
access and every selected source are required to read a preparation; researchers
can explicitly verify frozen originals through the BFF. This creates no native
thread/run and does not enable shared execution. See
[organization input preparation](../../docs/engineering/organization_research_inputs.zh-CN.md).
Flyway V6 adds internal execution authorization bindings. A separate workload
credential can request current all-input access for a bound principal, but cannot
manage projects or impersonate a browser user. This does not create a native run.
See [scoped organization evidence tools](../../docs/engineering/organization_execution_access.zh-CN.md).
The opt-in browser retrieval adapter uses a delegated-user `navigation-access`
verdict that checks both the current reader and saved execution principal in Java.
Only the immutable manifest payload is reusable; every verdict rechecks current
project/source permissions and binding state, including on cached results.
Flyway V7 adds one durable native draft preparation command per binding, with
frozen configuration, one dispatch attempt and read-only reconciliation. Native
threads use organization ownership; personal research entry points cannot read
or start them. V7 alone does not enable shared runs. See
[organization native drafts](../../docs/engineering/organization_native_drafts.zh-CN.md).
See [project resource links](../../docs/engineering/project_resource_links.zh-CN.md)
and [organization project scope and static
acceptance cases](../../docs/engineering/organization_projects.zh-CN.md).

See [deployment, protocol and qualification](../../docs/engineering/java_research_intake.zh-CN.md).
See [the common Java/Python version and continuation contract](../../docs/engineering/java_python_integration.zh-CN.md)
for execution snapshots, legacy replay limits and static integration coverage.
See [resource spaces and explicit publication](../../docs/engineering/resource_spaces.zh-CN.md)
for organization-owned personal workspaces, team access and custody boundaries.

## Build and qualify

Install JDK 21 and start Docker. Maven Wrapper downloads Maven 3.9.11 with a
checked SHA-256. Testcontainers creates its own disposable PostgreSQL instance.

```bash
./mvnw verify
```

On Windows use `./mvnw.cmd verify`. No repository-private data or paid API calls
are needed. `target/business-service-0.1.0.jar` is the executable artifact.

## Configure

Supply these environment variables outside Git:

- `FINSIGHT_BUSINESS_JDBC_URL`: JDBC URL for a **dedicated business database**.
- `FINSIGHT_BUSINESS_DB_USER` and `FINSIGHT_BUSINESS_DB_PASSWORD`: that database's credentials.
- `FINSIGHT_BUSINESS_SHARED_SECRET`: at least 32 UTF-8 bytes, shared with the BFF.
- `FINSIGHT_ORGANIZATION_RUNTIME_SECRET`: optional separate secret, at least 32 UTF-8 bytes;
  enables the internal runtime authorization endpoint. Must differ from the BFF secret.
- `FINSIGHT_PYTHON_INTAKE_URL`: loopback BFF URL, defaults to `http://127.0.0.1:8765`.
- `FINSIGHT_BUSINESS_PORT`: defaults to `8095`, listening on `127.0.0.1`.

On the BFF set the same shared secret and `FINSIGHT_BUSINESS_API_URL` to the
loopback business URL. Coordinate a BFF restart after configuring its existing
research profile, published library and attachment store.

```bash
java -jar target/business-service-0.1.0.jar
```

Open `/workspace/projects` through the BFF. Flyway applies the business schema;
it does not alter Agent Server tables. Keep both service ports private. Login and
browser sessions stay at the BFF. Do not use local identity mode for shared access.

To enable resource spaces, the BFF additionally requires
`FINSIGHT_AUTH_MODE=oidc_product` and `FINSIGHT_RESOURCE_SPACES_ENABLED=1`.
Existing private project assets are not automatically shared. Publications are
independent fixed copies in the Python `organization-assets` store; back up this
store alongside business PostgreSQL. Live database ACLs and personal-space takeover
are not included. Organization Agent inputs use the separately configured execution
authority and frozen resource manifest described in the browser workflow.

## Execution scope compatibility

Flyway V9 adds one explicit orientation-to-research continuation command per
execution, independent of the initial start receipt. It pins the predecessor run,
checkpoint and state digest, preserves frozen inputs/configuration, and binds a
new native run exactly once. Unknown dispatches are reconciled without retries.
The organization project results page uses current-viewer read APIs; creator-only
browser controls call these distinct preparation/start/continuation commands. See
[organization continuation](../../docs/engineering/organization_native_continuation.zh-CN.md).

Organization research has a separate current-reader authorization endpoint.
Project viewers with access to every frozen input can read prepared research
without impersonating its creator or obtaining permission to execute it.
The BFF rechecks this authority around state/export I/O and event delivery;
personal research routes remain closed to organization threads. See
[organization research reads](../../docs/engineering/organization_research_reads.zh-CN.md).

`execution.require_all_branches` defaults to `false` when omitted. It accepts
only JSON booleans, and `true` requires `mode: standard`. Java persists the
validated selection in new preparation commands. Historical saved command JSON,
request fingerprints and frozen thread configuration digests are not rewritten
to add this default. The organization BFF validates the effective options while
freezing the exact saved command representation. See the
[shared execution contract](../../docs/engineering/java_python_integration.zh-CN.md)
for delayed phase construction and scope compatibility checks.

## Frozen organization retrieval releases

Flyway V10 stores append-only project retrieval releases. A preparation may
specify `retrieval_release_id`; Java matches the complete frozen resource inputs
and saves `manifest.retrieval_index` (release ID, index/matrix SHA-256, model,
dimensions and projection). Omitted releases leave historical manifest shapes
and digests unchanged. Publishing a newer release does not upgrade an existing
preparation.

Operators prepare immutable Python indexes under
`FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT/<organization>/releases/<release>/`.
Project managers register a prepared release through the BFF route
`POST /api/v1/asset-workspace/organization-projects/{project}/research-drafts/{draft}/retrieval-releases/{release}/register`.
The BFF verifies the original text projection, matrix integrity and current
permissions before asking Java to register server-derived metadata. The generic
browser business gateway does not permit direct release registration. GET
`/v1/workspaces/projects/{project}/retrieval-releases` lists currently readable
releases; selecting one in the preparation UI does not confer source access.

Python verifies the frozen release before prepare/start/continuation and source
search. New queries require explicit server configuration
`FINSIGHT_ORGANIZATION_QUERY_EMBEDDING=qwen` and `QWEN_API_KEY`; their model must
match the index. The query cache is separate from permissions and scoped to the
organization, index and model. Concurrent followers wait up to 45 seconds for
the first receipt; they never send another provider request. Failed or unknown
requests remain blocked for reconciliation. No generation or paid rerank is
enabled by this setting. Back up retained releases and query receipts with the
business database and organization originals.

## Organization report questions and revisions

Flyway V11 adds `organization_report_command` without rewriting prior commands.
Enable the Java service with `FINSIGHT_ORGANIZATION_REPORT_ACTIONS_ENABLED=true`
and the BFF with the same variable set to `1` only on a qualified deployment.
The default is disabled. This flag does not grant access to any source.

The original initiator submits an explicit `ask` or `revise` command after a
completed native human-review checkpoint. Each command freezes the predecessor
run, checkpoint, state digest, report version and report digest. A targeted
revision additionally binds a saved citation and the same request ID. Runtime
model options remain those of the original preparation. Manual completion and
acceptance are not exposed through these organization commands.

The Java request ID is immutable and the dispatch operation ID is server-owned.
A native checkpoint can be consumed by one non-rejected command. This does
**not** make a report version single-use: questions can keep the report unchanged
while producing a fresh checkpoint for the next question. Current permission on
the project and every frozen input is checked before receipt replay and native
admission. The real `human_review` node also compares `Command.resume` with the
saved action before selecting a writer or any other action branch.

Browser routes under
`/api/v1/organization-projects/{project}/research/{execution}` provide
`report-action-preview`, `report-commands` and
`report-commands/{command}/reconcile`. Writes delegate to Java; the browser does
not call the native SDK. Reconciliation searches the exact operation across
native pagination and never resubmits. A received command means dispatch was
acknowledged, not that the report is correct or the run has completed.
After an unknown or failed run, preserve the command and audit records; this
slice does not add an automatic failed-run retry.

## Failure semantics

See [request lifecycle and fault qualification](../../docs/engineering/java_intake_recovery.zh-CN.md)
for operation ownership, recovery limits and reproducible synthetic fault cases.

Preparing and starting have separate, permanent operation IDs and saved JSON
bytes. A database compare-and-set claims one dispatch attempt. Timeouts, dropped
responses and process death keep the operation unknown. Reconcile only reads
the existing BFF receipt or the deterministic native thread and exact operation
tag; it never dispatches research. This is not a distributed exactly-once claim.

Do not edit command state back to `ready`, clear receipt stores or reconstruct a
task by choosing its newest run. Back up business PostgreSQL alongside Python
receipts/project assets and the native runtime. Retain failed and unknown records.
