-- FIN 0.1.3 DELL reference vertical: bounded data-foundation schema v1.0
-- Target runtime: PostgreSQL 16.x + pgvector 0.8.6.
--
-- Authority boundary:
--   SourceLocator != SourceCapture != RetrievalCandidate != Evidence.
--   Knowledge chunks are retrieval material only.  An exact-search result is
--   a transient RetrievalCandidate.  Nothing in this schema can become
--   Evidence or NumericFact, and this schema does not replace the current S2
--   SQLite authority.  FIN admission and finance-domain ports stay outside.
--
-- Vector boundary:
--   Embeddings are 1,024-dimensional halfvec values.  Runtime may compare as
--   native halfvec(1024) or cast to vector(1024), but only exact distance is
--   qualified.  This file intentionally creates no approximate vector index.
--
-- Transaction boundary:
--   This DDL intentionally contains no BEGIN/COMMIT/ROLLBACK.  The dedicated
--   installer or deployment caller owns the transaction and rollback choice.

DO $fin_pg16$
BEGIN
    IF current_setting('server_version_num')::integer / 10000 <> 16 THEN
        RAISE EXCEPTION 'fin_research requires PostgreSQL major version 16';
    END IF;
END
$fin_pg16$;

CREATE EXTENSION IF NOT EXISTS vector WITH VERSION '0.8.6';

DO $fin_pgvector$
DECLARE
    installed_version text;
BEGIN
    SELECT extversion INTO installed_version
    FROM pg_extension
    WHERE extname = 'vector';
    IF installed_version IS DISTINCT FROM '0.8.6' THEN
        RAISE EXCEPTION
            'fin_research requires pgvector 0.8.6, found %',
            coalesce(installed_version, '<missing>');
    END IF;
END
$fin_pgvector$;

CREATE SCHEMA IF NOT EXISTS fin_research;

CREATE TABLE IF NOT EXISTS fin_research.foundation_metadata (
    metadata_key text PRIMARY KEY,
    metadata_value text NOT NULL
);

INSERT INTO fin_research.foundation_metadata (metadata_key, metadata_value)
VALUES
    ('schema_contract_version', 'fin_ia_dell_data_foundation_v1_0'),
    ('postgres_major', '16'),
    ('pgvector_version', '0.8.6'),
    ('embedding_dimension', '1024'),
    ('vector_route', 'exact_only'),
    ('authority_boundary',
     'source_locator!=source_capture!=retrieval_candidate!=evidence;numeric_fact=false')
ON CONFLICT (metadata_key) DO NOTHING;

DO $fin_metadata_guard$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM fin_research.foundation_metadata
        WHERE (metadata_key, metadata_value) NOT IN (
            ('schema_contract_version', 'fin_ia_dell_data_foundation_v1_0'),
            ('postgres_major', '16'),
            ('pgvector_version', '0.8.6'),
            ('embedding_dimension', '1024'),
            ('vector_route', 'exact_only'),
            ('authority_boundary',
             'source_locator!=source_capture!=retrieval_candidate!=evidence;numeric_fact=false')
        )
    ) THEN
        RAISE EXCEPTION 'fin_research metadata conflicts with schema v1.0';
    END IF;
END
$fin_metadata_guard$;

CREATE TABLE IF NOT EXISTS fin_research.source_locators (
    locator_id text PRIMARY KEY,
    record_class text NOT NULL DEFAULT 'source_locator'
        CHECK (record_class = 'source_locator'),
    source_family text NOT NULL,
    source_type text NOT NULL,
    canonical_uri text NOT NULL,
    issuer_id text,
    document_date date,
    source_published_at timestamptz,
    recorded_at timestamptz NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object'),
    evidence_authority boolean NOT NULL DEFAULT false
        CHECK (NOT evidence_authority),
    numeric_fact_authority boolean NOT NULL DEFAULT false
        CHECK (NOT numeric_fact_authority),
    record_digest text NOT NULL
        CHECK (record_digest ~ '^[0-9a-f]{64}$')
);

