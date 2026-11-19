# Business service

Spring Boot and PostgreSQL store project roles, document versions, permissions and research submissions. Flyway applies the schema migrations under `src/main/resources/db/migration`.

Use Java 21 and the Maven wrapper to build the service. The default Compose stack sets up its dedicated database and connects it to the Python workbench. See the [deployment guide](../../deploy/agent_server/README.md) and [Chinese quickstart](../../docs/public/quickstart.zh-CN.md).
