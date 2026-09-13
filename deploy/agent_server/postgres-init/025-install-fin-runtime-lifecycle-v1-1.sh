#!/bin/sh
set -eu

# Install or migrate the exact FIN runtime schema to v1.1. The two reviewed
# migrations are mounted read-only outside docker-entrypoint-initdb.d so every
# path passes through source-digest checks, predecessor fingerprint checks and
# one PostgreSQL transaction. Never infer an upgrade from table presence alone.
identity_source_sql=/opt/fin-insight/001_dell_agent_server_identity_v1_0.sql
lifecycle_source_sql=/opt/fin-insight/002_dell_agent_server_remote_create_lifecycle_v1_1.sql
fingerprint_sql=/opt/fin-insight/040-fin-runtime-schema-fingerprint.sql
expected_identity_source_sha256=8102f5ab615bd616f64bd83f610b2e3c3206a9de023d7e27a48069f39e864209
expected_lifecycle_source_sha256=9e9f1e324c07bd767f71c8e870d736d44892b7b5614a4e0ffb1d557491218d25
expected_fingerprint_source_sha256=5de1648a55382aa3acc20297bbdd8a3694a2e0a69ee04814cc6499c0da332a66
expected_v1_0_catalog_sha256=55e3fb20718a060605dd713bea5be7e063bd1afaf7bd460d6041a63eb13a7892
expected_buggy_v1_1_catalog_sha256=31c314f1d0d17cd91e252d4733a0eba35ae5725e85e56685a63081ba552f7bad
expected_v1_1_catalog_sha256=f37dbff53d47dc59bb5390bdcf46a5f51b354ffa61ff5b8c596180d3aa169f7e

normalized_identity_sql=$(mktemp /tmp/fin-runtime-identity-v1-0.XXXXXX.sql)
normalized_lifecycle_sql=$(mktemp /tmp/fin-runtime-lifecycle-v1-1.XXXXXX.sql)
normalized_fingerprint_sql=$(mktemp /tmp/fin-runtime-fingerprint-v1-1.XXXXXX.sql)
fingerprint_rows=$(mktemp /tmp/fin-runtime-fingerprint-v1-1.XXXXXX.rows)
trap 'rm -f "$normalized_identity_sql" "$normalized_lifecycle_sql" "$normalized_fingerprint_sql" "$fingerprint_rows"' EXIT HUP INT TERM

is_sha256() {
    [ "${#1}" -eq 64 ] || return 1
    case "$1" in
        *[!0-9a-f]*) return 1 ;;
    esac
}

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

for required_source in \
    "$identity_source_sql" \
    "$lifecycle_source_sql" \
    "$fingerprint_sql"
do
    if [ ! -f "$required_source" ]; then
        echo "FIN runtime v1.1 migration source is missing" >&2
        exit 1
    fi
done

# Normalize reviewed sources exactly like the packaged Python loaders. This
# keeps a Windows checkout from changing the reviewed source identity.
tr -d '\r' < "$identity_source_sql" > "$normalized_identity_sql"
tr -d '\r' < "$lifecycle_source_sql" > "$normalized_lifecycle_sql"
tr -d '\r' < "$fingerprint_sql" > "$normalized_fingerprint_sql"

actual_identity_source_sha256=$(sha256sum "$normalized_identity_sql" | awk '{print $1}')
actual_lifecycle_source_sha256=$(sha256sum "$normalized_lifecycle_sql" | awk '{print $1}')
actual_fingerprint_source_sha256=$(sha256sum "$normalized_fingerprint_sql" | awk '{print $1}')

if [ "$actual_identity_source_sha256" != "$expected_identity_source_sha256" ]; then
    echo "FIN runtime identity v1.0 schema digest mismatch" >&2
    exit 1
fi
if [ "$actual_lifecycle_source_sha256" != "$expected_lifecycle_source_sha256" ]; then
    echo "FIN runtime lifecycle v1.1 schema digest mismatch" >&2
    exit 1
fi
if [ "$actual_fingerprint_source_sha256" != "$expected_fingerprint_source_sha256" ]; then
    echo "FIN runtime schema catalog fingerprint source digest mismatch" >&2
    exit 1
fi

# This placeholder is deliberately fatal. A catalog hash depends on PostgreSQL's
# canonical catalog rendering and must come from the pinned real PostgreSQL
# image; it must never be guessed from SQL text.
if ! is_sha256 "$expected_v1_1_catalog_sha256"; then
    echo "FIN runtime v1.1 catalog fingerprint awaits real PostgreSQL qualification" >&2
    exit 1
fi
if ! is_sha256 "$expected_buggy_v1_1_catalog_sha256"; then
    echo "FIN runtime known-buggy v1.1 predecessor fingerprint is invalid" >&2
    exit 1
fi

before_state=$(schema_presence)
case "$before_state" in
    absent)
        migration_mode=install_v1_1
        ;;
    present)
        before_catalog_sha256=$(catalog_sha256)
        if [ "$before_catalog_sha256" = "$expected_v1_1_catalog_sha256" ]; then
            migration_mode=already_v1_1
        elif [ "$before_catalog_sha256" = "$expected_buggy_v1_1_catalog_sha256" ]; then
            migration_mode=repair_v1_1_reconciled_self_match
        elif [ "$before_catalog_sha256" = "$expected_v1_0_catalog_sha256" ]; then
            migration_mode=migrate_v1_0_to_v1_1
        else
            echo "Existing FIN runtime schema is neither exact v1.0, known buggy v1.1, nor exact current v1.1; refusing drifted migration" >&2
            exit 1
        fi
        ;;
    *)
        echo "FIN runtime schema presence query returned an unsupported state" >&2
        exit 1
        ;;
esac

case "$migration_mode" in
    already_v1_1)
        ;;
    install_v1_1)
        # --single-transaction spans both ordered files. Each reviewed SQL uses
        # SET LOCAL ROLE fin_runtime_migrator and contains no transaction control.
        psql --set=ON_ERROR_STOP=1 \
            --username "$POSTGRES_USER" \
            --dbname "$POSTGRES_DB" \
            --single-transaction \
            --file "$normalized_identity_sql" \
            --file "$normalized_lifecycle_sql"
        ;;
    migrate_v1_0_to_v1_1|repair_v1_1_reconciled_self_match)
        psql --set=ON_ERROR_STOP=1 \
            --username "$POSTGRES_USER" \
            --dbname "$POSTGRES_DB" \
            --single-transaction \
            --file "$normalized_lifecycle_sql"
        ;;
    *)
        echo "FIN runtime v1.1 migration mode is unsupported" >&2
        exit 1
        ;;
esac

after_catalog_sha256=$(catalog_sha256)
if [ "$after_catalog_sha256" != "$expected_v1_1_catalog_sha256" ]; then
    echo "FIN runtime lifecycle schema v1.1 post-install verification failed" >&2
    exit 1
fi

if [ "$migration_mode" = already_v1_1 ]; then
    echo "FIN runtime lifecycle schema v1.1 already matches the exact catalog contract"
elif [ "$migration_mode" = repair_v1_1_reconciled_self_match ]; then
    echo "FIN runtime lifecycle schema v1.1 repaired from the exact known self-match predecessor"
else
    echo "FIN runtime lifecycle schema v1.1 installed from digest-pinned sources"
fi
