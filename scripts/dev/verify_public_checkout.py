"""Check a local source checkout without external services or paid calls."""

import argparse
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, help="Export a synthetic sample into a new directory.")
    args = parser.parse_args()
    from apps.workbench.backend.app import create_unconfigured_app

    with TestClient(create_unconfigured_app()) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        if health.json().get("status") != "ok":
            raise RuntimeError("Workbench health check failed")
        if client.get("/api/readiness").status_code != 503:
            raise RuntimeError("An unconfigured checkout must report its missing services")
    if args.output_directory:
        subprocess.run([sys.executable, "-m", "scripts.dev.export_synthetic_report",
                        "--output-directory", str(args.output_directory)], check=True)
    print("Workbench HTTP smoke check passed.")


if __name__ == "__main__":
    main()
