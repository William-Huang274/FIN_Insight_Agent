"""Create the local Compose environment. Existing settings are preserved."""
import argparse
import base64
import os
from pathlib import Path
import secrets

GENERATED = {
    "FINSIGHT_SESSION_SECRET", "FINSIGHT_BUSINESS_DB_ADMIN_PASSWORD", "FINSIGHT_BUSINESS_DB_PASSWORD", "FINSIGHT_BUSINESS_SHARED_SECRET",
    "FINSIGHT_ORGANIZATION_RUNTIME_SECRET", "FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD",
    "FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD", "FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD",
    "FINSIGHT_FIN_RUNTIME_OPERATOR_POSTGRES_PASSWORD",
}


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=root / ".env")
    path = parser.parse_args().env_file
    key_dir = path.parent / ".secrets"
    key_path = key_dir / "personal-research.key"
    # Use a restrictive host directory. The read-only single-file mount is
    # readable by both non-root container identities.
    if path.exists():
        parser.exit(1, f"{path} already exists. Keep its database credentials.\n")
    key_dir.mkdir(mode=0o700, exist_ok=True)
    if os.name == 'posix' and key_dir.stat().st_mode & 0o077:
        parser.error(f'Restrict {key_dir} to its owner (chmod 700) and retry.')
    try:
        key_fd = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        parser.exit(1, f"{key_path} already exists. Keep its matching database and settings.\n")
    with os.fdopen(key_fd, "wb") as key:
        key.write(base64.urlsafe_b64encode(secrets.token_bytes(32)))
    key_path.chmod(0o444)
    lines = (root / ".env.example").read_text(encoding="utf8").splitlines()
    for i, line in enumerate(lines):
        if line.removesuffix("=") in GENERATED:
            lines[i] = line + secrets.token_hex(32)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        parser.exit(1, f"{path} already exists. Keep its database credentials.\n")
    with os.fdopen(fd, "w", encoding="utf8", newline="\n") as output:
        output.write("\n".join(lines) + "\n")
    print(f"Created {path}. Provider credentials are empty.")


if __name__ == "__main__":
    main()
