"""Read the existing local deployment environment without experiment imports."""
from pathlib import Path


def read_local_environment(path: Path | None = None) -> dict[str, str]:
    source = path or Path(__file__).resolve().parents[2] / ".env"
    if not source.is_file():
        raise RuntimeError("deployment_environment_missing")
    try:
        lines = source.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        raise RuntimeError("deployment_environment_unreadable") from None
    values: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key.strip()] = value
    return values
