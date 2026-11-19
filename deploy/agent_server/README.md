# Local deployment

Start in the repository root with Docker Compose v2 or newer and Python 3.10+.

```sh
python scripts/deployment/initialize.py
docker compose config --quiet
docker compose up -d --build
```

Open [Projects](http://127.0.0.1:8765/workspace/projects). The workbench serves the compiled React application and Python API. Java listens on loopback inside the workbench network namespace and connects to its own PostgreSQL database. Flyway installs migrations from `apps/business-service/src/main/resources/db/migration/` as the database owner. The database bootstrap administrator has a separate password. Change `FINSIGHT_WORKBENCH_PORT` in the private `.env` to choose another host port.

The default stack supports a single local user and starts without any external accounts. You can create a project, upload original materials and inspect its Java-backed task list. Native thread history, graph views and model execution require the native stack below.

## Register and sign in on localhost

Docker Compose 2.24.4 or newer supports the HTTPS overlay. Run the environment initializer above once, then prepare a fresh Keycloak realm with the locked Python authentication dependencies. Defaults are HTTPS 18866 for the app and 18443 for the issuer. To select other free ports, pass `--https-port` and `--issuer-port` to the identity initializer.

```sh
uv run --locked --extra workbench-auth python scripts/deployment/initialize_identity.py
docker compose --env-file .env --env-file .secrets/identity/identity.env -f compose.yaml -f deploy/identity/compose.identity.yaml up -d --build --wait
```

Trust the generated local CA `.secrets/identity/tls/ca.pem` in the browser used for this deployment. Open [the HTTPS workbench](https://localhost:18866/workspace) and select **Register** to create an account in the local Keycloak realm. New accounts can create or join an organization in the workbench. Keycloak owns passwords and serves the account page. The BFF creates a short-lived secure browser session and Java checks organization and project access on requests. The overlay publishes the app and issuer only on host loopback. Java uses an internal HTTP callback in the shared container network namespace.

Keep `.secrets/identity/` and its PostgreSQL volume private. Use the same environment files and Compose project name on subsequent starts. The identity initializer creates new keys for a new installation and refuses existing directories. A separate Keycloak administrator login is generated under `credentials.private.json`. To add native research while retaining login, include the same overlays in every command:

```sh
docker compose --env-file .env --env-file .secrets/identity/identity.env -f compose.yaml -f deploy/agent_server/compose.native.yaml -f deploy/identity/compose.identity.yaml up -d --build --wait
```

## Research and conversation

1. Keep the generated `.env` and `.secrets/personal-research.key` private. Set your own `LANGSMITH_API_KEY` for the licensed native Agent Server. Its runtime requires tracing. Trace inputs and outputs are hidden. The fixed trace project identifier is created in the account associated with your key.
2. For personal research, save your DeepSeek credential in the workbench. Python encrypts the credential under the current identity. The BFF and the native worker share `/app/state/personal-keys` and read the same read-only master key. Signed-in conversations use the owner's personal key, including follow-ups and note revisions. The host-key fallback is opt-in for private single-user deployments. [Personal credential setup](../../apps/workbench/README.md#personal-research)
3. For the single-user stack, run these commands with the same Compose project and location as the original deployment.

```sh
docker compose -f compose.yaml -f deploy/agent_server/compose.native.yaml config --quiet
docker compose -f compose.yaml -f deploy/agent_server/compose.native.yaml up -d --build
docker compose -f compose.yaml -f deploy/agent_server/compose.native.yaml ps
```

The overlay adds a private native API, a dedicated pgvector PostgreSQL instance for threads and checkpoints, and Redis for queue coordination. It registers research, conversation and delegated-task graphs. Open [Research](http://127.0.0.1:8765/workspace/session) to prepare a new task. Starting it or sending a conversation message uses the selected provider and may incur charges. Recover failed or unknown submissions through their existing records. An infrastructure restart does not authorize resubmission.

## Organization search

To try a free keyword search, bind a published document on a research input sheet and search its text. [Search bound originals with BM25](../organization/README.md#search-your-own-documents-with-bm25)

For a reusable hybrid index, use the [organization retrieval setup](../organization/README.md) to export the authorized source projection, publish document vectors and BM25 postings, register a fixed release, and enable optional query embeddings or reranking.

## Data and storage

* **SEC company data.** Set `FINSIGHT_SEC_CONTACT_EMAIL` to your own real address in `.env` and recreate the workbench after changes. From a project, select the SEC source, enter a ticker and ten-digit CIK, then refresh. Capture retains the original companyfacts and submissions JSON, source URL, time and digest. For command-line filing ingestion, set `SEC_USER_AGENT` to your own application name and contact address. Example from the source checkout:

  ```sh
  uv run --no-sync python scripts/data_sec/download_sec_filings.py --tickers MSFT --years 2023 --form-types 10-K
  ```

* **Financial SQL.** A project SEC refresh writes a versioned source snapshot. A separate prebuilt financial fact mart can be supplied as `conversation_fact_mart` in session settings. Mount the same immutable SQLite file at that absolute container path, read-only, on both workbench and native services. The shipped `settings.json` starts with a writable audit directory. No external data package is required to start the stack.
* **Business SQL.** Run `docker compose exec business-db psql -U postgres -d finsight` for local administration. Query migration history with `SELECT version, success FROM flyway_schema_history ORDER BY installed_rank`. Research identity SQL is under `src/sec_agent/agent_runtime/sql/`. Native setup applies the identity/lifecycle scripts to its own database. Budget and dispatch SQL 003–005 apply to a separately provisioned budget database when enabling explicit budget bindings.
* **Backup.** Securely back up the business and native PostgreSQL databases, the identity database and private identity directory when sign-in is enabled, any separate funded-execution budget database, the workbench state volume, the deployment’s private environment and the matching Fernet key. The workbench volume includes attachments, project metadata, encrypted user credentials, execution receipts and call records. Preserve snapshots and read-only external data alongside their identifiers. Stop writers before a coordinated backup. A new Fernet key cannot decrypt old credentials.
* **Shutdown.** Use `docker compose -f compose.yaml -f deploy/agent_server/compose.native.yaml stop` for the full stack, or `docker compose stop` for the default stack. Keep the Compose project name stable on restart so it reuses the named volumes.

## Host Java and Python

The two application services may also run on the same host loopback with Java 21, Python 3.11 and Node 22. Build the frontend with `npm ci` and `npm run build` in `apps/workbench/frontend`. Install the Python extras for `agent-runtime`, `external-search`, `workbench-auth` and `workbench-delivery`. Run the Maven wrapper with `-DskipTests package` in `apps/business-service`.

Provision a dedicated PostgreSQL database named `finsight` with an owner named `finsight` and the password from the deployment environment. With this database available on host port 5432, run each service in a separate terminal:

```sh
uv run --no-sync python scripts/deployment/host_service.py java
uv run --no-sync python scripts/deployment/host_service.py workbench
```

`--db-port`, `--business-port`, `--ui-port`, `--native-port` and `--state-directory` select isolated endpoints and storage. Host mode requires a separately configured native endpoint for research. The default Compose deployment keeps its database private to its network.

For the optional funded GPT-6.2 Sol high / DeepSeek Flash organization profile, use the checked-in settings generator, explicit budget funding command, and production readiness check in the [Workbench deployment instructions](../../apps/workbench/README.md#provision-the-optional-organization-model-combination).
