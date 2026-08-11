from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "apps" / "workbench" / "frontend" / "vite" / "src"
CONTRACT = REPO_ROOT / "configs" / "releases" / "fin_ia_0_1_vt3_deliverable_review_trace_contract_v1_0.json"


def _source(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _type_fields(source: str, type_name: str) -> set[str]:
    match = re.search(rf"export type {type_name} = \{{(?P<body>.*?)\n\}};", source, re.DOTALL)
    assert match, f"{type_name} must be exported"
    return set(re.findall(r"^  ([a-z_]+):", match.group("body"), re.MULTILINE))


def test_vt3_frontend_uses_the_contract_routes_and_exact_review_binding() -> None:
    contract = _contract()
    api = _source("api/deliverables.ts")

    assert contract["contract_id"] == "REL-PROD-001:VT3:DELIVERABLE-REVIEW-TRACE"
    for route in contract["routes"]:
        assert route["operation"] in api

    assert "getDeliverableHead" in api
    assert "compileDeliverablePreviewFixture" in api
    assert "createDeliverableReviewAction" in api
    assert "getCaseTrace" in api
    assert "`${CASES_PATH}/${encodeURIComponent(caseId)}/deliverables`" in api
    assert "`/api/v1/artifacts/${encodeURIComponent(deliverableId)}/versions/${encodeURIComponent(String(artifactVersion))}/review-actions`" in api
    assert "`${CASES_PATH}/${encodeURIComponent(caseId)}/trace`" in api
    assert "/compile-preview" not in api
    assert "/latest" not in api
    wire = contract["wire_contract"]
    assert _type_fields(api, "CompileDeliverablePreviewCommand") == set(wire["compile_command_fields"])
    assert _type_fields(api, "ReviewDeliverableVersionCommand") == set(wire["review_command_fields"])
    assert _type_fields(api, "DeliverablePreviewView") == set(wire["deliverable_view_fields"])
    assert _type_fields(api, "DeliverableTraceView") == set(wire["trace_view_fields"])
    for action in contract["review_contract"]["actions"]:
        assert f'"{action}"' in api
    assert "Idempotency-Key" in api
    assert "localStorage" not in api


def test_vt3_frontend_renders_shared_presentation_model_and_required_claims() -> None:
    contract = _contract()
    api = _source("api/deliverables.ts")
    view = _source("features/deliverable-review/DeliverableReview.tsx")

    assert "sections" in api
    assert "material_claims" in api
    assert "renderings" in api
    for field in contract["presentation_contract"]["required_claim_fields"]:
        assert field in api
    assert "HtmlPreview" in view
    assert "MarkdownPreview" in view
    assert "deliverable.renderings.html.content" in view
    assert "deliverable.renderings.markdown.content" in view
    assert 'sandbox=""' in view
    assert "HTML" in view and "Markdown" in view


def test_vt3_frontend_exposes_review_trace_states_and_bidirectional_explorer() -> None:
    contract = _contract()
    shell = _source("app/AppShell.tsx")
    view = _source("features/deliverable-review/DeliverableReview.tsx")
    css = _source("app/p02-shell.css")

    assert 'kind: "deliverable"' in shell
    assert "/deliverable" in shell
    assert "DeliverableReview" in shell
    for direction in contract["trace_contract"]["directions"]:
        assert f'"{direction}"' in view
    assert "function selectTraceDirection(direction: TraceDirection)" in view
    assert "onDirection={selectTraceDirection}" in view
    assert 'node.node_type !== "material_claim"' in view
    for node_type in contract["trace_contract"]["allowed_node_types"]:
        assert f'"{node_type}"' in view
    for state in ("loading", "empty", "offline", "permission", "conflict", "stale", "error"):
        assert f'"{state}"' in view
    assert "crypto.randomUUID()" in view
    assert "fingerprint" in view
    assert "localStorage" not in view
    assert ".vt3-main-grid" in css
    assert ".vt3-trace-grid" in css
    assert "@media (max-width: 420px)" in css
