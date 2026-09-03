from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "dell_agent_server"
COMPOSE_PATH = DEPLOY / "compose.yaml"
ZERO_MODEL_COMPOSE_OVERRIDE_PATH = (
    DEPLOY / "compose.zero-model-qualification.yaml"
)
DOCKERFILE_PATH = DEPLOY / "Dockerfile"
DOCKERIGNORE_PATH = DEPLOY / "Dockerfile.dockerignore"
POSTGRES_INIT_PATH = DEPLOY / "postgres-init" / "010-create-runtime-roles.sh"
POSTGRES_IDENTITY_INIT_PATH = (
    DEPLOY / "postgres-init" / "020-install-fin-runtime-identity.sh"
)
POSTGRES_READINESS_PATH = (
    DEPLOY / "postgres-init" / "030-runtime-readiness.sh"
)
POSTGRES_FINGERPRINT_PATH = (
    DEPLOY / "postgres-init" / "040-fin-runtime-schema-fingerprint.sql"
)
IDENTITY_SQL_PATH = (
    ROOT
    / "src/sec_agent/agent_runtime/sql/001_dell_agent_server_identity_v1_0.sql"
)

LANGGRAPH_API_IMAGE = (
    "langchain/langgraph-api:0.13.3-py3.13@sha256:"
    "ec26d6f6eb7ce3428ca476700f572205e6aff65fe62151b8e32541b0d93f2a1d"
)
REDIS_IMAGE = (
    "redis:6@sha256:"
    "143f7bfc2358911d6b36138eabfbfffea46273c5d4b5696d90e5cbf23d633cf8"
)
PGVECTOR_IMAGE = (
    "pgvector/pgvector:pg16@sha256:"
    "ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b"
)

CONTROL_FILES = (
    "fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json",
    "fin_ia_0_1_3_dell_reference_vertical_deepseek_structured_agents_v1_0.json",
    "fin_ia_0_1_3_dell_source_family_physical_route_catalog_v1_0.json",
    "fin_ia_0_1_3_dell_reviewed_evidence_enrichment_v1_0.json",
    "fin_ia_0_1_3_dell_owner_data_gate_decision_v1_0.json",
)

HOST_BINDINGS = {
    "FINSIGHT_DELL_S1_NODES_HOST_PATH": (
        "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
        "rag_mature_stack/retrieval_qualification/"
        "dell_rag_full_stack_preview_attempt_20260902_03/retrieval_nodes.jsonl",
        "/run/fin-insight/s1/retrieval_nodes.jsonl",
    ),
    "FINSIGHT_DELL_REVIEWED_BASE_PACK_HOST_PATH": (
        "D:/FIN_Insight_Agent/data/workbench_private/"
        "fin_0_1_3_s1_dell_direct_source_evidence/r4/successor/pack.json",
        "/run/fin-insight/reviewed/base/pack.json",
    ),
    "FINSIGHT_DELL_REVIEWED_OVERLAY_HOST_PATH": (
        "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
        "evidence_overlay/attempts/"
        "20260902T051005+0800-dell-fy27q2-sec-ex99-review-a01/"
        "reviewed-evidence-case-projection.json",
        (
            "/run/fin-insight/reviewed/overlay/"
            "reviewed-evidence-case-projection.json"
        ),
    ),
    "FINSIGHT_DELL_S2_RESULT_HOST_PATH": (
        "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/s2/"
        "s2_exact_period_contract_successor_20260902_r1/"
        "company_financial_fact_mart_result.json",
        "/run/fin-insight/s2/company_financial_fact_mart_result.json",
    ),
    "FINSIGHT_DELL_S2_MART_HOST_PATH": (
        "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/s2/"
        "s2_exact_period_contract_successor_20260902_r1/"
        "company_financial_facts.sqlite",
        "/run/fin-insight/s2/company_financial_facts.sqlite",
    ),
    "FINSIGHT_DELL_EXTERNAL_PACK_HOST_ROOT": (
        "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
        "external_exact_url_qualification/"
        "dell_external_exact_url_zero_model_20260902_r12",
        "/run/fin-insight/external-r12",
    ),
}

