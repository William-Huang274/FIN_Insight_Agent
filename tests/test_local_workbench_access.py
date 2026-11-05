from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from tests.integration.fixtures.local_workbench_access import (
    COOKIE,
    DeviceStore,
    LocalWorkbenchAccess,
)

ORIGIN = "http://127.0.0.1:22047"
HEADERS = {"origin": ORIGIN, "x-workbench-request": "1"}


def client(path):
    service = FastAPI()

    @service.api_route("/api/v1/probe", methods=["GET", "POST"])
    def probe(request: Request):
        return {"owner": request.scope.get("session", {}).get("verified_owner")}

    return TestClient(
        LocalWorkbenchAccess(service, path, 22047),
        base_url=ORIGIN,
        client=("127.0.0.1", 34567),
    )


def test_pairing_is_browser_bound_and_read_only_and_survives_service_restart(tmp_path):
    db = tmp_path / "viewer.sqlite3"
    first, other = client(db), client(db)
    assert not first.get("/auth/status").json()["authenticated"]
    ticket = first.post("/auth/device/pair", headers=HEADERS).json()["id"]
    assert (
        first.post(
            "/auth/device/redeem", json={"id": ticket}, headers=HEADERS
        ).status_code
        == 409
    )
    assert DeviceStore(db).approve(ticket)
    assert (
        other.post(
            "/auth/device/redeem", json={"id": ticket}, headers=HEADERS
        ).status_code
        == 409
    )
    granted = first.post("/auth/device/redeem", json={"id": ticket}, headers=HEADERS)
    assert (
        granted.is_success
        and "HttpOnly" in granted.headers["set-cookie"]
        and "Max-Age=31536000" in granted.headers["set-cookie"]
    )
    reopened = client(db)
    reopened.cookies.update(first.cookies)
    assert reopened.get("/api/v1/probe").json()["owner"] == "oidc:alice"
    assert reopened.post("/api/v1/probe", headers=HEADERS).status_code == 403
    assert (
        reopened.get(
            "/api/v1/probe", headers={"sec-fetch-site": "same-site"}
        ).status_code
        == 403
    )
    assert (
        reopened.get(
            "/api/v1/probe", headers={"origin": "https://elsewhere.test"}
        ).status_code
        == 403
    )
    assert reopened.post("/auth/logout", headers=HEADERS).is_success
    assert not first.get("/auth/status").json()["authenticated"]


def test_local_launcher_ticket_is_single_use_and_cross_origin_cannot_redeem(tmp_path):
    db = tmp_path / "viewer.sqlite3"
    c = client(db)
    identifier, secret = DeviceStore(db).pair(approved=True)
    args = {"id": identifier, "secret": secret}
    assert (
        c.post(
            "/auth/device/redeem",
            json=args,
            headers={**HEADERS, "origin": "http://127.0.0.1:3000"},
        ).status_code
        == 403
    )
    assert c.post("/auth/device/redeem", json=args, headers=HEADERS).is_success
    assert c.post("/auth/device/redeem", json=args, headers=HEADERS).status_code == 409
    assert COOKIE in c.cookies
