"""Opt-in per-request function profile, isolated fixture only; no payload capture.

Profiling changes CPU cost. Use these records for attribution, not capacity P95.
"""
import cProfile
from functools import wraps
import json
from pathlib import Path
import pstats
from time import perf_counter
from uuid import uuid4


def profiled(method, root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)

    @wraps(method)
    def call(*args, **kwargs):
        profile = cProfile.Profile()
        started = perf_counter()
        status = 'completed'
        try:
            return profile.runcall(method, *args, **kwargs)
        except BaseException as error:
            status = type(error).__name__
            raise
        finally:
            stats = pstats.Stats(profile)
            rows = sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)
            result = {'scope': 'diagnostic function timings, not uninstrumented capacity',
                'status': status, 'seconds': perf_counter()-started,
                'functions': [{'file': Path(key[0]).name, 'line': key[1], 'function': key[2],
                    'calls': value[1], 'self_seconds': value[2], 'cumulative_seconds': value[3]}
                    for key, value in rows[:300]]}
            # Unique files avoid concurrent append/interleaving and capture no
            # actors, request text, credentials, response bodies or stack locals.
            with (root/(uuid4().hex+'.json')).open('x', encoding='utf8') as handle:
                json.dump(result, handle, indent=2)
    return call


def install(root):
    from apps.workbench.backend.organization_navigation import OrganizationNavigationService
    OrganizationNavigationService.navigate = profiled(OrganizationNavigationService.navigate, root)
