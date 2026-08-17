from __future__ import annotations

from types import SimpleNamespace

import pytest

from retrieval.cross_encoder import _required_cuda_device


def test_cross_encoder_fails_closed_when_cuda_is_unavailable() -> None:
    torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        device=lambda value: value,
    )

    with pytest.raises(RuntimeError, match="local_cross_encoder_cuda_required"):
        _required_cuda_device(torch)


def test_cross_encoder_selects_cuda_without_cpu_fallback() -> None:
    torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: True),
        device=lambda value: value,
    )

    assert _required_cuda_device(torch) == "cuda"
