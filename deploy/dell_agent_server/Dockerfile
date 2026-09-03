# Generated from the repository langgraph.json with langgraph-cli==0.4.31.
# Keep this image aligned with that file; the Compose boundary is local-only.
FROM langchain/langgraph-api:0.13.3-py3.13

RUN PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir -c /api/constraints.txt \
    langchain-core==1.6.1 \
    langchain-deepseek==1.1.0 \
    langchain-text-splitters==1.1.2 \
    langgraph==1.2.11 \
    langgraph-sdk==0.4.4 \
    langsmith==0.12.1 \
    mcp==2.1.1 \
    'psycopg[binary,pool]==3.3.4'

# -- Adding the minimum local package sources --
# Never copy the repository wholesale: local data, captures, receipts and
# developer runtime state must not enter the image or even the build context.
RUN mkdir -p /deps/FIN_Insight_Agent
COPY pyproject.toml README.md /deps/FIN_Insight_Agent/
COPY src /deps/FIN_Insight_Agent/src
# -- End of minimum local package sources --

# -- Installing all local dependencies --
RUN for dep in /deps/*; do \
        echo "Installing $dep"; \
        if [ -d "$dep" ]; then \
            (cd "$dep" && PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir -c /api/constraints.txt -e .); \
        fi; \
    done
# -- End of local dependencies install --

ENV LANGGRAPH_HTTP='{"disable_a2a": true, "disable_mcp": true, "disable_ui": true, "disable_webhooks": true}'
ENV LANGSERVE_GRAPHS='{"dell_reference_vertical": {"path": "sec_agent.agent_runtime.dell_agent_server_entry:dell_reference_vertical_graph", "description": "Dell research vertical; the only product serving graph"}}'

# -- Ensure user deps did not inadvertently overwrite langgraph-api --
RUN mkdir -p /api/langgraph_api /api/langgraph_runtime /api/langgraph_license \
    && touch /api/langgraph_api/__init__.py /api/langgraph_runtime/__init__.py /api/langgraph_license/__init__.py
RUN PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir --no-deps -e /api
# -- End of ensuring user deps did not inadvertently overwrite langgraph-api --

# -- Remove build package managers from the final image --
RUN pip uninstall -y pip setuptools wheel
RUN rm -rf /usr/local/lib/python*/site-packages/pip* \
        /usr/local/lib/python*/site-packages/setuptools* \
        /usr/local/lib/python*/site-packages/wheel* \
    && find /usr/local/bin -name "pip*" -delete \
    || true
RUN rm -rf /usr/lib/python*/site-packages/pip* \
        /usr/lib/python*/site-packages/setuptools* \
        /usr/lib/python*/site-packages/wheel* \
    && find /usr/bin -name "pip*" -delete \
    || true
RUN uv pip uninstall --system pip setuptools wheel && rm /usr/bin/uv /usr/bin/uvx

WORKDIR /deps/FIN_Insight_Agent
