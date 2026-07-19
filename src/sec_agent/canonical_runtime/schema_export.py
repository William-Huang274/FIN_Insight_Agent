from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import CANONICAL_MODELS, CommandEnvelope, ResultEnvelope
from .capability_security import CAPABILITY_SECURITY_MODELS
from .budget_control import BUDGET_CONTROL_MODELS
from .hitl_governance import HITL_GOVERNANCE_MODELS
from .parallel_context import PARALLEL_CONTEXT_MODELS
from .observability_ops import OBSERVABILITY_MODELS
from .local_retrieval_skeleton import LOCAL_RETRIEVAL_SKELETON_MODELS
from .local_retrieval_fixture import LOCAL_RETRIEVAL_FIXTURE_MODELS
from .local_retrieval_fixture_oracle import LOCAL_RETRIEVAL_FIXTURE_ORACLE_MODELS


def build_schema_bundle() -> dict[str, Any]:
    models = (*CANONICAL_MODELS, *CAPABILITY_SECURITY_MODELS, *BUDGET_CONTROL_MODELS, *HITL_GOVERNANCE_MODELS, *PARALLEL_CONTEXT_MODELS, *OBSERVABILITY_MODELS, *LOCAL_RETRIEVAL_SKELETON_MODELS, *LOCAL_RETRIEVAL_FIXTURE_MODELS, *LOCAL_RETRIEVAL_FIXTURE_ORACLE_MODELS, CommandEnvelope, ResultEnvelope)
    return {
        "schema_bundle_version": "finsight_point01_generated_json_schemas_v1_0",
        "models": {model.__name__: model.model_json_schema() for model in sorted(models, key=lambda item: item.__name__)},
    }


def write_schema_bundle(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_schema_bundle(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