CREATE TABLE IF NOT EXISTS fin_research.capture_attempts (
    attempt_id text PRIMARY KEY,
    source_locator_id text NOT NULL
        REFERENCES fin_research.source_locators(locator_id),
    case_id text NOT NULL,
    record_class text NOT NULL DEFAULT 'capture_attempt'
        CHECK (record_class = 'capture_attempt'),
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    research_as_of timestamptz NOT NULL,
    status text NOT NULL
        CHECK (status IN ('succeeded', 'failed', 'bounded_hold', 'not_modified')),
    input_digest text NOT NULL
        CHECK (input_digest ~ '^[0-9a-f]{64}$'),
    request_receipt_digest text NOT NULL
        CHECK (request_receipt_digest ~ '^[0-9a-f]{64}$'),
    terminal_receipt_digest text NOT NULL
        CHECK (terminal_receipt_digest ~ '^[0-9a-f]{64}$'),
    failure_class text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object'),
    evidence_authority boolean NOT NULL DEFAULT false
        CHECK (NOT evidence_authority),
    numeric_fact_authority boolean NOT NULL DEFAULT false
        CHECK (NOT numeric_fact_authority),
    record_digest text NOT NULL
        CHECK (record_digest ~ '^[0-9a-f]{64}$'),
    CHECK (completed_at >= started_at),
    UNIQUE (attempt_id, source_locator_id),
    UNIQUE (attempt_id, source_locator_id, status)
);

CREATE TABLE IF NOT EXISTS fin_research.source_captures (
    capture_id text PRIMARY KEY,
    attempt_id text NOT NULL,
    source_locator_id text NOT NULL,
    attempt_status text NOT NULL DEFAULT 'succeeded'
        CHECK (attempt_status = 'succeeded'),
    record_class text NOT NULL DEFAULT 'source_capture'
        CHECK (record_class = 'source_capture'),
    captured_at timestamptz NOT NULL,
    response_status integer NOT NULL
        CHECK (response_status BETWEEN 200 AND 299),
    media_type text NOT NULL,
    byte_length bigint NOT NULL CHECK (byte_length >= 0),
    raw_sha256 text NOT NULL
        CHECK (raw_sha256 ~ '^[0-9a-f]{64}$'),
    extracted_text_sha256 text
        CHECK (
            extracted_text_sha256 IS NULL
            OR extracted_text_sha256 ~ '^[0-9a-f]{64}$'
        ),
    object_uri text NOT NULL,
    capture_receipt_digest text NOT NULL
        CHECK (capture_receipt_digest ~ '^[0-9a-f]{64}$'),
    temporal_authority_basis text NOT NULL DEFAULT 'capture_time'
        CHECK (
            temporal_authority_basis IN (
                'capture_time',
                'immutable_source_version',
                'archive_seal'
            )
        ),
    source_version_id text,
    archive_sealed_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object'),
    retrieval_candidate boolean NOT NULL DEFAULT false
        CHECK (NOT retrieval_candidate),
    evidence_authority boolean NOT NULL DEFAULT false
        CHECK (NOT evidence_authority),
    numeric_fact_authority boolean NOT NULL DEFAULT false
        CHECK (NOT numeric_fact_authority),
    record_digest text NOT NULL
        CHECK (record_digest ~ '^[0-9a-f]{64}$'),
    FOREIGN KEY (attempt_id, source_locator_id, attempt_status)
        REFERENCES fin_research.capture_attempts(
            attempt_id,
            source_locator_id,
            status
        ),
    CHECK (
        (
            temporal_authority_basis = 'capture_time'
            AND source_version_id IS NULL
            AND archive_sealed_at IS NULL
        )
        OR (
            temporal_authority_basis = 'immutable_source_version'
            AND source_version_id IS NOT NULL
            AND length(btrim(source_version_id)) > 0
            AND archive_sealed_at IS NULL
        )
        OR (
            temporal_authority_basis = 'archive_seal'
            AND source_version_id IS NULL
            AND archive_sealed_at IS NOT NULL
        )
    )
);

