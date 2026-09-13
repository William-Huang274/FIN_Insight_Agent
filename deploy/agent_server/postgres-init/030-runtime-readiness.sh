#!/bin/sh
set -eu

# A PostgreSQL process accepting connections is not enough. A reused named
# volume may have skipped docker-entrypoint-initdb.d and still satisfy
# pg_isready. Check every credential actually used by this local stack and the
# exact secret-free FIN identity catalog fingerprint before allowing Agent
# Server to start. Never print credential values or resolved connection strings.
: "${POSTGRES_DB:?missing PostgreSQL database name}"
: "${POSTGRES_USER:?missing PostgreSQL bootstrap-admin user}"
: "${POSTGRES_PASSWORD:?missing PostgreSQL bootstrap-admin password}"
: "${FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD:?missing LangGraph PostgreSQL password}"
: "${FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD:?missing FIN runtime PostgreSQL password}"

for credential in \
    "$POSTGRES_PASSWORD" \
    "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" \
    "$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD"
do
    case "$credential" in
        *[!A-Za-z0-9._~-]*)
            exit 1
            ;;
    esac
    [ "${#credential}" -ge 16 ] || exit 1
done

[ "$POSTGRES_PASSWORD" != "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" ]
[ "$POSTGRES_PASSWORD" != "$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD" ]
[ "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" != "$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD" ]

export PGCONNECT_TIMEOUT=3
export PGSSLMODE=disable

fingerprint_sql=/opt/fin-insight/040-fin-runtime-schema-fingerprint.sql
expected_fingerprint_source_sha256=dec88b731a59d696509c184cf45ea1344d5840d7aa0c07515b3902b3de9ddd00
expected_catalog_sha256=28c2bb8501d78ca3b43e1a490acae050df46b8226d2c2511a34b99a1723ec4a8
normalized_fingerprint_sql=$(mktemp /tmp/fin-runtime-readiness.XXXXXX.sql)
fingerprint_rows=$(mktemp /tmp/fin-runtime-readiness.XXXXXX.rows)
trap 'rm -f "$normalized_fingerprint_sql" "$fingerprint_rows"' EXIT HUP INT TERM

[ -f "$fingerprint_sql" ]
tr -d '\r' < "$fingerprint_sql" > "$normalized_fingerprint_sql"
actual_fingerprint_source_sha256=$(sha256sum "$normalized_fingerprint_sql" | awk '{print $1}')
[ "$actual_fingerprint_source_sha256" = "$expected_fingerprint_source_sha256" ]

check_login() {
    credential=$1
    role=$2
    PGPASSWORD="$credential" psql \
        --host=127.0.0.1 \
        --username="$role" \
        --dbname="$POSTGRES_DB" \
        --no-password \
        --tuples-only \
        --no-align \
        --set=ON_ERROR_STOP=1 \
        --command='SELECT 1' \
        >/dev/null 2>&1
}

check_login "$POSTGRES_PASSWORD" "$POSTGRES_USER"
check_login "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" langgraph_runtime

# Running the fingerprint as fin_runtime_app doubles as that role's real TCP
# authentication check. Any query error, missing catalog fact or digest drift
# keeps PostgreSQL unhealthy.
if ! PGPASSWORD="$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD" psql \
    --host=127.0.0.1 \
    --username=fin_runtime_app \
    --dbname="$POSTGRES_DB" \
    --no-password \
    --tuples-only \
    --no-align \
    --set=ON_ERROR_STOP=1 \
    --file "$normalized_fingerprint_sql" \
    > "$fingerprint_rows" 2>/dev/null; then
    exit 1
fi

actual_catalog_sha256=$(sha256sum "$fingerprint_rows" | awk '{print $1}')
[ "$actual_catalog_sha256" = "$expected_catalog_sha256" ]