CONTAINER_DATA_PATHS = {
    "FIN_REPO_ROOT": "/deps/FIN_Insight_Agent",
    "FINSIGHT_DELL_S1_NODES_PATH": "/run/fin-insight/s1/retrieval_nodes.jsonl",
    "FINSIGHT_DELL_REVIEWED_BASE_PACK_PATH": (
        "/run/fin-insight/reviewed/base/pack.json"
    ),
    "FINSIGHT_DELL_REVIEWED_OVERLAY_PATH": (
        "/run/fin-insight/reviewed/overlay/reviewed-evidence-case-projection.json"
    ),
    "FINSIGHT_DELL_S2_RESULT_PATH": (
        "/run/fin-insight/s2/company_financial_fact_mart_result.json"
    ),
    "FINSIGHT_COMPANY_FINANCIAL_FACT_MART_PATH": (
        "/run/fin-insight/s2/company_financial_facts.sqlite"
    ),
    "FINSIGHT_DELL_EXTERNAL_MANIFEST_PATH": (
        "/run/fin-insight/external-r12/manifest.json"
    ),
}


def _compose() -> dict:
    value = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_local_compose_has_only_the_official_three_service_topology() -> None:
    compose = _compose()
    services = compose["services"]

    assert compose["name"] == "finsight-dell-agent-server-local"
    assert set(services) == {
        "langgraph-api",
        "langgraph-postgres",
        "langgraph-redis",
    }
    assert services["langgraph-redis"]["image"] == REDIS_IMAGE
    assert services["langgraph-postgres"]["image"] == PGVECTOR_IMAGE
    assert services["langgraph-api"]["depends_on"] == {
        "langgraph-redis": {"condition": "service_healthy"},
        "langgraph-postgres": {"condition": "service_healthy"},
    }


def test_only_api_is_published_and_it_is_loopback_only() -> None:
    services = _compose()["services"]

    assert services["langgraph-api"]["ports"] == [
        "127.0.0.1:${FINSIGHT_AGENT_SERVER_HOST_PORT:-18123}:8000"
    ]
    assert services["langgraph-api"]["healthcheck"]["timeout"] == "10s"
    assert services["langgraph-api"]["healthcheck"]["retries"] == 5
    assert "ports" not in services["langgraph-postgres"]
    assert "ports" not in services["langgraph-redis"]
    assert services["langgraph-postgres"]["healthcheck"] == {
        "test": [
            "CMD",
            "/bin/sh",
            "/usr/local/bin/fin-postgres-runtime-readiness",
        ],
        "start_period": "10s",
        "timeout": "5s",
        "retries": 12,
        "interval": "5s",
    }
    assert all(service.get("network_mode") != "host" for service in services.values())


def test_build_context_resolves_to_repo_and_uses_generated_server_dockerfile() -> None:
    build = _compose()["services"]["langgraph-api"]["build"]
    context = (COMPOSE_PATH.parent / build["context"]).resolve()
    dockerfile = context / build["dockerfile"]

    assert context == ROOT.resolve()
    assert dockerfile.resolve() == DOCKERFILE_PATH.resolve()
    assert dockerfile.is_file()


