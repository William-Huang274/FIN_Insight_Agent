"""Historical metric snapshots through actual BFF/Java/PG and organization reads."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
from hashlib import sha256
import socket
import threading
from uuid import uuid4

import httpx
import psycopg
import pytest

from apps.workbench.backend.business_transport import delegate
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.financial_library import content_digest
from sec_agent.research_foundation.organization_execution_access import (
    OrganizationExecutionAuthority, OrganizationExecutionReader, OrganizationExecutionUnavailable,
    build_organization_evidence_server)
from sec_agent.research_foundation.project_source_captures import render_capture
from tests.integration.test_organization_graph_native import OrganizationGraphStack
from tests.integration.test_java_intake_native import wait_for

pytestmark = pytest.mark.skipif(not os.getenv("FIN_STRUCTURED_SQL_CASES"), reason="explicit historical SQL manifest required")


def test_historical_cards_publication_conflicts_and_recovery(monkeypatch):
    connect = socket.socket.connect
    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise AssertionError("structured_driver_forbids_external_network")
        return connect(sock, address)
    monkeypatch.setattr(socket.socket, "connect", local_only)
    spec = json.loads(Path(os.environ["FIN_STRUCTURED_SQL_CASES"]).read_text(encoding="utf8"))
    s = OrganizationGraphStack()
    s.save("scope", {"real_services": ["BFF", "Spring Boot", "PostgreSQL", "SQLite custody"],
                    "synthetic": ["login identity", "explicit correction", "injected audit failure"],
                    "native_started": False, "provider_calls": 0,
                    "case_manifest_sha256": sha256(Path(os.environ["FIN_STRUCTURED_SQL_CASES"]).read_bytes()).hexdigest(),
                    "test_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()})
    monkeypatch.setenv("FINSIGHT_BUSINESS_SHARED_SECRET", s.shared)
    def api(method, path, body=None, status=200):
        response = s.bff.request(method, "/api/v1/business/workspaces"+path,
                                **({"json": body} if body is not None else {}))
        assert response.status_code == status, response.text
        return response.json()
    def pg():
        return psycopg.connect(host="127.0.0.1", port=s.pg_port, dbname="business",
                               user="probe", password=s.password, autocommit=True, connect_timeout=2)
    def bind(project, resource):
        draft, execution = str(uuid4()), str(uuid4())
        prepared = api("POST", f"/projects/{project}/research-drafts", {
            "id": draft, "title": "Historical structured data",
            "question": "Verify fixed cards and provenance; engineering acceptance only.",
            "research_as_of": spec["as_of"], "resource_ids": [resource]})
        path = f"/v1/workspaces/projects/{project}/research-drafts/{draft}/execution-bindings"
        body = json.dumps({"id": execution, "manifest_digest": prepared["manifest_digest"]}, separators=(",", ":")).encode()
        with httpx.Client(trust_env=False) as client:
            response = client.post(f"http://127.0.0.1:{s.java_port}"+path, content=body,
                headers={"Content-Type": "application/json", "Authorization": "Bearer "+delegate("oidc:alice", "POST", path, body)})
            assert response.status_code == 200, response.text
        return OrganizationExecutionReader(AssetWorkspace(s.state/"project-library"/"organization-assets"),
            OrganizationExecutionAuthority(base_url=f"http://127.0.0.1:{s.java_port}", secret=s.runtime_secret,
                execution_id=execution, manifest_digest=prepared["manifest_digest"]))
    results = []
    try:
        s.compose("up", "-d", "--pull", "never", "postgres")
        def ready():
            try:
                with psycopg.connect(host="127.0.0.1", port=s.pg_port, dbname="probe",
                                     user="probe", password=s.password, connect_timeout=2):
                    return True
            except psycopg.OperationalError:
                return False
        wait_for(ready)
        with psycopg.connect(host="127.0.0.1", port=s.pg_port, dbname="probe",
                             user="probe", password=s.password, autocommit=True) as db:
            db.execute("CREATE DATABASE business")
        business = s.boot("java")
        s.boot("bff")
        assets = AssetWorkspace(s.state/"project-library")
        private, org, space, project = [str(uuid4()) for _ in range(4)]
        assets.library.save("oidc:alice", 0, {"projects": [{"id": private, "name": "Historical copies"}], "assignments": {}, "pinned": []})
        api("POST", "/organizations", {"id": org, "name": "SQL acceptance", "display_name": "Alice"})
        api("POST", "/spaces", {"id": space, "organization_id": org, "name": "Fixed financial cards"})
        create = {"id": project, "organization_id": org, "name": "Historical SQL", "description": "Engineering only"}
        api("POST", "/projects", create)
        api("POST", "/projects", create)
        api("POST", "/projects", {**create, "name": "Conflicting creation"}, status=409)
        with pg() as db:
            assert db.execute("SELECT count(*) FROM organization_project_audit WHERE project_id=%s", (project,)).fetchone()[0] == 1
        def publish(snapshot, name):
            note = "Historical engineering copy; not a newly verified financial conclusion."
            kwargs = {"source_capture": {"snapshot": snapshot, "note": note}}
            scope = assets.library.scope("oidc:alice", private)
            content = render_capture(snapshot, note).encode()
            saved = assets.library.documents.add(scope, name, content, **kwargs)
            assert assets.library.documents.add(scope, name, content, **kwargs)["document_id"] == saved["document_id"]
            ref = next(v["ref"] for a in assets.catalog("oidc:alice", private)["items"]
                       for v in a["versions"] if v["ref"]["version_id"] == saved["document_id"])
            rid = str(uuid4())
            body = {"id": rid, "space_id": space, "ref": ref}
            response = s.request(s.bff, "POST", "/api/v1/asset-workspace/spaces/publish", json=body)
            assert s.request(s.bff, "POST", "/api/v1/asset-workspace/spaces/publish", json=body) == response
            revision = api("GET", f"/projects/{project}")["revision"]
            api("POST", f"/projects/{project}/resources/{rid}", {"revision": revision, "linked": True})
            return rid
        for n, case in enumerate(spec["cases"]):
            snapshot = case["snapshot"]
            rid = publish(snapshot, f"historical-cards-{n}.md")
            reader = bind(project, rid)
            rows = reader.read_rows(rid)
            assert rows["rows"] == snapshot["rows"]
            # Exercise the actual structured MCP tool too.
            import asyncio
            from mcp import Client
            async def read_tool():
                async with Client(build_organization_evidence_server(reader), raise_exceptions=False) as client:
                    return await client.call_tool(
                        "read_organization_evidence_rows", {"resource_id": rid, "offset": 0, "limit": 2})
            tool = asyncio.run(read_tool())
            assert not tool.is_error and tool.structured_content["rows"] == snapshot["rows"][:2]
            assert reader.read_rows(rid, offset=2, limit=2)["rows"] == snapshot["rows"][2:]
            endpoint = f"/api/v1/asset-workspace/organization-projects/{project}/resources/{rid}"
            assert s.bff.get(endpoint).json()["capture"]["rows"] == snapshot["rows"]
            correction = deepcopy(snapshot)
            correction["rows"][0]["engineering_test_revision"] = "fixture only; not issuer restatement"
            correction["query_digest"] = content_digest(correction["rows"])
            revised = publish(correction, f"engineering-card-revision-{n}.md")
            assert reader.read_rows(rid) == rows
            with pytest.raises(OrganizationExecutionUnavailable):
                reader.read_rows(revised)
            assert bind(project, revised).read_rows(revised)["rows"] == correction["rows"]
            results.append({"case": case["id"], "resource_id": rid, "snapshot_digest": content_digest(snapshot),
                            "rows": rows["rows"], "new_resource_id": revised,
                            "old_input_unchanged": True, "unselected_revision_denied": True})
            s.save("structured-progress", {"cases": results, "provider_calls": 0})
        # Two distinct edits based on the SAME revision: one wins, one conflicts.
        revision = api("GET", f"/projects/{project}")["revision"]
        barrier = threading.Barrier(2)
        def edit(name):
            barrier.wait(timeout=10)
            return s.bff.post(f"/api/v1/business/workspaces/projects/{project}", json={
                "revision": revision, "name": name, "description": "Concurrent edit", "archived": False}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(edit, name) for name in ("Editor A", "Editor B")]
            statuses = sorted(f.result(timeout=30) for f in futures)
        assert statuses == [200, 409]
        current = api("GET", f"/projects/{project}")
        assert current["revision"] == revision+1
        # PostgreSQL trigger fails after UPDATE, at the actual audit insert.
        # Scoped to this private project's row, never installed in shared databases.
        with pg() as db:
            before = db.execute("SELECT count(*) FROM organization_project_audit WHERE project_id=%s", (project,)).fetchone()[0]
            db.execute("""CREATE FUNCTION qualification_reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'qualification audit failure'; END $$""")
            db.execute("CREATE TRIGGER qualification_reject_audit BEFORE INSERT ON organization_project_audit FOR EACH ROW EXECUTE FUNCTION qualification_reject_audit()")
        edit_body = {"revision": current["revision"], "name": "Recovered edit", "description": "After explicit repair", "archived": False}
        failed = s.bff.post(f"/api/v1/business/workspaces/projects/{project}", json=edit_body)
        assert failed.status_code >= 500
        after = api("GET", f"/projects/{project}")
        assert (after["revision"], after["name"]) == (current["revision"], current["name"])
        with pg() as db:
            assert db.execute("SELECT count(*) FROM organization_project_audit WHERE project_id=%s", (project,)).fetchone()[0] == before
            db.execute("DROP TRIGGER qualification_reject_audit ON organization_project_audit")
            db.execute("DROP FUNCTION qualification_reject_audit()")
        business.terminate()
        business.wait(timeout=20)
        business = s.boot("java")
        assert api("GET", f"/projects/{project}")["revision"] == current["revision"]
        api("POST", f"/projects/{project}", edit_body)
        assert api("GET", f"/projects/{project}")["revision"] == current["revision"]+1
        assert reader.read_rows(rid) == rows
        resource = s.bff.get(f"/api/v1/asset-workspace/spaces/resources/{rid}").json()
        api("POST", f"/resources/{rid}/revoke", {"revision": resource["permission_revision"]})
        with pytest.raises(OrganizationExecutionUnavailable):
            reader.read_rows(rid)
        s.save("structured-result", {"status": "passed", "cases": results, "provider_calls": 0,
            "concurrent_edit_statuses": statuses, "audit_failure_http_status": failed.status_code,
            "duplicate_creation_has_one_audit": True,
            "audit_and_project_rolled_back": True, "java_restart_recovered": True,
            "revoked_structured_rows_denied": True, "driver_external_network_blocked": True,
            "financial_quality": "not_assessed", "native_started": False})
    finally:
        for process in s.processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=20)
        for log in s.logs:
            log.close()
        try:
            s.compose("logs", "--no-color")
        finally:
            s.compose("stop", "-t", "5")
            s.bff.close()
            s.native.close()
