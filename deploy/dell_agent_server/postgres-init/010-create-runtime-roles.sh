#!/bin/sh
set -eu

: "${FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD:?missing LangGraph PostgreSQL password}"
: "${FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD:?missing FIN runtime PostgreSQL password}"
: "${POSTGRES_PASSWORD:?missing PostgreSQL bootstrap-admin password}"

for credential in \
    "$POSTGRES_PASSWORD" \
    "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" \
    "$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD"
do
    case "$credential" in
        *[!A-Za-z0-9._~-]*)
            echo "PostgreSQL runtime passwords must be URL-safe" >&2
            exit 1
            ;;
    esac
    if [ "${#credential}" -lt 16 ]; then
        echo "PostgreSQL runtime passwords must contain at least 16 characters" >&2
        exit 1
    fi
done

if [ "$POSTGRES_PASSWORD" = "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" ] \
    || [ "$POSTGRES_PASSWORD" = "$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD" ] \
    || [ "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" = "$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD" ]
then
    echo "PostgreSQL bootstrap and runtime passwords must be distinct" >&2
    exit 1
fi

# Passwords are expanded only into psql stdin. Before any statement containing
# them is sent, this connection disables statement logging and suppresses the
# error-statement/parameter payload. This keeps an unexpected server-side DDL
# failure from copying the whole password-bearing DO block into PostgreSQL
# logs. The values are never command-line arguments or shell output.
PGOPTIONS="-c log_statement=none -c log_min_error_statement=panic -c log_parameter_max_length=0 -c log_parameter_max_length_on_error=0" \
psql --set=ON_ERROR_STOP=1 \
    --set=VERBOSITY=terse \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" <<SQL
CREATE EXTENSION IF NOT EXISTS vector;

DO \$roles\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'langgraph_runtime') THEN
        EXECUTE format(
            'CREATE ROLE langgraph_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L',
            '$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD'
        );
    ELSE
        EXECUTE format(
            'ALTER ROLE langgraph_runtime PASSWORD %L',
            '$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fin_runtime_app') THEN
        EXECUTE format(
            'CREATE ROLE fin_runtime_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L',
            '$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD'
        );
    ELSE
        EXECUTE format(
            'ALTER ROLE fin_runtime_app PASSWORD %L',
            '$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fin_runtime_migrator') THEN
        EXECUTE 'CREATE ROLE fin_runtime_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION';
    END IF;
END
\$roles\$;

ALTER ROLE langgraph_runtime NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
ALTER ROLE fin_runtime_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
ALTER ROLE fin_runtime_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE TEMPORARY ON DATABASE postgres FROM PUBLIC;

GRANT CONNECT, CREATE, TEMPORARY ON DATABASE postgres TO langgraph_runtime;
GRANT USAGE, CREATE ON SCHEMA public TO langgraph_runtime;

GRANT CONNECT, CREATE ON DATABASE postgres TO fin_runtime_migrator;
GRANT CONNECT ON DATABASE postgres TO fin_runtime_app;
REVOKE CREATE ON SCHEMA public FROM fin_runtime_app;
SQL
