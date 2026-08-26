from __future__ import annotations

import math
from pathlib import PurePosixPath
import re
from typing import Any, Mapping
import unicodedata
from urllib.parse import unquote


class DellReportPublicValidationR8Error(ValueError):
    pass


_FORBIDDEN_PUBLIC_LOCATION = re.compile(
    r"(?:\b[a-z][a-z0-9+.-]{1,15}://|www\.|(?:urn|mailto|data):)|"
    r"(?:^|\s)(?:[a-z]:[\\/]|\\\\|//[^/\s]+/[^/\s]+|"
    r"/(?:home|users|tmp|var|etc|mnt|opt|root|workspace)(?:/|\b)|"
    r"/(?:[^/\s]+/)+[^/\s]+)",
    re.IGNORECASE | re.MULTILINE,
)
_PARENT_TRAVERSAL = re.compile(r"(?:^|[\\/])\.\.(?:[\\/]|$)")
_ENCODED_OCTET = re.compile(r"%[0-9A-Fa-f]{2}")
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"\b(?:api[_-]?key|access[_-]?token|auth(?:orization)?|bearer|"
    r"client[_-]?secret|credential|password|passwd|private[_-]?key)"
    r"\s*[:=]\s*['\"]?[^\s,;]{6,}",
    re.IGNORECASE,
)
_SECRET_LIKE_TOKEN = re.compile(
    r"\b(?:(?:secret|token|credential|private|key)[_-]"
    r"(?:live|prod|production|private|value)[_-][a-z0-9_=-]{8,}|"
    r"[a-z]{2}-(?:proj|live|prod)-[a-z0-9_-]{16,})\b",
    re.IGNORECASE,
)
_TOKEN_CANDIDATE = re.compile(r"[A-Za-z0-9_+/=-]{32,}")
_BIDI_CONTROL = frozenset(
    {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)

_DIGEST_FIELDS = frozenset(
    {
        "sha256",
        "result_digest",
        "resource_canonical_digest",
        "source_package_scan_digest",
        "raw_execution_sha256",
        "raw_execution_projection_digest",
        "validated_execution_digest",
        "private_result_sha256",
        "private_result_digest",
        "policy_digest",
    }
)
_COMMIT_FIELDS = frozenset(
    {
        "head",
        "head_tree",
        "upstream",
        "implementation_commit",
        "implementation_tree",
        "prepared_from_commit",
    }
)
_REPO_REF_FIELDS = frozenset(
    {"ref", "private_result_ref", "authority_commit_changed_paths"}
)
_PUBLIC_REF_ROOTS = frozenset(
    {"configs", "data", "docs", "reports", "scripts", "src", "tests"}
)


def _fail(code: str, path: str) -> None:
    raise DellReportPublicValidationR8Error(f"dell_03B_R8_{code}:{path}")


def _token_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {token: value.count(token) for token in set(value)}
    length = len(value)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in counts.values()
    )


def normalize_and_decode_public_string(
    value: str,
    *,
    path: str,
    maximum_decode_rounds: int = 6,
) -> tuple[str, tuple[str, ...]]:
    if not isinstance(value, str):
        _fail("public_string_type", path)
    normalized = unicodedata.normalize("NFKC", value)
    if any(
        (ord(token) < 32 and token not in "\t\n\r") or token in _BIDI_CONTROL
        for token in normalized
    ):
        _fail("public_control_or_bidi_character", path)

    decoded = normalized
    history = [decoded]
    for _ in range(maximum_decode_rounds):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = unicodedata.normalize("NFKC", next_value)
        history.append(decoded)
    if _ENCODED_OCTET.search(decoded):
        _fail("public_residual_encoded_octet", path)
    return decoded, tuple(history)


def _validate_threats(
    value: str,
    *,
    field: str,
    path: str,
) -> str:
    decoded, history = normalize_and_decode_public_string(value, path=path)
    for candidate in history:
        if _FORBIDDEN_PUBLIC_LOCATION.search(candidate):
            _fail("public_URL_or_absolute_locator", path)
        if _PARENT_TRAVERSAL.search(candidate):
            _fail("public_relative_parent_traversal", path)
        if _CREDENTIAL_ASSIGNMENT.search(candidate):
            _fail("public_credential_assignment", path)
        if _SECRET_LIKE_TOKEN.search(candidate):
            _fail("public_secret_like_token", path)

    if field in _REPO_REF_FIELDS:
        for segment in PurePosixPath(decoded).parts:
            for token in re.findall(r"[A-Za-z0-9_+=-]{32,}", segment):
                character_classes = sum(
                    bool(pattern.search(token))
                    for pattern in (
                        re.compile(r"[a-z]"),
                        re.compile(r"[A-Z]"),
                        re.compile(r"[0-9]"),
                        re.compile(r"[_+=-]"),
                    )
                )
                canonical_hex = bool(
                    re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", token)
                )
                if (
                    not canonical_hex
                    and character_classes >= 3
                    and _token_entropy(token) >= 4.35
                ):
                    _fail("public_secret_like_high_entropy", path)
    elif field not in _DIGEST_FIELDS | _COMMIT_FIELDS:
        for token in _TOKEN_CANDIDATE.findall(decoded):
            if _token_entropy(token) >= 4.35:
                _fail("public_secret_like_high_entropy", path)
    return decoded


