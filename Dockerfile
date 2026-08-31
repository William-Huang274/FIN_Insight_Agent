ARG NODE_IMAGE=node:22-bookworm-slim@sha256:7af03b14a13c8cdd38e45058fd957bf00a72bbe17feac43b1c15a689c029c732
ARG PYTHON_IMAGE=python:3.11.16-slim-trixie@sha256:9c900dea9e8fb7e16277c179b555cc72d29a352dbc33cff48ad5a0412fd5bfc7
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.10.7@sha256:edd1fd89f3e5b005814cc8f777610445d7b7e3ed05361f9ddfae67bebfe8456a

FROM ${UV_IMAGE} AS uv-bin

FROM ${NODE_IMAGE} AS workbench-frontend

WORKDIR /app/apps/workbench/frontend
COPY apps/workbench/frontend/package*.json ./
RUN npm ci --no-audit --no-fund --fetch-retries=5 --fetch-retry-mintimeout=20000 --fetch-retry-maxtimeout=120000
COPY apps/workbench/frontend/ ./
RUN npm run build


FROM ${PYTHON_IMAGE} AS workbench-base

ARG DEBIAN_OPENSSL_VERSION=3.5.7-1~deb13u2
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/opt/finsight-venv
ENV UV_PYTHON_DOWNLOADS=0
ENV UV_LINK_MODE=copy
ENV PATH="/opt/finsight-venv/bin:$PATH"

COPY --from=uv-bin /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        "openssl=${DEBIAN_OPENSSL_VERSION}" \
        "libssl3t64=${DEBIAN_OPENSSL_VERSION}" \
        "openssl-provider-legacy=${DEBIAN_OPENSSL_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ARG WORKBENCH_IMAGE_KIND=backend
ARG WORKBENCH_RUNTIME_PROFILE=core
ARG WORKBENCH_RELEASE_ID=local
ENV WORKBENCH_IMAGE_KIND=${WORKBENCH_IMAGE_KIND}
ENV WORKBENCH_RUNTIME_PROFILE=${WORKBENCH_RUNTIME_PROFILE}
ENV WORKBENCH_RELEASE_ID=${WORKBENCH_RELEASE_ID}
ENV WORKBENCH_SCRIPT_UPDATE_MODE=image_rebuild
ENV WORKBENCH_DATA_UPDATE_MODE=data_build_jobs

COPY pyproject.toml uv.lock README.md README.zh-CN.md README.en.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
ENV FINSIGHT_REVIEWED_EVIDENCE_ROOT=/app/reviewed-evidence
ENV FINSIGHT_WORKBENCH_PRIVATE_ROOT=/app/data/workbench_private
ENV FINSIGHT_WORKBENCH_STORE_PATH=/app/state/workbench.sqlite
COPY apps ./apps
COPY configs ./configs
COPY scripts ./scripts
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable
RUN /usr/local/bin/python -m pip uninstall --yes pip setuptools \
    && rm -rf /usr/local/lib/python3.11/ensurepip
RUN groupadd --gid 10001 finsight \
    && useradd --no-log-init --create-home --uid 10001 --gid 10001 finsight \
    && mkdir -p data/workbench_private reviewed-evidence state \
    && chown -R 10001:10001 /app/state

EXPOSE 8765
CMD ["python", "scripts/dev/run_workbench_backend.py", "--host", "0.0.0.0", "--port", "8765"]


FROM workbench-base AS workbench
ARG OCI_REVISION=uncommitted
ARG OCI_SOURCE=https://github.com/William-Huang274/FIN_Insight_Agent
ENV WORKBENCH_IMAGE_KIND=current-product
ENV WORKBENCH_RUNTIME_PROFILE=reviewed-evidence
ENV WORKBENCH_DATA_UPDATE_MODE=external_data_build_jobs
COPY --from=workbench-frontend /app/apps/workbench/frontend/dist ./apps/workbench/frontend/dist
RUN rm -f /bin/uv /bin/uvx
LABEL org.opencontainers.image.source=${OCI_SOURCE} \
      org.opencontainers.image.revision=${OCI_REVISION} \
      io.finsight.image.kind=current-product \
      io.finsight.runtime.profile=reviewed-evidence
USER 10001:10001


FROM workbench-base AS control-plane
ARG OCI_REVISION=uncommitted
ARG OCI_SOURCE=https://github.com/William-Huang274/FIN_Insight_Agent
ENV WORKBENCH_IMAGE_KIND=control-plane
ENV WORKBENCH_RUNTIME_PROFILE=dagster-postgres-shadow
ENV FINSIGHT_REPOSITORY_ROOT=/app
ENV FINSIGHT_S2_POLICY_ROOT=/app/configs/financial_facts
ENV FINSIGHT_S2_OUTPUT_ROOT=/app/state/s2-shadow
ENV DAGSTER_HOME=/app/dagster-home
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --extra control-plane --no-editable \
    && mkdir -p "$DAGSTER_HOME" "$FINSIGHT_S2_OUTPUT_ROOT" \
    && cp configs/control_plane/dagster.postgres.yaml "$DAGSTER_HOME/dagster.yaml" \
    && chown -R 10001:10001 "$DAGSTER_HOME" /app/state \
    && rm -f /bin/uv /bin/uvx
LABEL org.opencontainers.image.source=${OCI_SOURCE} \
      org.opencontainers.image.revision=${OCI_REVISION} \
      io.finsight.image.kind=control-plane \
      io.finsight.runtime.profile=dagster-postgres-shadow
USER 10001:10001
EXPOSE 3000
ENTRYPOINT ["python", "-m", "sec_agent.adapters.dagster_control_plane_launcher"]
CMD ["dev", "--host", "0.0.0.0", "--port", "3000", "--module-name", "sec_agent.adapters.dagster_s2_fact_mart"]
