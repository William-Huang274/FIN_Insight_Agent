from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.contracts import load_evidence_request, load_financial_research_kernel
from retrieval.route_compiler import (
    compile_retrieval_execution_plan,
    load_query_object_fact_route_policy,
)
from apps.workbench.backend.api.v1.research_retrieval import (
    build_research_retrieval_router,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from sec_agent.research.planning import (
    ResearchPlanningError,
    compile_research_objective,
    compile_research_planner_messages,
    compile_research_plan,
    load_research_planning_policy,
    parse_research_planner_output,
)
from sec_agent.research.material_scope import (
    compile_research_material_scope_messages,
)
from sec_agent.runtime_resource_registry import resolve_registered_runtime_resource