CREATE TABLE IF NOT EXISTS fin_research.knowledge_chunks (
    chunk_id text PRIMARY KEY,
    capture_id text NOT NULL
        REFERENCES fin_research.source_captures(capture_id),
    record_class text NOT NULL DEFAULT 'knowledge_chunk'
        CHECK (record_class = 'knowledge_chunk'),
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    chunk_kind text NOT NULL,
    chunk_contract_version text NOT NULL,
    parser_name text NOT NULL,
    parser_version text NOT NULL,
    parser_config_digest text NOT NULL
        CHECK (parser_config_digest ~ '^[0-9a-f]{64}$'),
    materialized_at timestamptz NOT NULL,
    locator jsonb NOT NULL CHECK (jsonb_typeof(locator) = 'object'),
    chunk_text text NOT NULL CHECK (length(btrim(chunk_text)) > 0),
    chunk_text_sha256 text NOT NULL
        CHECK (chunk_text_sha256 ~ '^[0-9a-f]{64}$'),
    embedding_model_id text NOT NULL,
    embedding_revision text NOT NULL,
    -- Digest of the canonical vector input before half-precision storage.
    -- A later qualification/readback receipt must own stored-value parity.
    embedding_input_sha256 text NOT NULL
        CHECK (embedding_input_sha256 ~ '^[0-9a-f]{64}$'),
    embedding halfvec(1024) NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object'),
    retrieval_material boolean NOT NULL DEFAULT true
        CHECK (retrieval_material),
    retrieval_candidate boolean NOT NULL DEFAULT false
        CHECK (NOT retrieval_candidate),
    evidence_authority boolean NOT NULL DEFAULT false
        CHECK (NOT evidence_authority),
    numeric_fact_authority boolean NOT NULL DEFAULT false
        CHECK (NOT numeric_fact_authority),
    record_digest text NOT NULL
        CHECK (record_digest ~ '^[0-9a-f]{64}$'),
    UNIQUE (capture_id, ordinal, chunk_contract_version)
);

CREATE TABLE IF NOT EXISTS fin_research.legacy_object_mappings (
    mapping_id text PRIMARY KEY,
    legacy_namespace text NOT NULL,
    legacy_snapshot_id text NOT NULL,
    legacy_snapshot_digest text NOT NULL
        CHECK (legacy_snapshot_digest ~ '^[0-9a-f]{64}$'),
    legacy_object_id text NOT NULL,
    target_locator_id text
        REFERENCES fin_research.source_locators(locator_id),
    target_capture_id text
        REFERENCES fin_research.source_captures(capture_id),
    target_chunk_id text
        REFERENCES fin_research.knowledge_chunks(chunk_id),
    mapping_receipt_digest text NOT NULL
        CHECK (mapping_receipt_digest ~ '^[0-9a-f]{64}$'),
    mapped_at timestamptz NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object'),
    migration_authority boolean NOT NULL DEFAULT false
        CHECK (NOT migration_authority),
    evidence_authority boolean NOT NULL DEFAULT false
        CHECK (NOT evidence_authority),
    numeric_fact_authority boolean NOT NULL DEFAULT false
        CHECK (NOT numeric_fact_authority),
    record_digest text NOT NULL
        CHECK (record_digest ~ '^[0-9a-f]{64}$'),
    CHECK (
        num_nonnulls(target_locator_id, target_capture_id, target_chunk_id) = 1
    ),
    UNIQUE (
        legacy_namespace,
        legacy_snapshot_digest,
        legacy_object_id
    )
);

-- Metadata indexes only.  Vector distance therefore remains an exact scan over
-- the rows admitted by case/as-of/source filters.
CREATE INDEX IF NOT EXISTS source_locators_filter_idx
    ON fin_research.source_locators
    (source_family, issuer_id, document_date, source_published_at);

