# Dell Agent Server — local demo boundary

This is the only supported serving stack for the Dell reference vertical:
LangGraph Agent Server `0.13.3`, LangSmith tracing, Redis and pgvector-backed
PostgreSQL. It does not provide a FastAPI, SQLite, direct-invoke or no-LangSmith
fallback.

## Security boundary

This Compose project is **not a production deployment**. Agent Server uses noop
authentication in this local setup. Loopback binding is the trust boundary:
only `127.0.0.1:8123` is published, while PostgreSQL and Redis have no host
ports. Do not change the API binding to `0.0.0.0`, expose it through a reverse
proxy, or use it on a shared/untrusted host without a separately reviewed
authentication and production deployment design.

The Compose and Dockerfile contain no credential values. Put real values only
in the repository-root `.env`, which is excluded by both `.gitignore` and
the Dockerfile-specific deny-by-default build-context allowlist. The image only
copies `pyproject.toml`, `README.md`, and `src/`; local data, captures, reports,
Git state and runtime artifacts are neither sent in the build context nor
copied into the image. Compose uses that file only for variable interpolation
and passes the four explicitly listed product variables to Agent Server; it
does not inject unrelated repository credentials. At minimum, the local file
must define:

```dotenv
LANGSMITH_API_KEY=<local secret>
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=fin-insight-dell-reference-vertical
DEEPSEEK_API_KEY=<local secret>
FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD=<strong URL-safe local secret>
```

Use a URL-safe PostgreSQL password because the same value is interpolated into
the internal `POSTGRES_URI`. Never commit `.env`, paste its contents into a
receipt, or add a credential value to Compose.

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

Even after the services start, the current Dell graph intentionally fails
closed before opening data or provider resources until its separate Owner data
authority gate is approved. That refusal is part of the single runtime path;
it is not a fallback.
