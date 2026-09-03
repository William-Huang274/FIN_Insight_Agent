from __future__ import annotations

import json
from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "dell_agent_server"
COMPOSE_PATH = DEPLOY / "compose.yaml"
DOCKERFILE_PATH = DEPLOY / "Dockerfile"
DOCKERIGNORE_PATH = DEPLOY / "Dockerfile.dockerignore"


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
    assert services["langgraph-redis"]["image"] == "redis:6"
    assert services["langgraph-postgres"]["image"] == "pgvector/pgvector:pg16"
    assert services["langgraph-api"]["depends_on"] == {
        "langgraph-redis": {"condition": "service_healthy"},
        "langgraph-postgres": {"condition": "service_healthy"},
    }


def test_only_api_is_published_and_it_is_loopback_only() -> None:
    services = _compose()["services"]

    assert services["langgraph-api"]["ports"] == ["127.0.0.1:8123:8000"]
    assert "ports" not in services["langgraph-postgres"]
    assert "ports" not in services["langgraph-redis"]
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
        "LANGSMITH_API_KEY",
        "LANGSMITH_TRACING",
        "LANGSMITH_PROJECT",
        "DEEPSEEK_API_KEY",
    }
    assert api["environment"]["REDIS_URI"] == "redis://langgraph-redis:6379"
    assert api["environment"]["LANGSMITH_TRACING"] == "true"
    assert (
        api["environment"]["LANGSMITH_PROJECT"]
        == "fin-insight-dell-reference-vertical"
    )
    assert str(api["environment"]["LANGSMITH_API_KEY"]).startswith("${")
    assert str(api["environment"]["DEEPSEEK_API_KEY"]).startswith("${")
    assert "${FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD:?" in raw
    assert str(postgres["environment"]["POSTGRES_PASSWORD"]).startswith("${")
    assert re.search(r"(?im)^\.env$", (ROOT / ".gitignore").read_text("utf-8"))
    assert re.search(r"(?im)^\.env$", (ROOT / ".dockerignore").read_text("utf-8"))
    without_interpolation_contracts = re.sub(r"\$\{[^}\r\n]+\}", "${REDACTED}", raw)
    assert not re.search(
        r"(?:sk-|lsv2_|api[_-]?key\s*[:=]\s*[^$\s])",
        without_interpolation_contracts,
        re.I,
    )


def test_agent_server_image_uses_a_deny_by_default_minimum_build_context() -> None:
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
    dockerignore = DOCKERIGNORE_PATH.read_text(encoding="utf-8").splitlines()

    assert "ADD ." not in dockerfile
    assert "COPY ." not in dockerfile
    assert "COPY pyproject.toml README.md /deps/FIN_Insight_Agent/" in dockerfile
    assert "COPY src /deps/FIN_Insight_Agent/src" in dockerfile
    rules = [line.strip() for line in dockerignore if line.strip() and not line.startswith("#")]
    assert rules == ["**", "!pyproject.toml", "!README.md", "!src/", "!src/**"]
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


def test_dockerfile_locks_agent_server_graph_and_runtime_dependencies() -> None:
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
    graph_match = re.search(r"^ENV LANGSERVE_GRAPHS='([^']+)'$", dockerfile, re.M)
    http_match = re.search(r"^ENV LANGGRAPH_HTTP='([^']+)'$", dockerfile, re.M)

    assert dockerfile.splitlines()[2] == "FROM langchain/langgraph-api:0.13.3-py3.13"
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
    for dependency in (
        "langchain-core==1.6.1",
        "langchain-deepseek==1.1.0",
        "langchain-text-splitters==1.1.2",
        "langgraph==1.2.11",
        "langgraph-sdk==0.4.4",
        "langsmith==0.12.1",
        "mcp==2.1.1",
        "psycopg[binary,pool]==3.3.4",
    ):
        assert dockerfile.count(dependency) == 1


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
    assert "127.0.0.1:8123" in readme
    assert "no host" in readme
    assert "does not provide a fastapi, sqlite, direct-invoke or no-langsmith" in readme
    assert "config --quiet" in readme
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
    ):
        assert re.search(rf"(?m)^{name}=$", env_example)
