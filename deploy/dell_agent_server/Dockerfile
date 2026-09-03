# Generated from the repository langgraph.json with langgraph-cli==0.4.31.
# Keep this image aligned with that file; the Compose boundary is local-only.
FROM langchain/langgraph-api:0.13.3-py3.13@sha256:ec26d6f6eb7ce3428ca476700f572205e6aff65fe62151b8e32541b0d93f2a1d

# -- Adding the minimum local package sources --
# Never copy the repository wholesale: local data, captures, receipts and
# developer runtime state must not enter the image or even the build context.
RUN mkdir -p /deps/FIN_Insight_Agent/configs/research
COPY pyproject.toml uv.lock README.md /deps/FIN_Insight_Agent/
COPY src /deps/FIN_Insight_Agent/src
COPY configs/research/fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json \
     configs/research/fin_ia_0_1_3_dell_reference_vertical_deepseek_structured_agents_v1_0.json \
     configs/research/fin_ia_0_1_3_dell_source_family_physical_route_catalog_v1_0.json \
     configs/research/fin_ia_0_1_3_dell_reviewed_evidence_enrichment_v1_0.json \
     configs/research/fin_ia_0_1_3_dell_owner_data_gate_decision_v1_0.json \
     /deps/FIN_Insight_Agent/configs/research/
# -- End of minimum local package sources --

# -- Installing all local dependencies --
RUN cd /deps/FIN_Insight_Agent \
    && uv export --locked --no-dev --extra agent-runtime --no-emit-project \
        --no-header --no-annotate --format requirements-txt \
        --output-file /tmp/finsight-agent-runtime-requirements.txt \
    && PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir \
        -c /api/constraints.txt \
        -r /tmp/finsight-agent-runtime-requirements.txt \
    && PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir \
        --no-deps -e . \
    && rm -f /tmp/finsight-agent-runtime-requirements.txt
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
