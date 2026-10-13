"""Bind working papers to a Java-authorized execution, never to model arguments.

This composition primitive does not enable the organization research graph.
All inputs use current_project_and_all_inputs, including derived working papers.
"""
from contextlib import contextmanager

from .working_memory_tools import native_memory_scope


@contextmanager
def organization_memory_scope(reader):
    grant, manifest, _ = reader._grant()
    with native_memory_scope('organization:' + manifest['organization_id'], grant['execution_id'],
                             access_check=lambda: reader._after(grant), allow_remote_search=False):
        yield
