from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping


HEX64 = re.compile(r"[0-9a-f]{64}")

TARGET_IDS = (
    "DELL-RSQ-03A-TARGET-ASP",
    "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
    "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
    "DELL-RSQ-03A-TARGET-HBM-SUPPLY",
    "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
    "DELL-RSQ-03A-TARGET-UNITS",
)


class DellReportR14ContractError(ValueError):
    """A typed fail-closed R14 contract violation."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise DellReportR14ContractError(code)


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DellReportR14ContractError(
            f"R14_canonical_JSON_invalid:{type(exc).__name__}"
        ) from exc


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def domain_digest(domain: bytes, *parts: bytes) -> str:
    require(domain.endswith(b"\0"), "R14_domain_separator_must_end_with_NUL")
    payload = bytearray(domain)
    for part in parts:
        payload.extend(len(part).to_bytes(8, "big"))
        payload.extend(part)
    return sha256_bytes(bytes(payload))


def domain_rows_digest(domain: bytes, rows: Iterable[bytes]) -> str:
    require(domain.endswith(b"\0"), "R14_domain_separator_must_end_with_NUL")
    digest = hashlib.sha256()
    digest.update(domain)
    count = 0
    for row in rows:
        digest.update(len(row).to_bytes(8, "big"))
        digest.update(row)
        count += 1
    digest.update(count.to_bytes(8, "big"))
    return digest.hexdigest()


def with_result_digest(value: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(value)
    output.pop("result_digest", None)
    output["result_digest"] = canonical_digest(output)
    return output


def validate_result_digest(value: Mapping[str, Any], *, code: str) -> str:
    expected = value.get("result_digest")
    require(
        isinstance(expected, str) and bool(HEX64.fullmatch(expected)),
        f"{code}_result_digest_missing_or_invalid",
    )
    body = dict(value)
    body.pop("result_digest", None)
    actual = canonical_digest(body)
    require(actual == expected, f"{code}_result_digest_mismatch")
    return actual


def require_identifier(value: Any, *, field: str) -> str:
    require(isinstance(value, str), f"R14_{field}_not_string")
    output = value.strip()
    require(bool(output), f"R14_{field}_missing")
    require("\x00" not in output, f"R14_{field}_contains_NUL")
    return output


def require_sha256(value: Any, *, field: str) -> str:
    output = str(value or "")
    require(bool(HEX64.fullmatch(output)), f"R14_{field}_sha256_invalid")
    return output


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValueError(f"non_finite_JSON_constant:{constant}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise DellReportR14ContractError(
            f"R14_JSON_read_failed:{path.as_posix()}:{type(exc).__name__}"
        ) from exc
    require(isinstance(value, dict), f"R14_JSON_root_not_object:{path.as_posix()}")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_repo_relative_path(root: Path, value: Any, *, field: str) -> Path:
    relative = require_identifier(value, field=field)
    candidate = Path(relative)
    require(not candidate.is_absolute(), f"R14_{field}_absolute_path_forbidden")
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise DellReportR14ContractError(
            f"R14_{field}_outside_repository"
        ) from exc
    return resolved


__all__ = [
    "DellReportR14ContractError",
    "HEX64",
    "canonical_digest",
    "canonical_json_bytes",
    "domain_digest",
    "domain_rows_digest",
    "file_sha256",
    "read_json",
    "repository_root",
    "require",
    "require_identifier",
    "require_sha256",
    "resolve_repo_relative_path",
    "sha256_bytes",
    "TARGET_IDS",
    "validate_result_digest",
    "with_result_digest",
]