def test_env_and_build_context_cannot_copy_checked_in_secrets() -> None:
    compose = _compose()
    api = compose["services"]["langgraph-api"]
    postgres = compose["services"]["langgraph-postgres"]
    raw = COMPOSE_PATH.read_text(encoding="utf-8")

    assert "env_file" not in api
    assert set(api["environment"]) == {
        "REDIS_URI",
        "POSTGRES_URI",
        "FIN_RUNTIME_POSTGRES_URI",
        "FINSIGHT_DELL_EXECUTION_PROFILE",
        "LANGSMITH_API_KEY",
        "LANGSMITH_HIDE_INPUTS",
        "LANGSMITH_HIDE_OUTPUTS",
        "LANGSMITH_TRACING",
        "LANGSMITH_PROJECT",
        "N_JOBS_PER_WORKER",
        *CONTAINER_DATA_PATHS,
    }
    assert api["environment"]["REDIS_URI"] == "redis://langgraph-redis:6379"
    assert api["environment"]["LANGSMITH_TRACING"] == "true"
    assert api["environment"]["LANGSMITH_HIDE_INPUTS"] == "true"
    assert api["environment"]["LANGSMITH_HIDE_OUTPUTS"] == "true"
    assert (
        api["environment"]["LANGSMITH_PROJECT"]
        == "fin-insight-dell-reference-vertical"
    )
    assert api["environment"]["N_JOBS_PER_WORKER"] == "4"
    assert api["environment"]["FINSIGHT_DELL_EXECUTION_PROFILE"] == "product"
    assert str(api["environment"]["LANGSMITH_API_KEY"]).startswith("${")
    assert "DEEPSEEK_API_KEY" not in api["environment"]
    assert str(api["environment"]["POSTGRES_URI"]).startswith(
        "postgres://langgraph_runtime:${"
    )
    assert str(api["environment"]["FIN_RUNTIME_POSTGRES_URI"]).startswith(
        "postgres://fin_runtime_app:${"
    )
    assert {
        name: api["environment"][name] for name in CONTAINER_DATA_PATHS
    } == CONTAINER_DATA_PATHS
    for service in compose["services"].values():
        assert set(HOST_BINDINGS).isdisjoint(service.get("environment", {}))
    assert "${FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD:?" in raw
    assert "${FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD:?" in raw
    assert "${FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD:?" in raw
    assert str(postgres["environment"]["POSTGRES_PASSWORD"]).startswith("${")
    assert set(postgres["environment"]) == {
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD",
        "FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD",
    }
    assert re.search(r"(?im)^\.env$", (ROOT / ".gitignore").read_text("utf-8"))
    assert re.search(r"(?im)^\.env$", (ROOT / ".dockerignore").read_text("utf-8"))
    without_interpolation_contracts = re.sub(r"\$\{[^}\r\n]+\}", "${REDACTED}", raw)
    assert not re.search(
        r"(?:sk-|lsv2_|api[_-]?key\s*[:=]\s*[^$\s])",
        without_interpolation_contracts,
        re.I,
    )


def test_zero_model_qualification_requires_an_explicit_compose_override() -> None:
    override = yaml.safe_load(
        ZERO_MODEL_COMPOSE_OVERRIDE_PATH.read_text(encoding="utf-8")
    )

    assert override == {
        "name": "finsight-dell-qualification-20260904-r8a3",
        "services": {
            "langgraph-api": {
                "environment": {
                    "FINSIGHT_DELL_EXECUTION_PROFILE": (
                        "zero_model_control_plane_v1"
                    ),
                    "LANGSMITH_HIDE_INPUTS": "true",
                    "LANGSMITH_HIDE_OUTPUTS": "true",
                },
                "volumes": [
                    {
                        "type": "bind",
                        "source": "../../scripts/qualification/agent_server_r8",
                        "target": "/opt/fin-insight-qualification/r8",
                        "read_only": True,
                        "bind": {"create_host_path": False},
                    }
                ],
            }
        }
    }
    assert "${" not in ZERO_MODEL_COMPOSE_OVERRIDE_PATH.read_text(
        encoding="utf-8"
    )


def test_only_api_receives_the_six_exact_read_only_data_bindings() -> None:
    services = _compose()["services"]
    api_volumes = services["langgraph-api"]["volumes"]

    assert len(api_volumes) == len(HOST_BINDINGS) == 6
    assert {volume["target"] for volume in api_volumes} == {
        target for _, target in HOST_BINDINGS.values()
    }
    for host_name, (default_source, target) in HOST_BINDINGS.items():
        assert {
            "type": "bind",
            "source": f"${{{host_name}:-{default_source}}}",
            "target": target,
            "read_only": True,
            "bind": {"create_host_path": False},
        } in api_volumes

    assert not services["langgraph-redis"].get("volumes")
    postgres_bindings = tuple(
        volume
        for volume in services["langgraph-postgres"].get("volumes", [])
        if isinstance(volume, dict) and volume.get("type") == "bind"
    )
    assert postgres_bindings == (
        {
            "type": "bind",
            "source": "./postgres-init/010-create-runtime-roles.sh",
            "target": "/docker-entrypoint-initdb.d/010-create-runtime-roles.sh",
            "read_only": True,
            "bind": {"create_host_path": False},
        },
        {
            "type": "bind",
            "source": "./postgres-init/020-install-fin-runtime-identity.sh",
            "target": (
                "/docker-entrypoint-initdb.d/"
                "020-install-fin-runtime-identity.sh"
            ),
            "read_only": True,
            "bind": {"create_host_path": False},
        },
        {
            "type": "bind",
            "source": "./postgres-init/030-runtime-readiness.sh",
            "target": "/usr/local/bin/fin-postgres-runtime-readiness",
            "read_only": True,
            "bind": {"create_host_path": False},
        },
        {
            "type": "bind",
            "source": (
                "../../src/sec_agent/agent_runtime/sql/"
                "001_dell_agent_server_identity_v1_0.sql"
            ),
            "target": (
                "/opt/fin-insight/"
                "001_dell_agent_server_identity_v1_0.sql"
            ),
            "read_only": True,
            "bind": {"create_host_path": False},
        },
        {
            "type": "bind",
            "source": (
                "./postgres-init/"
                "040-fin-runtime-schema-fingerprint.sql"
            ),
            "target": (
                "/opt/fin-insight/"
                "040-fin-runtime-schema-fingerprint.sql"
            ),
            "read_only": True,
            "bind": {"create_host_path": False},
        },
    )

    raw = COMPOSE_PATH.read_text(encoding="utf-8")
    assert "docker.sock" not in raw
    assert "target: D:/" not in raw
    assert "target: Z:/" not in raw
    assert all(
        default_source not in CONTAINER_DATA_PATHS.values()
        for default_source, _ in HOST_BINDINGS.values()
    )


