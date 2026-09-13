#!/bin/sh
set -eu

# Process readiness is insufficient. Verify all four real TCP credentials and
# the exact secret-free FIN runtime v1.1 catalog before Agent Server may start.
# Never print credential values or resolved connection strings.
: "${POSTGRES_DB:?missing PostgreSQL database name}"
: "${POSTGRES_USER:?missing PostgreSQL bootstrap-admin user}"
: "${POSTGRES_PASSWORD:?missing PostgreSQL bootstrap-admin password}"
: "${FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD:?missing LangGraph PostgreSQL password}"
: "${FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD:?missing FIN runtime PostgreSQL password}"
: "${FINSIGHT_FIN_RUNTIME_OPERATOR_POSTGRES_PASSWORD:?missing FIN runtime operator PostgreSQL password}"

for credential in \
    "$POSTGRES_PASSWORD" \
    "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" \
    "$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD" \
    "$FINSIGHT_FIN_RUNTIME_OPERATOR_POSTGRES_PASSWORD"
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
[ "$POSTGRES_PASSWORD" != "$FINSIGHT_FIN_RUNTIME_OPERATOR_POSTGRES_PASSWORD" ]
[ "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" != "$FINSIGHT_FIN_RUNTIME_OPERATOR_POSTGRES_PASSWORD" ]
[ "$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD" != "$FINSIGHT_FIN_RUNTIME_OPERATOR_POSTGRES_PASSWORD" ]

export PGCONNECT_TIMEOUT=3
export PGSSLMODE=disable

fingerprint_sql=/opt/fin-insight/040-fin-runtime-schema-fingerprint.sql
expected_fingerprint_source_sha256=5de1648a55382aa3acc20297bbdd8a3694a2e0a69ee04814cc6499c0da332a66
expected_v1_1_catalog_sha256=f37dbff53d47dc59bb5390bdcf46a5f51b354ffa61ff5b8c596180d3aa169f7e
normalized_fingerprint_sql=$(mktemp /tmp/fin-runtime-readiness-v1-1.XXXXXX.sql)
fingerprint_rows=$(mktemp /tmp/fin-runtime-readiness-v1-1.XXXXXX.rows)
trap 'rm -f "$normalized_fingerprint_sql" "$fingerprint_rows"' EXIT HUP INT TERM

is_sha256() {
    [ "${#1}" -eq 64 ] || return 1
    case "$1" in
        *[!0-9a-f]*) return 1 ;;
    esac
}

[ -f "$fingerprint_sql" ]
tr -d '\r' < "$fingerprint_sql" > "$normalized_fingerprint_sql"
actual_fingerprint_source_sha256=$(sha256sum "$normalized_fingerprint_sql" | awk '{print $1}')
[ "$actual_fingerprint_source_sha256" = "$expected_fingerprint_source_sha256" ]
is_sha256 "$expected_v1_1_catalog_sha256"

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
check_login "$FINSIGHT_FIN_RUNTIME_OPERATOR_POSTGRES_PASSWORD" fin_runtime_operator

# Running the fingerprint as fin_runtime_app proves its real TCP login and its
# least-privilege read surface. Any query error or catalog drift stays unhealthy.
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
[ "$actual_catalog_sha256" = "$expected_v1_1_catalog_sha256" ]