def _validate_repo_relative_ref(value: str, *, path: str) -> None:
    if (
        "\\" in value
        or value.startswith("/")
        or re.match(r"^[a-zA-Z]:", value)
        or not re.fullmatch(r"[A-Za-z0-9._/-]+", value)
    ):
        _fail("public_repo_ref_grammar", path)
    pure = PurePosixPath(value)
    if (
        not pure.parts
        or pure.parts[0] not in _PUBLIC_REF_ROOTS
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        _fail("public_repo_ref_scope", path)


def validate_public_string_r8(
    value: str,
    *,
    field: str,
    path: str,
    target_ids: frozenset[str] | None = None,
    attempt_id: str | None = None,
) -> str:
    # Threat and entropy checks deliberately run before every type-specific
    # identifier/ref early return. Digest/commit fields only bypass generic
    # entropy after locator/secret/traversal checks and must still pass grammar.
    decoded = _validate_threats(value, field=field, path=path)
    if decoded != unicodedata.normalize("NFKC", value):
        _fail("public_encoded_or_noncanonical_value", path)
    if field in _DIGEST_FIELDS:
        if not re.fullmatch(r"[0-9a-f]{64}", decoded):
            _fail("public_digest_grammar", path)
        return decoded
    if field in _COMMIT_FIELDS:
        if not re.fullmatch(r"[0-9a-f]{40}", decoded):
            _fail("public_commit_grammar", path)
        return decoded
    if field in _REPO_REF_FIELDS:
        _validate_repo_relative_ref(decoded, path=path)
        return decoded
    if field == "target_id":
        if target_ids is None or decoded not in target_ids:
            _fail("public_target_id_value", path)
        return decoded
    if field == "attempt_id":
        if attempt_id is None or decoded != attempt_id:
            _fail("public_attempt_id_value", path)
        return decoded
    if field == "case_key":
        if decoded != "DELL":
            _fail("public_case_key_value", path)
        return decoded
    if field == "request_ids":
        if not re.fullmatch(r"REQ::DELL::[A-Z0-9_-]+::V[0-9]+", decoded):
            _fail("public_request_id_grammar", path)
        return decoded
    if field == "compiled_object_ids":
        if not re.fullmatch(r"COBJ::[A-Za-z0-9_-]{8,64}", decoded):
            _fail("public_compiled_object_id_grammar", path)
        return decoded
    if field in {"canonical_source_family_id", "source_record_id"}:
        if len(decoded) > 512 or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.:-]+", decoded
        ):
            _fail("public_source_identity_grammar", path)
        return decoded
    if field == "pack_gap_id":
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{3,96}", decoded):
            _fail("public_pack_gap_id_grammar", path)
        return decoded
    if len(decoded) > 8192:
        _fail("public_string_too_long", path)
    return decoded


def validate_public_scalar_tree_r8(
    value: Any,
    *,
    path: str = "public",
    field: str = "public",
    target_ids: frozenset[str] | None = None,
    attempt_id: str | None = None,
) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key).casefold()
            if any(
                token in key_text
                for token in (
                    "model_text",
                    "material_sentence",
                    "source_locator",
                    "secret",
                    "excerpt",
                    "raw_text",
                )
            ):
                _fail("public_forbidden_field", f"{path}.{key}")
            validate_public_scalar_tree_r8(
                nested,
                path=f"{path}.{key}",
                field=str(key),
                target_ids=target_ids,
                attempt_id=attempt_id,
            )
        return
    if isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            validate_public_scalar_tree_r8(
                nested,
                path=f"{path}[{index}]",
                field=field,
                target_ids=target_ids,
                attempt_id=attempt_id,
            )
        return
    if isinstance(value, str):
        validate_public_string_r8(
            value,
            field=field,
            path=path,
            target_ids=target_ids,
            attempt_id=attempt_id,
        )
        return
    if value is not None and not isinstance(value, (bool, int, float)):
        _fail("public_non_JSON_scalar", path)


__all__ = [
    "DellReportPublicValidationR8Error",
    "normalize_and_decode_public_string",
    "validate_public_scalar_tree_r8",
    "validate_public_string_r8",
]
