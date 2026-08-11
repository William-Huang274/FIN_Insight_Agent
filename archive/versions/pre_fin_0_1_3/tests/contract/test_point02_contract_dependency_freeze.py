from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = ROOT / "data/manifests/point02_entry_preflight_v1_0.json"
V10_CLOSEOUT = ROOT / "data/manifests/point02_closeout_decision_v1_0.json"
V11_CLOSEOUT = ROOT / "data/manifests/point02_closeout_decision_v1_1.json"
ADR = ROOT / "docs/architecture/repository/ADR_POINT02_AUTHORITY_ROLLBACK_20260718.md"
V10_OBJECTS = ROOT / "configs/releases/point02_canonical_object_subset_v1_0.json"
V11_OBJECTS = ROOT / "configs/releases/point02_canonical_object_subset_v1_1.json"
V10_ROUTES = ROOT / "configs/releases/point02_route_surface_map_v1_0.json"
V11_ROUTES = ROOT / "configs/releases/point02_route_surface_map_v1_1.json"
DEPENDENCIES = ROOT / "configs/releases/point02_frontend_dependency_lock_v1_0.json"
V10_OPENAPI = ROOT / "configs/releases/point02_api_v1_openapi_baseline_v1_0.json"
V11_OPENAPI = ROOT / "configs/releases/point02_api_v1_openapi_baseline_v1_1.json"
FIXTURES = ROOT / "configs/releases/point02_test_and_fixture_manifest_v1_0.json"
V10_OWNERS = ROOT / "data/manifests/point02_cross_owner_review_v1_0.json"
V11_OWNERS = ROOT / "data/manifests/point02_cross_owner_review_v1_1.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_digest(payload: dict[str, Any], *, omit: str | None = None) -> str:
    material = {key: value for key, value in payload.items() if key != omit}
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _schema_name(reference: str) -> str:
    prefix = "#/components/schemas/"
    assert reference.startswith(prefix)
    return reference.removeprefix(prefix)


def _request_schema(operation: dict[str, Any]) -> str | None:
    body = operation.get("requestBody")
    if body is None:
        return None
    reference = body["content"]["application/json"]["schema"]["$ref"]
    return _schema_name(reference)


def _success_response_schema(operation: dict[str, Any]) -> str:
    success_responses = [
        response
        for status, response in operation["responses"].items()
        if str(status).startswith("2")
    ]
    assert len(success_responses) == 1
    reference = success_responses[0]["content"]["application/json"]["schema"]["$ref"]
    return _schema_name(reference)


def _openapi_operations(openapi: dict[str, Any]) -> dict[str, dict[str, Any]]:
    operations: dict[str, dict[str, Any]] = {}
    for path_item in openapi["paths"].values():
        for method, operation in path_item.items():
            if method not in {"get", "post", "patch", "put", "delete"}:
                continue
            operation_id = operation["operationId"]
            assert operation_id not in operations
            operations[operation_id] = operation
    return operations


