#!/bin/sh
set -eu

# Install the exact packaged FIN identity schema during first initialization of
# a fresh PostgreSQL volume. The source SQL is mounted read-only outside
# docker-entrypoint-initdb.d so the official image cannot execute it a second
# time without this digest and transaction boundary.
source_sql=/opt/fin-insight/001_dell_agent_server_identity_v1_0.sql
fingerprint_sql=/opt/fin-insight/040-fin-runtime-schema-fingerprint.sql
expected_source_sha256=8102f5ab615bd616f64bd83f610b2e3c3206a9de023d7e27a48069f39e864209
expected_fingerprint_source_sha256=dec88b731a59d696509c184cf45ea1344d5840d7aa0c07515b3902b3de9ddd00
expected_catalog_sha256=28c2bb8501d78ca3b43e1a490acae050df46b8226d2c2511a34b99a1723ec4a8
normalized_sql=$(mktemp /tmp/fin-runtime-identity.XXXXXX.sql)
normalized_fingerprint_sql=$(mktemp /tmp/fin-runtime-fingerprint.XXXXXX.sql)
fingerprint_rows=$(mktemp /tmp/fin-runtime-fingerprint.XXXXXX.rows)
trap 'rm -f "$normalized_sql" "$normalized_fingerprint_sql" "$fingerprint_rows"' EXIT HUP INT TERM

schema_presence() {
    psql --set=ON_ERROR_STOP=1 \
        --username "$POSTGRES_USER" \
        --dbname "$POSTGRES_DB" \
        --tuples-only --no-align \
        --command="SELECT CASE WHEN pg_catalog.to_regnamespace('fin_runtime') IS NULL THEN 'absent' ELSE 'present' END"
}

catalog_sha256() {
    if ! psql --set=ON_ERROR_STOP=1 \
        --username "$POSTGRES_USER" \
        --dbname "$POSTGRES_DB" \
        --tuples-only --no-align \
        --file "$normalized_fingerprint_sql" \
        > "$fingerprint_rows"; then
        echo "FIN runtime schema catalog fingerprint query failed" >&2
        return 1
    fi
    sha256sum "$fingerprint_rows" | awk '{print $1}'
}

if [ ! -f "$source_sql" ] || [ ! -f "$fingerprint_sql" ]; then
    echo "FIN runtime identity schema or catalog fingerprint source is missing" >&2
    exit 1
fi

# Python's packaged-schema loader normalizes CRLF before checking the same
# identity-schema digest. Normalize both reviewed SQL sources here as well for
# a Windows checkout.
tr -d '\r' < "$source_sql" > "$normalized_sql"
actual_source_sha256=$(sha256sum "$normalized_sql" | awk '{print $1}')
if [ "$actual_source_sha256" != "$expected_source_sha256" ]; then
    echo "FIN runtime identity schema digest mismatch" >&2
    exit 1
fi

tr -d '\r' < "$fingerprint_sql" > "$normalized_fingerprint_sql"
actual_fingerprint_source_sha256=$(sha256sum "$normalized_fingerprint_sql" | awk '{print $1}')
if [ "$actual_fingerprint_source_sha256" != "$expected_fingerprint_source_sha256" ]; then
    echo "FIN runtime schema catalog fingerprint source digest mismatch" >&2
    exit 1
fi

before_state=$(schema_presence)
case "$before_state" in
    absent)
        ;;
    present)
        before_catalog_sha256=$(catalog_sha256)
        if [ "$before_catalog_sha256" = "$expected_catalog_sha256" ]; then
            echo "FIN runtime identity schema v1.0 already matches the exact catalog contract"
            exit 0
        fi
        echo "Existing FIN runtime schema is not the exact supported v1.0 catalog; a separately reviewed migration is required" >&2
        exit 1
        ;;
    *)
        echo "FIN runtime schema presence query returned an unsupported state" >&2
        exit 1
        ;;
esac

# --single-transaction is required because the reviewed SQL begins with
# SET LOCAL ROLE fin_runtime_migrator. Any failure rolls back the whole schema.
psql --set=ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --single-transaction \
    --file "$normalized_sql"

after_catalog_sha256=$(catalog_sha256)
if [ "$after_catalog_sha256" != "$expected_catalog_sha256" ]; then
    echo "FIN runtime identity schema post-install verification failed" >&2
    exit 1
fi

echo "FIN runtime identity schema installed from digest-pinned source"
