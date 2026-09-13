# Generated from the repository langgraph.json with langgraph-cli==0.4.31.
# Keep this image aligned with that file; the Compose boundary is local-only.
FROM langchain/langgraph-api:0.13.3-py3.13@sha256:ec26d6f6eb7ce3428ca476700f572205e6aff65fe62151b8e32541b0d93f2a1d

# -- Adding the minimum local package sources --
# Never copy the repository wholesale: local data, captures, receipts and
# developer runtime state must not enter the image or even the build context.
RUN mkdir -p /deps/FIN_Insight_Agent/configs/research
COPY pyproject.toml uv.lock /deps/FIN_Insight_Agent/

# Install locked third-party dependencies BEFORE frequently changed source.
# Source/config changes must not redownload the entire runtime over the proxy.
RUN cd /deps/FIN_Insight_Agent \
    && uv export --quiet --locked --no-dev --extra agent-runtime --extra external-search --no-emit-project \
        --no-header --no-annotate --format requirements-txt \
        --output-file /tmp/finsight-agent-runtime-requirements.txt \
    && PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir \
        -c /api/constraints.txt \
        -r /tmp/finsight-agent-runtime-requirements.txt \
    && rm -f /tmp/finsight-agent-runtime-requirements.txt
# -- End of local dependencies install --

ENV LANGGRAPH_HTTP='{"disable_a2a": true, "disable_mcp": true, "disable_ui": true, "disable_webhooks": true}'
ENV LANGSERVE_GRAPHS='{"dell_reference_vertical": {"path": "sec_agent.agent_runtime.agent_server_entry:research_graph", "description": "Research and report-review workflow"}}'

# -- Ensure user deps did not inadvertently overwrite langgraph-api --
RUN mkdir -p /api/langgraph_api /api/langgraph_runtime /api/langgraph_license \
    && touch /api/langgraph_api/__init__.py /api/langgraph_runtime/__init__.py /api/langgraph_license/__init__.py
RUN PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir --no-deps -e /api
# -- End of ensuring user deps did not inadvertently overwrite langgraph-api --

COPY src /deps/FIN_Insight_Agent/src
COPY README.md /deps/FIN_Insight_Agent/
RUN cd /deps/FIN_Insight_Agent \
    && PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir --no-deps -e .
COPY configs/research/cases/growth_quality.json /deps/FIN_Insight_Agent/configs/research/cases/
COPY configs/research/model_routing.json /deps/FIN_Insight_Agent/configs/research/
COPY configs/research/quick_answer.json /deps/FIN_Insight_Agent/configs/research/
COPY configs/research/reference_foundation.json /deps/FIN_Insight_Agent/configs/research/
COPY configs/research/runtime/conversation.json /deps/FIN_Insight_Agent/configs/research/runtime/
COPY configs/research/runtime/research_session.json /deps/FIN_Insight_Agent/configs/research/runtime/
COPY configs/research/structured_agents.json /deps/FIN_Insight_Agent/configs/research/
# -- End of minimum local package sources --

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
