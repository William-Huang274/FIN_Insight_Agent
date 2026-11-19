"""Run a host service against a dedicated local PostgreSQL and native API."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.deployment.environment import read_local_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=["java", "workbench"])
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--db-port", type=int, default=5432)
    parser.add_argument("--business-port", type=int, default=8095)
    parser.add_argument("--ui-port", type=int, default=8765)
    parser.add_argument("--native-port", type=int, default=18165)
    parser.add_argument("--state-directory", type=Path, default=ROOT / ".finsight")
    args = parser.parse_args()
    env = {**read_local_environment(args.env_file), **os.environ}
    if args.service == "java":
        jar = ROOT / "apps/business-service/target/business-service-0.1.0.jar"
        if not jar.is_file():
            parser.error("Build apps/business-service with Maven package first.")
        env["FINSIGHT_BUSINESS_PORT"] = str(args.business_port)
        env.setdefault("FINSIGHT_BUSINESS_DB_USER", "finsight")
        env.setdefault("FINSIGHT_BUSINESS_JDBC_URL", f"jdbc:postgresql://127.0.0.1:{args.db_port}/finsight")
        env["FINSIGHT_PYTHON_INTAKE_URL"] = f"http://127.0.0.1:{args.ui_port}"
        command = ["java", "-jar", str(jar)]
    else:
        env.setdefault("FINSIGHT_PERSONAL_KEY_STORE", str(args.state_directory.resolve() / "personal-keys"))
        env.setdefault("FINSIGHT_PERSONAL_KEY_FILE", str(args.env_file.resolve().parent / ".secrets/personal-research.key"))
        env.setdefault("FINSIGHT_PERSONAL_RESEARCH_ENABLED", "1")
        env["FINSIGHT_LOCAL_STATE_ROOT"] = str(args.state_directory.resolve())
        env["FINSIGHT_BUSINESS_API_URL"] = f"http://127.0.0.1:{args.business_port}"
        env["FINSIGHT_REPORT_SESSION_API_URL"] = f"http://127.0.0.1:{args.native_port}"
        command = [sys.executable, "scripts/dev/run_workbench_backend.py", "--port", str(args.ui_port)]
    subprocess.run(command, env=env, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