def test_agent_server_image_uses_a_deny_by_default_minimum_build_context() -> None:
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
    dockerignore = DOCKERIGNORE_PATH.read_text(encoding="utf-8").splitlines()

    assert "ADD ." not in dockerfile
    assert "COPY ." not in dockerfile
    assert (
        "COPY pyproject.toml uv.lock README.md /deps/FIN_Insight_Agent/"
        in dockerfile
    )
    assert "COPY src /deps/FIN_Insight_Agent/src" in dockerfile
    rules = [
        line.strip()
        for line in dockerignore
        if line.strip() and not line.startswith("#")
    ]
    assert rules == [
        "**",
        "!pyproject.toml",
        "!uv.lock",
        "!README.md",
        "!src/",
        "!src/**/",
        "!src/**/*.py",
        "!src/**/*.sql",
        "**/__pycache__/**",
        "**/*.pyc",
        "**/*.pyo",
        "**/*.pyd",
        "!configs/",
        "!configs/research/",
        *(f"!configs/research/{name}" for name in CONTROL_FILES),
    ]
    assert "!configs/**" not in rules
    assert "!configs/research/**" not in rules
    assert "!src/**" not in rules
    assert {
        rule.removeprefix("!configs/research/")
        for rule in rules
        if rule.startswith("!configs/research/") and not rule.endswith("/")
    } == set(CONTROL_FILES)
    for name in CONTROL_FILES:
        relative_path = f"configs/research/{name}"
        assert dockerfile.count(relative_path) == 1
        value = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
        assert isinstance(value, dict)
    for forbidden in (
        ".env",
        ".git",
        ".codex_runtime",
        "artifacts/runtime",
        "data/staging",
        "data/manifests",
        "data/captures",
        "data/raw_private",
        "reports",
        "tests",
    ):
        assert not any(
            rule == f"!{forbidden}" or rule.startswith(f"!{forbidden}/")
            for rule in rules
        )

    # Keep the admitted source surface executable and reviewable. In
    # particular, ignored local bytecode must not become an implicit build
    # input merely because it lives below src/.
    admitted_source_suffixes = {
        Path(rule.removeprefix("!")).suffix
        for rule in rules
        if rule.startswith("!src/**/") and not rule.endswith("/")
    }
    assert admitted_source_suffixes == {".py", ".sql"}
    assert all(
        not rule.startswith("!src/")
        or rule in {"!src/", "!src/**/", "!src/**/*.py", "!src/**/*.sql"}
        for rule in rules
    )


