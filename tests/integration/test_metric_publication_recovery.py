"""Old metric cards across custody/registration failures; real HTTP and databases.

Opt-in private fixture. Faults are installed only in this attempt's stores.
No Agent, model, embedding, public library copy or shared service is required.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import threading
from uuid import uuid4

import httpx
import psycopg
import pytest

from apps.workbench.backend.space_assets import SpaceAssets
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.project_source_captures import render_capture
from tests.integration.test_organization_graph_native import OrganizationGraphStack
from tests.integration.test_java_intake_native import wait_for

pytestmark = pytest.mark.skipif(os.getenv("FIN_METRIC_RECOVERY_QUALIFICATION") != "1",
    reason="explicit isolated metric publication recovery qualification required")

PUBLICATION = "/api/v1/asset-workspace/spaces/publish"


@contextmanager
def lost_publication_reply(origin, observation):
    """Forward once, consume the real response, close TCP without returning it."""
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == PUBLICATION
            body = self.rfile.read(int(self.headers["Content-Length"]))
            headers = {k: self.headers[k] for k in
                       ("Authorization", "Content-Type", "X-Workbench-Request")}
            with httpx.Client(trust_env=False, timeout=50) as client:
                result = client.post(origin + PUBLICATION, content=body, headers=headers)
            observation.update(upstream_status=result.status_code, upstream_body=result.json())
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_old_cards_publication_failures_concurrency_and_recovery(monkeypatch):
    connect = socket.socket.connect
    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise AssertionError("publication_recovery_forbids_external_network")
        return connect(sock, address)
    monkeypatch.setattr(socket.socket, "connect", local_only)
    manifest = Path(os.environ["FIN_STRUCTURED_SQL_CASES"])
    original = manifest.read_bytes()
    spec = json.loads(original)
    assert len(spec["cases"]) >= 4
    s = OrganizationGraphStack()
    org, space, private = [str(uuid4()) for _ in range(3)]
    results = []

    def pg(database="business"):
        return psycopg.connect(host="127.0.0.1", port=s.pg_port, dbname=database,
            user="probe", password=s.password, autocommit=True, connect_timeout=2)

    def api(method, path, body=None):
        return s.request(s.bff, method, "/api/v1/business/workspaces"+path,
                         **({"json": body} if body is not None else {}))

    def sql_count(resource):
        with pg() as db:
            return db.execute("SELECT count(*) FROM space_resource WHERE id=%s", (resource,)).fetchone()[0]

    try:
        s.compose("up", "-d", "--pull", "never", "postgres")
        def ready():
            try:
                with pg("probe"):
                    return True
            except psycopg.OperationalError:
                return False
        wait_for(ready)
        with pg("probe") as db:
            db.execute("CREATE DATABASE business")
        business, bff = s.boot("java"), s.boot("bff")
        assets = AssetWorkspace(s.state/"project-library")
        shared = SpaceAssets(s.state/"project-library"/"organization-assets")
        assets.library.save("oidc:alice", 0, {"projects": [{"id": private, "name": "Historical recovery"}],
                                             "assignments": {}, "pinned": []})
        api("POST", "/organizations", {"id": org, "name": "Publication recovery", "display_name": "Alice"})
        api("POST", "/spaces", {"id": space, "organization_id": org, "name": "Fixed metric copies"})
        scope = assets.library.scope("oidc:alice", private)
        cases = []
        for index, case in enumerate(spec["cases"][:4]):
            snapshot = case["snapshot"]
            note = "Historical engineering fixture; no new financial quality assessment."
            saved = assets.library.documents.add(scope, f"historical-recovery-{index}.md",
                render_capture(snapshot, note).encode(),
                source_capture={"snapshot": snapshot, "note": note})
            ref = next(v["ref"] for a in assets.catalog("oidc:alice", private)["items"]
                       for v in a["versions"] if v["ref"]["version_id"] == saved["document_id"])
            cases.append((case, {"id": str(uuid4()), "space_id": space, "ref": ref}))

        def receipt(resource):
            with shared.workspace.library.documents.connect() as db:
                rows = db.execute("SELECT binding FROM space_publications WHERE id=?", (resource,)).fetchall()
            assert len(rows) <= 1
            return json.loads(rows[0]["binding"]) if rows else None

        def hidden(resource):
            assert sql_count(resource) == 0
            assert s.bff.get("/api/v1/asset-workspace/spaces/resources/"+resource).status_code == 404
            assert resource not in [r["id"] for r in api("GET", f"/spaces/{space}/resources")["items"]]

        def verify(case, body):
            binding = receipt(body["id"])
            assert binding is not None and binding["source_ref"] == body["ref"]
            result = s.request(s.bff, "GET", "/api/v1/asset-workspace/spaces/resources/"+body["id"])
            assert result["capture"]["rows"] == case["snapshot"]["rows"]
            assert result["permission_revision"] == 1
            assert sql_count(body["id"]) == 1
            with shared.workspace.library.documents.connect() as db:
                assert db.execute("SELECT count(*) FROM attachments WHERE id=?",
                                  (binding["ref"]["version_id"],)).fetchone()[0] == 1
            return binding

        # Python body persists, receipt INSERT fails. No Java record or public read.
        case, body = cases[0]
        with shared.workspace.library.documents.connect() as db:
            db.execute("""CREATE TRIGGER qualification_receipt_failure BEFORE INSERT ON space_publications
                          BEGIN SELECT RAISE(ABORT, 'qualification receipt failure'); END""")
        failed = s.bff.post(PUBLICATION, json=body)
        assert failed.status_code >= 500
        assert receipt(body["id"]) is None
        hidden(body["id"])
        assert len(shared.workspace.catalog("organization:"+org, space)["items"]) == 1
        with shared.workspace.library.documents.connect() as db:
            db.execute("DROP TRIGGER qualification_receipt_failure")
        assert s.bff.post(PUBLICATION, json=body).status_code == 200
        verify(case, body)
        assert len(shared.workspace.catalog("organization:"+org, space)["items"]) == 1
        results.append({"case": case["id"], "fault": "sqlite_receipt_insert",
                        "failed_status": failed.status_code, "hidden_before_repair": True,
                        "same_body_reused_after_manual_retry": True})

        # Java transaction fails on audit INSERT after resource INSERT.
        case, body = cases[1]
        with pg() as db:
            db.execute("""CREATE FUNCTION qualification_publication_audit_failure() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN
                IF NEW.action='resource_publish' THEN RAISE EXCEPTION 'qualification publication failure'; END IF;
                RETURN NEW; END $$""")
            db.execute("""CREATE TRIGGER qualification_publication_audit_failure BEFORE INSERT
                ON resource_space_audit FOR EACH ROW EXECUTE FUNCTION qualification_publication_audit_failure()""")
        failed = s.bff.post(PUBLICATION, json=body)
        assert failed.status_code >= 500
        before = receipt(body["id"])
        assert before is not None
        hidden(body["id"])
        with pg() as db:
            assert db.execute("SELECT count(*) FROM resource_space_audit WHERE action='resource_publish' AND target=%s",
                              (body["id"],)).fetchone()[0] == 0
            db.execute("DROP TRIGGER qualification_publication_audit_failure ON resource_space_audit")
            db.execute("DROP FUNCTION qualification_publication_audit_failure()")
        business.terminate()
        business.wait(timeout=20)
        business = s.boot("java")
        assert s.bff.post(PUBLICATION, json=body).status_code == 200
        assert verify(case, body) == before
        results.append({"case": case["id"], "fault": "postgres_audit_insert",
                        "failed_status": failed.status_code, "resource_and_audit_rolled_back": True,
                        "hidden_before_repair": True, "java_restart_same_binding": True})

        # Both stores commit, but caller never receives the successful HTTP reply.
        case, body = cases[2]
        observation = {}
        with lost_publication_reply(f"http://127.0.0.1:{s.bff_port}", observation) as proxy:
            with httpx.Client(trust_env=False, timeout=50) as client:
                with pytest.raises(httpx.RemoteProtocolError):
                    client.post(proxy+PUBLICATION, json=body, headers={
                        "Authorization": "Bearer qualification-alice", "X-Workbench-Request": "1"})
        assert observation["upstream_status"] == 200
        before = verify(case, body)
        for process in (business, bff):
            process.terminate()
            process.wait(timeout=20)
        business, bff = s.boot("java"), s.boot("bff")
        retry = s.request(s.bff, "POST", PUBLICATION, json=body)
        assert retry == observation["upstream_body"]
        assert verify(case, body) == before
        results.append({"case": case["id"], "fault": "tcp_reply_lost_after_commit",
                        "caller_received_success": False, "upstream_status": observation["upstream_status"],
                        "java_and_bff_restart_same_binding": True})

        # Concurrent exact retries must converge; reusing the ID for another card must conflict.
        case, body = cases[3]
        barrier = threading.Barrier(4)
        def publish():
            barrier.wait(timeout=10)
            return s.bff.post(PUBLICATION, json=body)
        with ThreadPoolExecutor(max_workers=4) as pool:
            replies = [f.result(timeout=55) for f in [pool.submit(publish) for _ in range(4)]]
        assert [r.status_code for r in replies] == [200]*4, [r.text for r in replies]
        assert all(r.json() == replies[0].json() for r in replies)
        before = verify(case, body)
        conflict = s.bff.post(PUBLICATION, json={**body, "ref": cases[0][1]["ref"]})
        assert conflict.status_code == 409
        assert verify(case, body) == before
        results.append({"case": case["id"], "fault": "four_concurrent_identical_requests",
                        "statuses": [r.status_code for r in replies], "different_card_same_id": 409})

        # Replays cannot undo revocation; retained custody is not publicly readable.
        api("POST", f"/resources/{body['id']}/revoke", {"revision": 1})
        assert s.bff.post(PUBLICATION, json=body).status_code == 409
        assert s.bff.get("/api/v1/asset-workspace/spaces/resources/"+body["id"]).status_code == 404
        assert receipt(body["id"]) == before
        with pg() as db:
            assert db.execute("SELECT active,revision FROM space_resource WHERE id=%s",
                              (body["id"],)).fetchone() == (False, 2)
        with shared.workspace.library.documents.connect() as db:
            assert db.execute("SELECT count(*) FROM space_publications").fetchone()[0] == 4
            assert db.execute("SELECT count(*) FROM attachments").fetchone()[0] == 4
        with pg() as db:
            assert db.execute("SELECT count(*) FROM space_resource").fetchone()[0] == 4
        assert manifest.read_bytes() == original
        s.save("publication-recovery-result", {"status": "passed", "cases": results,
            "input_manifest_sha256": sha256(original).hexdigest(), "provider_calls": 0,
            "python_copies": 4, "python_receipts": 4, "java_resources": 4,
            "revoked_replay_denied": True, "native_started": False,
            "real_services": ["HTTP BFF", "Spring Boot", "PostgreSQL", "SQLite custody"],
            "synthetic": ["login identities", "organization setup", "explicit failure injection"],
            "source_rows_unchanged": True, "financial_quality": "not_assessed",
            "production_capacity": "not_assessed", "recovery": "manual retry with original ID"})
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
