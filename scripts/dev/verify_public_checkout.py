"""Run a bounded public-checkout check with pytest and the existing exporter.

No Docker, private datasets or model credentials required. Dependencies must
already be installed with the documented uv extras. Failures stop the check.
"""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True,
                        help="A new directory for explicitly synthetic exports.")
    args = parser.parse_args()
    output = args.output_directory.resolve()
    if output.exists():
        parser.error("Output directory already exists; choose a new directory to preserve earlier results.")
    root = Path(__file__).resolve().parents[2]
    subprocess.run([sys.executable, "-m", "pytest", "-q",
                    "tests/test_task_attachments.py", "tests/test_report_delivery.py",
                    "tests/test_studio_configuration.py", "tests/test_targeted_revision.py"],
                   cwd=root, check=True)
    subprocess.run([sys.executable, "-m", "scripts.qualification.research_delivery_smoke",
                    "--output-directory", str(output)], cwd=root, check=True)
    print("Public checkout check passed. Synthetic exports only; no model calls.")


if __name__ == "__main__":
    main()
