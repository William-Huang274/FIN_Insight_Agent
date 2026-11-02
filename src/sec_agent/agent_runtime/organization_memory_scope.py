"""Bind working papers to a Java-authorized execution, never to model arguments.

This composition primitive does not enable the organization research graph.
All inputs use current_project_and_all_inputs, including derived working papers.
"""
from contextlib import contextmanager

from .working_memory_tools import native_memory_scope


@contextmanager
def organization_memory_scope(reader, *, workspace=None):
    grant, manifest, _ = reader._grant()
    # A host-owned replay branch may isolate notes while using the same current
    # execution grant for sources. This is not a model-facing workspace selector.
    with native_memory_scope('organization:' + manifest['organization_id'], workspace or grant['execution_id'],
                             access_check=lambda: reader._after(grant), allow_remote_search=False):
        yield
