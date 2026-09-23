# FinSight research intake

Optional Spring Boot 3.5 / Java 21 business service. PostgreSQL owns project
research requests and submission receipts; the existing Python BFF owns login,
current project authorization and native research access. Agent Server remains
the executor. This service has no model SDK, retrieval implementation or billing
ledger. The first release supports personal projects on one BFF host.

See [deployment, protocol and qualification](../../docs/engineering/java_research_intake.zh-CN.md).

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

## Failure semantics

Preparing and starting have separate, permanent operation IDs and saved JSON
bytes. A database compare-and-set claims one dispatch attempt. Timeouts, dropped
responses and process death keep the operation unknown. Reconcile only reads
the existing BFF receipt or the deterministic native thread and exact operation
tag; it never dispatches research. This is not a distributed exactly-once claim.

Do not edit command state back to `ready`, clear receipt stores or reconstruct a
task by choosing its newest run. Back up business PostgreSQL alongside Python
receipts/project assets and the native runtime. Retain failed and unknown records.