def test_dockerfile_locks_agent_server_graph_and_runtime_dependencies() -> None:
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
    graph_match = re.search(r"^ENV LANGSERVE_GRAPHS='([^']+)'$", dockerfile, re.M)
    http_match = re.search(r"^ENV LANGGRAPH_HTTP='([^']+)'$", dockerfile, re.M)

    assert dockerfile.splitlines()[2] == f"FROM {LANGGRAPH_API_IMAGE}"
    assert graph_match is not None
    assert json.loads(graph_match.group(1)) == {
        "dell_reference_vertical": {
            "path": (
                "sec_agent.agent_runtime.dell_agent_server_entry:"
                "dell_reference_vertical_graph"
            ),
            "description": "Dell research vertical; the only product serving graph",
        }
    }
    assert http_match is not None
    assert json.loads(http_match.group(1)) == {
        "disable_a2a": True,
        "disable_mcp": True,
        "disable_ui": True,
        "disable_webhooks": True,
    }
    assert "uv export --locked --no-dev --extra agent-runtime" in dockerfile
    assert "--no-emit-project" in dockerfile
    assert "--no-deps -e ." in dockerfile
    assert "finsight-agent-runtime-requirements.txt" in dockerfile
    assert (ROOT / "uv.lock").is_file()

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for dependency in (
        '"langchain-core==1.6.1"',
        '"langchain-deepseek==1.1.0"',
        '"langchain-text-splitters==1.1.2"',
        '"langgraph==1.2.11"',
        '"langgraph-sdk==0.4.4"',
        '"langsmith==0.12.1"',
        '"mcp==2.1.1"',
        '"psycopg[binary,pool]==3.3.4"',
    ):
        assert pyproject.count(dependency) == 1


def test_root_config_and_deployment_expose_the_same_single_graph() -> None:
    root_config = json.loads((ROOT / "langgraph.json").read_text(encoding="utf-8"))
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert set(root_config["graphs"]) == {"dell_reference_vertical"}
    assert root_config["api_version"] == "0.13.3"
    assert root_config["python_version"] == "3.13"
    assert dockerfile.count('"dell_reference_vertical"') == 1


def test_readme_states_nonproduction_no_auth_boundary_and_no_fallback() -> None:
    readme_raw = (DEPLOY / "README.md").read_text(encoding="utf-8")
    readme = readme_raw.casefold()

    assert "not a production deployment" in readme
    assert "noop" in readme
    assert "127.0.0.1:${finsight_agent_server_host_port:-18123}" in readme
    assert "no host" in readme
    assert "does not provide a fastapi, sqlite, direct-invoke or no-langsmith" in readme
    assert "config --quiet" in readme
    assert "bootstrap-admin" in readme
    assert "select`/`insert" in readme
    assert not re.search(
        r"docker compose[^\r\n]*\sconfig\s*(?:\r?\n|$)",
        readme_raw,
        re.I,
    )


