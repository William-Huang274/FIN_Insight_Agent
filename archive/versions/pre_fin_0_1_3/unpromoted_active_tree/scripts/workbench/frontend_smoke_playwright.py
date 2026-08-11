from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "interrupted"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a rendered Workbench frontend smoke test with Playwright.")
    parser.add_argument("--base-url", default=os.environ.get("WORKBENCH_BASE_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--screenshot-dir", type=Path, default=_default_screenshot_dir())
    parser.add_argument("--chrome-executable", default=os.environ.get("WORKBENCH_CHROME_EXECUTABLE", _default_chrome_executable()))
    parser.add_argument("--maintenance-timeout-s", type=float, default=45.0)
    parser.add_argument("--skip-maintenance", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    args.screenshot_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "base_url": base_url,
        "screenshots": {
            "desktop": str(args.screenshot_dir / "workbench_frontend_desktop.png"),
            "maintenance": str(args.screenshot_dir / "workbench_frontend_maintenance.png"),
            "mobile": str(args.screenshot_dir / "workbench_frontend_mobile.png"),
        },
        "console": [],
        "mobile_console": [],
    }

    with sync_playwright() as playwright:
        launch_options: dict[str, Any] = {"headless": True}
        if args.chrome_executable:
            launch_options["executable_path"] = args.chrome_executable
        browser = playwright.chromium.launch(**launch_options)
        try:
            desktop = browser.new_page(viewport={"width": 1440, "height": 1000})
            _capture_console(desktop, result["console"])
            desktop.goto(f"{base_url}/", wait_until="networkidle")
            _assert_workbench_loaded(desktop)
            desktop.screenshot(path=result["screenshots"]["desktop"], full_page=False)

            if not args.skip_maintenance:
                completed = _run_runtime_preflight(desktop, base_url, args.maintenance_timeout_s)
                result["maintenance_job"] = completed
                desktop.reload(wait_until="networkidle")
                desktop.get_by_role("heading", name="运行态总览").wait_for(timeout=15000)
                desktop.locator("#runtime").get_by_text(completed["job_id"]).first.wait_for(timeout=15000)
                desktop.locator("#runtime").get_by_text(completed["status"]).first.wait_for(timeout=15000)
            desktop.screenshot(path=result["screenshots"]["maintenance"], full_page=False)

            desktop.locator('a[href="#data-build"]').click()
            desktop.get_by_role("button", name=re.compile("填入建议路径")).click()
            desktop.get_by_role("button", name=re.compile("预览命令")).click()
            desktop.get_by_text("命令预览").wait_for(timeout=15000)
            data_build_text = desktop.locator("#data-build").inner_text()
            result["data_build_has_preview"] = bool(re.search(r"命令预览|preview|command", data_build_text, re.I))

            desktop.locator('a[href="#jobs"]').click()
            desktop.get_by_role("heading", name="任务中心").wait_for(timeout=15000)
            result["jobs_text_present"] = "任务中心" in desktop.locator("#jobs").inner_text()
            result["title"] = desktop.title()

            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            _capture_console(mobile, result["mobile_console"])
            mobile.goto(f"{base_url}/", wait_until="networkidle")
            mobile.get_by_role("heading", name="运行态总览").wait_for(timeout=15000)
            mobile.screenshot(path=result["screenshots"]["mobile"], full_page=False)
        finally:
            browser.close()

    blocking_console = _blocking_console(result["console"]) + _blocking_console(result["mobile_console"])
    result["blocking_console"] = blocking_console
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if blocking_console:
        return 1
    if not result.get("data_build_has_preview") or not result.get("jobs_text_present"):
        return 1
    return 0


def _default_screenshot_dir() -> Path:
    root = os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()
    return Path(root) / "workbench-frontend-smoke"


def _default_chrome_executable() -> str:
    if os.name != "nt":
        return ""
    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def _capture_console(page: Any, bucket: list[dict[str, str]]) -> None:
    def on_console(message: Any) -> None:
        if message.type in {"error", "warning"}:
            bucket.append({"type": str(message.type), "text": str(message.text)})

    page.on("console", on_console)
    page.on("pageerror", lambda error: bucket.append({"type": "pageerror", "text": str(error)}))


def _blocking_console(events: list[dict[str, str]]) -> list[dict[str, str]]:
    return [event for event in events if event.get("type") in {"error", "pageerror"}]


def _assert_workbench_loaded(page: Any) -> None:
    page.get_by_role("heading", name="运行态总览").wait_for(timeout=15000)
    page.get_by_text(re.compile(r"完整 runtime|integrated|control-plane|runtime", re.I)).first.wait_for(timeout=15000)
    body_text = page.locator("body").inner_text(timeout=15000)
    framework_overlay_terms = ["Internal Server Error", "Vite", "Failed to fetch dynamically imported module"]
    if any(term in body_text for term in framework_overlay_terms):
        raise AssertionError(f"Framework error overlay detected: {framework_overlay_terms}")


def _run_runtime_preflight(page: Any, base_url: str, timeout_s: float) -> dict[str, Any]:
    before = _latest_maintenance_run(base_url)
    before_id = str(before.get("job_id") or "") if before else ""
    page.get_by_role("button", name=re.compile(r"Runtime preflight", re.I)).first.click()

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        run = _latest_maintenance_run(base_url)
        if run and str(run.get("job_id") or "") != before_id and str(run.get("status") or "") in TERMINAL_STATUSES:
            if str(run.get("status") or "") != "completed":
                raise AssertionError(f"Maintenance job ended with non-pass status: {run}")
            return run
        time.sleep(0.5)
    raise TimeoutError("Runtime preflight maintenance job did not reach terminal status.")


def _latest_maintenance_run(base_url: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"{base_url}/api/runs", timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None
    for run in payload.get("runs") or []:
        if run.get("job_type") == "maintenance":
            return run
    return None


if __name__ == "__main__":
    raise SystemExit(main())