def _indexed(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    indexed = {row[key]: row for row in rows}
    assert len(indexed) == len(rows)
    return indexed


def test_entry_preflight_binds_active_foundation_contracts_and_rg1_debt() -> None:
    preflight = _load(PREFLIGHT)
    bindings = preflight["required_contract_bindings"]
    assert bindings["point01_scope_closeout_decision"]["canonical_digest"] == "f95aeefec9c21726896baf6cf40f3fdcfd4d6c34699f92fbeceabd705ca3902e"
    assert bindings["release_contract"]["canonical_digest"] == "be7aec37c3020f6e679ef047b37fbaa6c8b1105eb8b825498bd9d15175f520ba"
    assert bindings["detailed_execution_backlog"]["canonical_digest"] == "a35c772ca2acd358fbe8e20f2e9dd5ac271049e7c515c706a930224fadb0463b"
    assert bindings["feature_scope"]["sha256"] == "a7afc254a264d1c930ca9ee9d3355da21fab35a81dc740b799f424e4e3a11740"
    assert preflight["release_blocker"]["status"] == "hard_blocker_not_bypassable"
    assert preflight["authority_state"]["legacy_global_authority"] == "retained"
    assert "P02_1_or_P02_2_implementation" in preflight["forbidden_current_actions"]


def test_v1_1_artifacts_preserve_v1_0_candidate_evidence_and_exact_supersession() -> None:
    version_pairs = [
        (V11_OBJECTS, V10_OBJECTS, None),
        (V11_ROUTES, V10_ROUTES, None),
        (V11_OPENAPI, V10_OPENAPI, None),
        (V11_OWNERS, V10_OWNERS, None),
        (V11_CLOSEOUT, V10_CLOSEOUT, "closeout_digest"),
    ]
    for current_path, historical_path, historical_omit in version_pairs:
        current = _load(current_path)
        historical = _load(historical_path)
        supersedes = current.get("supersedes") or current["x-p02-history"]["supersedes"]
        assert supersedes["path"] == str(historical_path.relative_to(ROOT)).replace("\\", "/")
        assert supersedes["canonical_digest"] == _canonical_digest(historical, omit=historical_omit)
        history = current["history"] if "history" in current else current["x-p02-history"]
        assert history["v1_0_disposition"] == "historical_candidate_evidence_set_closure_not_approved"


def test_v1_1_derived_active_contract_set_closure() -> None:
    objects = _load(V11_OBJECTS)
    routes = _load(V11_ROUTES)
    openapi = _load(V11_OPENAPI)
    owners = _load(V11_OWNERS)

    active_surfaces = [surface for surface in routes["surfaces"] if surface["admission"] == "active_vt0_contract"]
    active_action_ids = {action for surface in active_surfaces for action in surface["active_actions"]}
    active_read_model_ids = {model for surface in active_surfaces for model in surface["active_read_models"]}
    assert active_action_ids
    assert active_read_model_ids == {
        "TaskCenterProjection",
        "CaseWorkspaceProjection",
        "DecisionSurfaceView",
        "WorkUnitExecutionView",
        "ActivityTraceView",
    }

    route_action_mappings = _indexed(routes["route_action_mappings"], "route_action_id")
    route_read_model_mappings = _indexed(routes["active_read_model_mappings"], "read_model_id")
    owner_action_mappings = _indexed(owners["closure_mapping"]["active_route_action_bindings"], "route_action_id")
    owner_read_model_mappings = _indexed(owners["closure_mapping"]["active_read_model_bindings"], "read_model_id")

    # The actual active surface declarations, route map, and owner review must name the same set.
    assert active_action_ids == set(route_action_mappings) == set(owner_action_mappings)
    assert active_read_model_ids == set(route_read_model_mappings) == set(owner_read_model_mappings)
    for action_id, mapping in route_action_mappings.items():
        reviewed = {key: value for key, value in owner_action_mappings[action_id].items() if key != "openapi_contract_owner"}
        assert reviewed == mapping
        assert owner_action_mappings[action_id]["openapi_contract_owner"] == "TECH_06"

    canonical_commands = _indexed(objects["canonical_commands"], "command_id")
    canonical_queries = _indexed(objects["canonical_queries"], "query_id")
    canonical_read_models = _indexed(objects["canonical_read_models"], "read_model_id")
    command_mappings = [mapping for mapping in route_action_mappings.values() if mapping["kind"] == "command"]
    query_mappings = [mapping for mapping in route_action_mappings.values() if mapping["kind"] == "query"]

    assert {mapping["canonical_command_id"] for mapping in command_mappings} == set(canonical_commands)
    assert {mapping["canonical_query_id"] for mapping in query_mappings} == set(canonical_queries)
    assert active_read_model_ids == set(canonical_read_models)

    for mapping in command_mappings:
        command = canonical_commands[mapping["canonical_command_id"]]
        assert mapping["canonical_owner"] == command["command_owner"]
        assert mapping["openapi_operation_id"] == command["openapi_operation_id"]
        assert mapping["request_schema"] == command["request_schema"]
        assert mapping["response_schema"] == command["response_schema"]
    for mapping in route_read_model_mappings.values():
        read_model = canonical_read_models[mapping["read_model_id"]]
        query = canonical_queries[mapping["canonical_query_id"]]
        assert mapping["read_model_owner"] == read_model["read_model_owner"] == query["query_owner"]
        assert mapping["canonical_query_id"] == read_model["query_id"]
        assert mapping["openapi_operation_id"] == query["openapi_operation_id"]
        assert mapping["response_schema"] == read_model["response_schema"]
        reviewed = {key: value for key, value in owner_read_model_mappings[mapping["read_model_id"]].items() if key != "openapi_contract_owner"}
        assert reviewed == mapping
        assert owner_read_model_mappings[mapping["read_model_id"]]["openapi_contract_owner"] == "TECH_06"

    operations = _openapi_operations(openapi)
    mapped_operation_ids = {mapping["openapi_operation_id"] for mapping in route_action_mappings.values()}
    assert set(operations) == mapped_operation_ids
    for operation_id, operation in operations.items():
        operation_mappings = [mapping for mapping in route_action_mappings.values() if mapping["openapi_operation_id"] == operation_id]
        expected_request_schemas = {mapping["request_schema"] for mapping in operation_mappings if "request_schema" in mapping}
        expected_response_schemas = {mapping["response_schema"] for mapping in operation_mappings}
        assert len(expected_request_schemas) <= 1
        assert len(expected_response_schemas) == 1
        assert _request_schema(operation) == next(iter(expected_request_schemas), None)
        assert _success_response_schema(operation) == next(iter(expected_response_schemas))

    component_schemas = set(openapi["components"]["schemas"])
    expected_request_schemas = {mapping["request_schema"] for mapping in command_mappings}
    expected_response_schemas = {mapping["response_schema"] for mapping in route_action_mappings.values()}
    assert expected_request_schemas <= component_schemas
    assert expected_response_schemas == active_read_model_ids
    assert expected_response_schemas <= component_schemas


def test_checkpoint_wire_semantics_and_resume_disposition_are_closed() -> None:
    objects = _load(V11_OBJECTS)
    routes = _load(V11_ROUTES)
    openapi = _load(V11_OPENAPI)
    owners = _load(V11_OWNERS)
    route_action_mappings = _indexed(routes["route_action_mappings"], "route_action_id")
    operations = _openapi_operations(openapi)

    accept = route_action_mappings["AcceptPlanningCheckpoint"]
    returned = route_action_mappings["ReturnPlanningCheckpoint"]
    assert accept["decision"] == "accept"
    assert returned["decision"] == "return"
    assert accept["canonical_command_id"] == returned["canonical_command_id"] == "PlanningCheckpointDecisionCommand"
    assert accept["openapi_operation_id"] == returned["openapi_operation_id"] == "reviewPlanningCheckpoint"
    assert accept["request_schema"] == returned["request_schema"] == "PlanningCheckpointDecisionCommand"

    checkpoint_command = _indexed(objects["canonical_commands"], "command_id")["PlanningCheckpointDecisionCommand"]
    assert checkpoint_command["decision_field"]["route_action_values"] == {
        "AcceptPlanningCheckpoint": "accept",
        "ReturnPlanningCheckpoint": "return",
    }
    assert checkpoint_command["version_fields"] == [
        "expected_case_version",
        "expected_decision_surface_contract_version",
        "expected_checkpoint_version",
    ]
    checkpoint_schema = openapi["components"]["schemas"]["PlanningCheckpointDecisionCommand"]
    assert checkpoint_schema["properties"]["decision"]["enum"] == ["accept", "return"]
    assert set(checkpoint_command["version_fields"]) <= set(checkpoint_schema["required"])
    assert _request_schema(operations["reviewPlanningCheckpoint"]) == "PlanningCheckpointDecisionCommand"
    assert _success_response_schema(operations["reviewPlanningCheckpoint"]) == "DecisionSurfaceView"

    route_resume = routes["future_not_admitted_actions"]
    canonical_resume = objects["future_not_admitted_actions"]
    owner_resume = owners["closure_mapping"]["future_not_admitted_actions"]
    assert route_resume == [
        {
            "route_action_id": "ResumeWorkUnit",
            "surface_route": "/cases/:caseId/activity",
            "canonical_command_id": "ResumeWorkUnitCommand",
            "command_owner": "TECH_06",
            "openapi_disposition": "not_exposed_in_P02_0_active_tranche",
            "reason": "resume_and_targeted_state_recovery_is_deferred_to_VT2_P02_5; VT1 requires start_cancel_and_typed_stop_only",
            "runtime_admission": "not_granted",
        }
    ]
    assert canonical_resume[0]["route_action_id"] == owner_resume[0]["route_action_id"] == route_resume[0]["route_action_id"]
    assert canonical_resume[0]["command_owner"] == owner_resume[0]["command_owner"] == route_resume[0]["command_owner"] == "TECH_06"
    assert canonical_resume[0]["openapi_disposition"] == owner_resume[0]["openapi_disposition"] == route_resume[0]["openapi_disposition"]
    assert "ResumeWorkUnit" not in {action for surface in routes["surfaces"] for action in surface["active_actions"]}
    assert "ResumeWorkUnitCommand" not in _indexed(objects["canonical_commands"], "command_id")
    assert "resumeWorkUnit" not in _openapi_operations(openapi)


def test_closeout_binds_current_artifacts_and_keeps_runtime_release_boundaries() -> None:
    closeout = _load(V11_CLOSEOUT)
    current_paths = {
        "P02.0-T03": V11_OBJECTS,
        "P02.0-T04": V11_ROUTES,
        "P02.0-T05": DEPENDENCIES,
        "P02.0-T06": V11_OPENAPI,
        "P02.0-T07": FIXTURES,
        "P02.0-T08": V11_OWNERS,
    }
    assert closeout["closeout_digest"] == _canonical_digest(closeout, omit="closeout_digest")
    assert closeout["entry_preflight_ref"]["canonical_digest"] == _canonical_digest(_load(PREFLIGHT))
    assert closeout["task_outputs"]["P02.0-T02"]["file_sha256"] == hashlib.sha256(ADR.read_bytes()).hexdigest()
    for task_id, path in current_paths.items():
        assert closeout["task_outputs"][task_id]["canonical_digest"] == _canonical_digest(_load(path))
    readiness = closeout["readiness"]
    assert readiness["P02.1"] == "ready_for_skeleton_fixture_internal_development_only_pending_parent_independent_review"
    assert readiness["P02.2"] == "ready_for_skeleton_fixture_internal_development_only_pending_parent_independent_review"
    assert readiness["runtime_admission"] == "not_granted"
    assert readiness["release_admission"] == "not_admitted"
    assert readiness["legacy_global_authority"] == "retained"
    assert closeout["stage_acceptance"]["calibrated"]["status"] == "not_evaluated_in_P02_0"
    assert "runtime_execution" in closeout["derived_set_closure_evidence"]["non_evidence"]
    assert "REL-PROD-001-RG1-POINT01-OPERATIONAL-VERTICAL-PATH" in closeout["hard_blockers_retained"]


def test_unchanged_contract_inputs_remain_design_only_and_uninstalled() -> None:
    dependencies = _load(DEPENDENCIES)
    fixtures = _load(FIXTURES)
    assert all(row["install_status"] == "not_installed" for row in dependencies["proposed_dependencies"])
    assert {row["fixture_id"] for row in fixtures["fixtures"]} == {"p36_ai_infrastructure", "enterprise_ai_saas", "us_banks"}
    assert fixtures["profiles"]["operational"]["allowed_now"] is False