def test_root_env_example_declares_every_required_secret_without_values() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    for name in (
        "LANGSMITH_API_KEY",
        "DEEPSEEK_API_KEY",
        "FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD",
        "FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD",
        "FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD",
    ):
        assert re.search(rf"(?m)^{name}=$", env_example)

    assignments = dict(
        line.split("=", maxsplit=1)
        for line in env_example.splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    assert {
        name: assignments[name] for name in HOST_BINDINGS
    } == {
        name: default_source
        for name, (default_source, _) in HOST_BINDINGS.items()
    }
    assert set(CONTAINER_DATA_PATHS).isdisjoint(assignments)


def test_postgres_bootstrap_separates_non_superuser_runtime_roles() -> None:
    script = POSTGRES_INIT_PATH.read_text(encoding="utf-8")
    lowered = script.casefold()

    assert "create role langgraph_runtime login nosuperuser" in lowered
    assert "create role fin_runtime_app login nosuperuser" in lowered
    assert "create role fin_runtime_migrator nologin nosuperuser" in lowered
    assert "grant usage, create on schema public to langgraph_runtime" in lowered
    assert "revoke create on schema public from public" in lowered
    assert "revoke temporary on database postgres from public" in lowered
    assert "revoke create on schema public from fin_runtime_app" in lowered
    assert "passwords must be url-safe" in lowered
    assert "passwords must be distinct" in lowered
    assert '"$POSTGRES_PASSWORD" = "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD"' in script
    assert '"$POSTGRES_PASSWORD" = "$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD"' in script
    assert (
        '"$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" = '
        '"$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD"'
    ) in script
    assert "log_statement=none" in script
    assert "log_min_error_statement=panic" in script
    assert "log_parameter_max_length=0" in script
    assert "log_parameter_max_length_on_error=0" in script
    assert script.index("PGOPTIONS=") < script.index("psql --set=ON_ERROR_STOP=1")
    assert "set -x" not in lowered


def test_fresh_postgres_volume_installs_digest_pinned_identity_schema() -> None:
    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    installer = POSTGRES_IDENTITY_INIT_PATH.read_text(encoding="utf-8")
    fingerprint_sql = POSTGRES_FINGERPRINT_PATH.read_text(encoding="utf-8")

    assert "020-install-fin-runtime-identity.sh" in compose
    assert "001_dell_agent_server_identity_v1_0.sql" in compose
    assert "040-fin-runtime-schema-fingerprint.sql" in compose
    assert "--single-transaction" in installer
    assert "sha256sum" in installer
    assert (
        "8102f5ab615bd616f64bd83f610b2e3c3206a9de023d7e27a48069f39e864209"
        in installer
    )
    assert IDENTITY_SQL_PATH.is_file()
    assert POSTGRES_FINGERPRINT_PATH.is_file()
    fingerprint_source_digest = hashlib.sha256(
        fingerprint_sql.replace("\r\n", "\n").encode("utf-8")
    ).hexdigest()
    assert fingerprint_source_digest == (
        "dec88b731a59d696509c184cf45ea1344d5840d7aa0c07515b3902b3de9ddd00"
    )
    assert fingerprint_source_digest in installer
    assert (
        "28c2bb8501d78ca3b43e1a490acae050df46b8226d2c2511a34b99a1723ec4a8"
        in installer
    )
    for catalog_surface in (
            "pg_namespace",
            "pg_roles",
            "pg_auth_members",
            "pg_db_role_setting",
        "pg_class",
        "pg_attribute",
        "pg_constraint",
        "pg_index",
        "pg_trigger",
        "pg_proc",
        "pg_default_acl",
        "pg_get_functiondef",
    ):
        assert catalog_surface in fingerprint_sql
    for role_surface in (
        "rolconnlimit",
        "rolvaliduntil",
        "rolconfig",
        "setdatabase",
        "setrole",
        "setconfig",
    ):
        assert role_surface in fingerprint_sql
    assert "a separately reviewed migration is required" in installer
    assert installer.index("before_state=$(schema_presence)") < installer.index(
        "--single-transaction"
    )
    assert "after_catalog_sha256=$(catalog_sha256)" in installer
    assert "obj_description" in fingerprint_sql


def test_postgres_readiness_rejects_process_only_or_stale_volume_health() -> None:
    script = POSTGRES_READINESS_PATH.read_text(encoding="utf-8")

    assert "*[!A-Za-z0-9._~-]*" in script
    assert '[ "${#credential}" -ge 16 ]' in script
    assert '[ "$POSTGRES_PASSWORD" != "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" ]' in script
    assert '[ "$POSTGRES_PASSWORD" != "$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD" ]' in script
    assert (
        '[ "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" != '
        '"$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD" ]'
    ) in script
    assert script.count("--host=127.0.0.1") == 2
    assert 'check_login "$POSTGRES_PASSWORD" "$POSTGRES_USER"' in script
    assert (
        'check_login "$FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD" '
        "langgraph_runtime"
    ) in script
    assert "PGPASSWORD=\"$FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD\"" in script
    assert "040-fin-runtime-schema-fingerprint.sql" in script
    assert (
        "dec88b731a59d696509c184cf45ea1344d5840d7aa0c07515b3902b3de9ddd00"
        in script
    )
    assert (
        "28c2bb8501d78ca3b43e1a490acae050df46b8226d2c2511a34b99a1723ec4a8"
        in script
    )
    assert '--file "$normalized_fingerprint_sql"' in script
    assert 'actual_catalog_sha256=$(sha256sum "$fingerprint_rows"' in script
    assert "pg_isready" not in "\n".join(
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    )
    assert "echo" not in script


def test_agent_server_receives_only_the_fin_identity_guard_and_no_model_secret() -> None:
    api_environment = _compose()["services"]["langgraph-api"]["environment"]

    assert str(api_environment["FIN_RUNTIME_POSTGRES_URI"]).startswith(
        "postgres://fin_runtime_app:${"
    )
    assert "postgres://postgres:" not in str(
        api_environment["FIN_RUNTIME_POSTGRES_URI"]
    )
    assert "postgres://langgraph_runtime:" not in str(
        api_environment["FIN_RUNTIME_POSTGRES_URI"]
    )
    assert "DEEPSEEK_API_KEY" not in api_environment
