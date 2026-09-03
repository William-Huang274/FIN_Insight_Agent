-- Canonical, secret-free catalog projection for the FIN identity schema.
-- Callers hash the unaligned rows exactly as emitted by psql.  Do not add
-- volatile OIDs, timestamps, passwords, connection strings or row data.
WITH facts(kind, identity, definition) AS (
    SELECT
        'schema',
        namespace.nspname::text,
        pg_catalog.jsonb_build_object(
            'owner', pg_catalog.pg_get_userbyid(namespace.nspowner),
            'comment', pg_catalog.obj_description(namespace.oid, 'pg_namespace'),
            'acl', COALESCE(namespace.nspacl::text, 'NULL')
        )
    FROM pg_catalog.pg_namespace AS namespace
    WHERE namespace.nspname = 'fin_runtime'

    UNION ALL

    SELECT
        'role',
        role.rolname::text,
        pg_catalog.jsonb_build_object(
            'superuser', role.rolsuper,
            'inherit', role.rolinherit,
            'create_role', role.rolcreaterole,
            'create_database', role.rolcreatedb,
            'login', role.rolcanlogin,
            'replication', role.rolreplication,
            'bypass_rls', role.rolbypassrls,
            'connection_limit', role.rolconnlimit,
            'valid_until', role.rolvaliduntil,
            'config', role.rolconfig
        )
    FROM pg_catalog.pg_roles AS role
    WHERE role.rolname IN (
        'fin_runtime_app',
        'fin_runtime_migrator',
        'langgraph_runtime'
    )

    UNION ALL

    SELECT
        'role_membership',
        (granted_role.rolname || '->' || member_role.rolname)::text,
        pg_catalog.jsonb_build_object(
            'grantor', grantor_role.rolname,
            'admin_option', membership.admin_option,
            'inherit_option', membership.inherit_option,
            'set_option', membership.set_option
        )
    FROM pg_catalog.pg_auth_members AS membership
    JOIN pg_catalog.pg_roles AS granted_role
      ON granted_role.oid = membership.roleid
    JOIN pg_catalog.pg_roles AS member_role
      ON member_role.oid = membership.member
    JOIN pg_catalog.pg_roles AS grantor_role
      ON grantor_role.oid = membership.grantor
    WHERE granted_role.rolname IN (
        'fin_runtime_app',
        'fin_runtime_migrator',
        'langgraph_runtime'
    )
       OR member_role.rolname IN (
        'fin_runtime_app',
        'fin_runtime_migrator',
        'langgraph_runtime'
    )

    UNION ALL

    SELECT
        'role_setting',
        (
            COALESCE(database_row.datname, '<all-databases>')
            || '.' || COALESCE(role.rolname, '<all-roles>')
        )::text,
        pg_catalog.jsonb_build_object(
            'settings', setting.setconfig
        )
    FROM pg_catalog.pg_db_role_setting AS setting
    LEFT JOIN pg_catalog.pg_database AS database_row
      ON database_row.oid = setting.setdatabase
     AND setting.setdatabase <> 0
    LEFT JOIN pg_catalog.pg_roles AS role
      ON role.oid = setting.setrole
     AND setting.setrole <> 0
    WHERE role.rolname IN (
        'fin_runtime_app',
        'fin_runtime_migrator',
        'langgraph_runtime'
    )
       OR (
            setting.setrole = 0
            AND (
                setting.setdatabase = 0
                OR database_row.datname = pg_catalog.current_database()
            )
       )

    UNION ALL

    SELECT
        'relation',
        class.relname::text,
        pg_catalog.jsonb_build_object(
            'kind', class.relkind,
            'persistence', class.relpersistence,
            'owner', pg_catalog.pg_get_userbyid(class.relowner),
            'row_security', class.relrowsecurity,
            'force_row_security', class.relforcerowsecurity,
            'replica_identity', class.relreplident,
            'acl', COALESCE(class.relacl::text, 'NULL')
        )
    FROM pg_catalog.pg_class AS class
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    WHERE namespace.nspname = 'fin_runtime'
      AND class.relkind IN ('r', 'i', 'S')

    UNION ALL

    SELECT
        'column',
        (class.relname || '.' || attribute.attnum::text || '.' || attribute.attname)::text,
        pg_catalog.jsonb_build_object(
            'type', pg_catalog.format_type(attribute.atttypid, attribute.atttypmod),
            'not_null', attribute.attnotnull,
            'identity', attribute.attidentity,
            'generated', attribute.attgenerated,
            'collation', CASE
                WHEN attribute.attcollation = 0 THEN NULL
                ELSE attribute.attcollation::pg_catalog.regcollation::text
            END,
            'default', pg_catalog.pg_get_expr(default_value.adbin, default_value.adrelid)
        )
    FROM pg_catalog.pg_attribute AS attribute
    JOIN pg_catalog.pg_class AS class
      ON class.oid = attribute.attrelid
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    LEFT JOIN pg_catalog.pg_attrdef AS default_value
      ON default_value.adrelid = attribute.attrelid
     AND default_value.adnum = attribute.attnum
    WHERE namespace.nspname = 'fin_runtime'
      AND class.relkind = 'r'
      AND attribute.attnum > 0
      AND NOT attribute.attisdropped

    UNION ALL

    SELECT
        'constraint',
        (class.relname || '.' || constraint_row.conname)::text,
        pg_catalog.jsonb_build_object(
            'type', constraint_row.contype,
            'deferrable', constraint_row.condeferrable,
            'deferred', constraint_row.condeferred,
            'validated', constraint_row.convalidated,
            'no_inherit', constraint_row.connoinherit,
            'definition', pg_catalog.pg_get_constraintdef(constraint_row.oid, true)
        )
    FROM pg_catalog.pg_constraint AS constraint_row
    JOIN pg_catalog.pg_class AS class
      ON class.oid = constraint_row.conrelid
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    WHERE namespace.nspname = 'fin_runtime'

    UNION ALL

    SELECT
        'index',
        index_class.relname::text,
        pg_catalog.jsonb_build_object(
            'table', table_class.relname,
            'unique', index_row.indisunique,
            'primary', index_row.indisprimary,
            'valid', index_row.indisvalid,
            'ready', index_row.indisready,
            'live', index_row.indislive,
            'clustered', index_row.indisclustered,
            'replica_identity', index_row.indisreplident,
            'definition', pg_catalog.pg_get_indexdef(index_row.indexrelid)
        )
    FROM pg_catalog.pg_index AS index_row
    JOIN pg_catalog.pg_class AS index_class
      ON index_class.oid = index_row.indexrelid
    JOIN pg_catalog.pg_class AS table_class
      ON table_class.oid = index_row.indrelid
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = table_class.relnamespace
    WHERE namespace.nspname = 'fin_runtime'

    UNION ALL

    SELECT
        'trigger',
        (class.relname || '.' || trigger_row.tgname)::text,
        pg_catalog.jsonb_build_object(
            'enabled', trigger_row.tgenabled,
            'type_bits', trigger_row.tgtype,
            'function', trigger_row.tgfoid::pg_catalog.regprocedure::text,
            'definition', pg_catalog.pg_get_triggerdef(trigger_row.oid, true)
        )
    FROM pg_catalog.pg_trigger AS trigger_row
    JOIN pg_catalog.pg_class AS class
      ON class.oid = trigger_row.tgrelid
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = class.relnamespace
    WHERE namespace.nspname = 'fin_runtime'
      AND NOT trigger_row.tgisinternal

    UNION ALL

    SELECT
        'function',
        (
            procedure.proname || '('
            || pg_catalog.pg_get_function_identity_arguments(procedure.oid)
            || ')'
        )::text,
        pg_catalog.jsonb_build_object(
            'owner', pg_catalog.pg_get_userbyid(procedure.proowner),
            'language', language.lanname,
            'kind', procedure.prokind,
            'volatility', procedure.provolatile,
            'strict', procedure.proisstrict,
            'security_definer', procedure.prosecdef,
            'leakproof', procedure.proleakproof,
            'parallel', procedure.proparallel,
            'config', procedure.proconfig,
            'acl', COALESCE(procedure.proacl::text, 'NULL'),
            'definition', pg_catalog.pg_get_functiondef(procedure.oid)
        )
    FROM pg_catalog.pg_proc AS procedure
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = procedure.pronamespace
    JOIN pg_catalog.pg_language AS language
      ON language.oid = procedure.prolang
    WHERE namespace.nspname = 'fin_runtime'

    UNION ALL

    SELECT
        'default_acl',
        (
            role.rolname || '.' || default_acl.defaclobjtype::text
            || '.' || COALESCE(namespace.nspname, '<global>')
        )::text,
        pg_catalog.jsonb_build_object(
            'acl', COALESCE(default_acl.defaclacl::text, 'NULL')
        )
    FROM pg_catalog.pg_default_acl AS default_acl
    JOIN pg_catalog.pg_roles AS role
      ON role.oid = default_acl.defaclrole
    LEFT JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = default_acl.defaclnamespace
    WHERE role.rolname = 'fin_runtime_migrator'
      AND namespace.nspname = 'fin_runtime'

    UNION ALL

    SELECT
        'database_privilege',
        role_name || '.' || privilege_name,
        pg_catalog.to_jsonb(
            pg_catalog.has_database_privilege(
                role_name,
                pg_catalog.current_database(),
                privilege_name
            )
        )
    FROM (
        VALUES
            ('fin_runtime_app', 'CONNECT'),
            ('fin_runtime_app', 'CREATE'),
            ('fin_runtime_app', 'TEMPORARY'),
            ('fin_runtime_migrator', 'CONNECT'),
            ('fin_runtime_migrator', 'CREATE'),
            ('fin_runtime_migrator', 'TEMPORARY'),
            ('langgraph_runtime', 'CONNECT'),
            ('langgraph_runtime', 'CREATE'),
            ('langgraph_runtime', 'TEMPORARY')
    ) AS privilege(role_name, privilege_name)
)
SELECT pg_catalog.encode(
    pg_catalog.convert_to(
        kind || chr(31) || identity || chr(31) || definition::text,
        'UTF8'
    ),
    'hex'
)
FROM facts
ORDER BY kind, identity;
