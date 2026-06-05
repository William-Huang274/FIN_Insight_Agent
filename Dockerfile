ARG NODE_IMAGE=node:22-bookworm-slim
ARG PYTHON_IMAGE=python:3.11-slim

FROM ${NODE_IMAGE} AS workbench-frontend

WORKDIR /app/apps/workbench/frontend
COPY apps/workbench/frontend/package*.json ./
RUN npm ci --no-audit --no-fund --fetch-retries=5 --fetch-retry-mintimeout=20000 --fetch-retry-maxtimeout=120000
COPY apps/workbench/frontend/ ./
RUN npm run build


FROM ${PYTHON_IMAGE} AS workbench-base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
ARG INSTALL_OS_PACKAGES=0
ARG WORKBENCH_IMAGE_KIND=backend
ARG WORKBENCH_RUNTIME_PROFILE=control-plane
ARG WORKBENCH_RELEASE_ID=local
ENV WORKBENCH_IMAGE_KIND=${WORKBENCH_IMAGE_KIND}
ENV WORKBENCH_RUNTIME_PROFILE=${WORKBENCH_RUNTIME_PROFILE}
ENV WORKBENCH_RELEASE_ID=${WORKBENCH_RELEASE_ID}
ENV WORKBENCH_SCRIPT_UPDATE_MODE=image_rebuild
ENV WORKBENCH_DATA_UPDATE_MODE=data_build_jobs
RUN if [ "$INSTALL_OS_PACKAGES" = "1" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends bash git \
        && rm -rf /var/lib/apt/lists/*; \
    fi

ARG REQUIREMENTS_FILE=requirements.txt
COPY requirements.txt requirements-workbench.txt pyproject.toml README.md README.zh-CN.md README.en.md ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r "${REQUIREMENTS_FILE}"

COPY apps ./apps
COPY configs ./configs
COPY scripts ./scripts
COPY src ./src
COPY eval_sets ./eval_sets
COPY docs/workbench ./docs/workbench

RUN mkdir -p data/workbench_private reports/quality/workbench_eval

EXPOSE 8765
CMD ["python", "scripts/workbench/start_workbench.py", "--host", "0.0.0.0", "--port", "8765"]


FROM workbench-base AS workbench-backend


FROM workbench-base AS workbench
COPY --from=workbench-frontend /app/apps/workbench/frontend/dist ./apps/workbench/frontend/dist
