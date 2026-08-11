from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
RULES = {
    "hex_provider_key": re.compile(r"\bsk-[A-Fa-f0-9]{32,}\b"),
    "openai_project_key": re.compile(r"\bsk-proj-[A-Za-z0-9_-]{32,}\b"),
    "anthropic_key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{32,}\b"),
    "tencent_secret_id": re.compile(r"\bAKID[A-Za-z0-9]{13,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def _git_paths(*args: str) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]


def _paths() -> list[str]:
    tracked = _git_paths("ls-files")
    untracked = _git_paths("ls-files", "--others", "--exclude-standard")
    return sorted(set(tracked + untracked))


def _allowed_fixture(path: str, line: str, rule: str) -> bool:
    lowered = line.lower()
    if rule == "tencent_secret_id" and path.endswith(
        "test_fin_0_1_3_s1_08_query_facet_three_way_evaluation.py"
    ):
        return "example.com" in lowered and "src_fake" in lowered
    return False


def main() -> int:
    findings: list[dict[str, object]] = []
    scanned = 0
    for relative in _paths():
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        for line_number, line in enumerate(text.splitlines(), start=1):
            for rule, pattern in RULES.items():
                if pattern.search(line) and not _allowed_fixture(relative, line, rule):
                    findings.append(
                        {"path": relative, "line": line_number, "rule": rule}
                    )
    report = {
        "schema_version": "fin_ia_repository_secret_scan_v1_0",
        "status": "pass" if not findings else "fail",
        "files_scanned": scanned,
        "findings": findings,
        "note": "No matched secret value is printed by this scanner.",
    }
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