CREATE INDEX IF NOT EXISTS capture_attempts_case_asof_idx
    ON fin_research.capture_attempts (case_id, research_as_of, status);

CREATE INDEX IF NOT EXISTS source_captures_locator_idx
    ON fin_research.source_captures (source_locator_id, attempt_id);

CREATE INDEX IF NOT EXISTS knowledge_chunks_capture_ordinal_idx
    ON fin_research.knowledge_chunks (capture_id, ordinal);

CREATE INDEX IF NOT EXISTS legacy_object_lookup_idx
    ON fin_research.legacy_object_mappings
    (legacy_namespace, legacy_snapshot_digest, legacy_object_id);

CREATE OR REPLACE FUNCTION fin_research.validate_capture_attempt_window()
RETURNS trigger
LANGUAGE plpgsql
AS $fin_capture_attempt_window$
DECLARE
    parent_locator_id text;
    attempt_started_at timestamptz;
    attempt_completed_at timestamptz;
BEGIN
    SELECT source_locator_id, started_at, completed_at
      INTO parent_locator_id, attempt_started_at, attempt_completed_at
      FROM fin_research.capture_attempts
     WHERE attempt_id = NEW.attempt_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'capture attempt % does not exist', NEW.attempt_id;
    END IF;
    IF parent_locator_id IS DISTINCT FROM NEW.source_locator_id THEN
        RAISE EXCEPTION
            'capture locator % does not match attempt locator %',
            NEW.source_locator_id,
            parent_locator_id;
    END IF;
    IF NEW.captured_at < attempt_started_at
       OR NEW.captured_at > attempt_completed_at THEN
        RAISE EXCEPTION
            'capture time % is outside attempt window [% - %]',
            NEW.captured_at,
            attempt_started_at,
            attempt_completed_at;
    END IF;
    RETURN NEW;
END
$fin_capture_attempt_window$;

DO $fin_capture_attempt_trigger$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger AS trigger_row
        JOIN pg_class AS table_row
          ON table_row.oid = trigger_row.tgrelid
        JOIN pg_namespace AS namespace_row
          ON namespace_row.oid = table_row.relnamespace
        WHERE namespace_row.nspname = 'fin_research'
          AND table_row.relname = 'source_captures'
          AND trigger_row.tgname = 'validate_capture_attempt_window'
          AND NOT trigger_row.tgisinternal
    ) THEN
        CREATE TRIGGER validate_capture_attempt_window
        BEFORE INSERT ON fin_research.source_captures
        FOR EACH ROW EXECUTE FUNCTION
            fin_research.validate_capture_attempt_window();
    END IF;
END
$fin_capture_attempt_trigger$;

CREATE OR REPLACE FUNCTION fin_research.reject_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $fin_append_only$
BEGIN
    RAISE EXCEPTION
        'fin_research append-only table % does not permit %',
        TG_TABLE_NAME,
        TG_OP;
END
$fin_append_only$;

DO $fin_append_only_triggers$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'source_locators',
        'capture_attempts',
        'source_captures',
        'knowledge_chunks',
        'legacy_object_mappings'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_trigger AS trigger_row
            JOIN pg_class AS table_row
              ON table_row.oid = trigger_row.tgrelid
            JOIN pg_namespace AS namespace_row
              ON namespace_row.oid = table_row.relnamespace
            WHERE namespace_row.nspname = 'fin_research'
              AND table_row.relname = table_name
              AND trigger_row.tgname = 'reject_immutable_mutation'
              AND NOT trigger_row.tgisinternal
        ) THEN
            EXECUTE format(
                'CREATE TRIGGER reject_immutable_mutation '
                'BEFORE UPDATE OR DELETE ON fin_research.%I '
                'FOR EACH ROW EXECUTE FUNCTION '
                'fin_research.reject_immutable_mutation()',
                table_name
            );
        END IF;
    END LOOP;
END
$fin_append_only_triggers$;
