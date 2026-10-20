"""Reuse only HTTPX certificate configuration for private delegated requests.

Clients, sockets, credentials and authorization responses are never cached here.
HTTPX constructs a TLS context even for the validated plain-HTTP loopback bridge;
loading the same CA bundle on every authorization check adds avoidable work.
"""
from functools import lru_cache
import ssl
from threading import Lock

import certifi

_lock = Lock()


@lru_cache(maxsize=1)
def _context():
    return ssl.create_default_context(cafile=certifi.where())


def delegated_ssl_context():
    """Immutable-after-creation trust configuration; certificate checks stay on."""
    with _lock:
        return _context()
