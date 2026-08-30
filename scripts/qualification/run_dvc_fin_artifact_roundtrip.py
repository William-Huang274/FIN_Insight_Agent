from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from scripts.qualification.fin_control_plane_slice_common import (
    EXPECTED_AFTER_VALUE,
    EXPECTED_BEFORE_VALUE,
    canonical_json,
    create_run_directory,
    fixture_payload,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "qualification command failed "
            f"(exit={completed.returncode}): {command!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification-root", type=Path, required=True)
    parser.add_argument("--dvc-executable", type=Path, required=True)
    args = parser.parse_args()

    run_directory = create_run_directory(args.qualification_root, "dvc")
    repository = run_directory / "repository"
    remote = run_directory / "remote"
    quarantine = run_directory / "quarantine"
    repository.mkdir(parents=True)
    remote.mkdir(parents=True)
    quarantine.mkdir(parents=True)

    env = os.environ.copy()
    env["DVC_NO_ANALYTICS"] = "true"
    env["DVC_SITE_CACHE_DIR"] = str(run_directory / "site-cache")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git executable is required for DVC qualification")
    dvc = str(args.dvc_executable.resolve())

    run([git, "init"], cwd=repository, env=env)
    run([git, "config", "user.name", "FIN qualification"], cwd=repository, env=env)
    run(
        [git, "config", "user.email", "qualification@localhost.invalid"],
        cwd=repository,
        env=env,
    )
    run([dvc, "init"], cwd=repository, env=env)

    artifact_path = repository / "dell-point-in-time-fixture.json"
    payload = {
        "fixture": fixture_payload(),
        "expected_point_in_time_values": {
            "before": EXPECTED_BEFORE_VALUE,
            "after": EXPECTED_AFTER_VALUE,
        },
        "purpose": "qualification-only deterministic FIN artifact",
    }
    artifact_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    expected_sha256 = sha256_file(artifact_path)

    run([dvc, "add", artifact_path.name], cwd=repository, env=env)
    run(
        [dvc, "remote", "add", "-d", "qualification", str(remote)],
        cwd=repository,
        env=env,
    )
    push_output = run([dvc, "push"], cwd=repository, env=env)

    shutil.move(str(artifact_path), quarantine / artifact_path.name)
    local_cache = repository / ".dvc" / "cache"
    if local_cache.exists():
        shutil.move(str(local_cache), quarantine / "local-cache-before-pull")
    pull_output = run([dvc, "pull"], cwd=repository, env=env)

    restored_sha256 = sha256_file(artifact_path)
    restored_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    if restored_sha256 != expected_sha256:
        raise RuntimeError("DVC round-trip changed the artifact digest")
    if canonical_json(restored_payload) != canonical_json(payload):
        raise RuntimeError("DVC round-trip changed the artifact payload")

    summary = {
        "dvc_version": run([dvc, "--version"], cwd=repository, env=env),
        "expected_sha256": expected_sha256,
        "pull_output": pull_output,
        "push_output": push_output,
        "remote_path": str(remote),
        "repository": str(repository),
        "restored_sha256": restored_sha256,
        "round_trip_status": "PASS",
        "run_directory": str(run_directory),
    }
    (run_directory / "dvc-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
