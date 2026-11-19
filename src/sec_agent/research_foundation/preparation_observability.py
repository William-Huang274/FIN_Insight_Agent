"""Engineering timings only: no source text, credentials or model calls."""
from contextlib import contextmanager
import logging
import json
from time import perf_counter

logger = logging.getLogger(__name__)


def _emit(event, **fields):
    # Production uses a message-only formatter. Keep timings in the serialized
    # message as well as structured LogRecord fields; don't silently drop them.
    logger.info(json.dumps({'event': event, **fields}, separators=(',', ':')),
                extra={'event': event, **fields})


@contextmanager
def preparation_span(phase):
    counts, start, status = {}, perf_counter(), 'error'
    _emit('organization_preparation_started', phase=phase)
    try:
        yield counts
        status = 'success'
    finally:
        _emit('organization_preparation_finished', phase=phase, status=status,
              elapsed_ms=round((perf_counter() - start) * 1000, 3), counts=counts)
