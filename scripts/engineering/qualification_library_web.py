"""Loopback-only qualification composition of the actual public read router."""
import os
from pathlib import Path
from fastapi import FastAPI
from apps.workbench.backend.api.v1.data_library import build_data_library_router

if os.environ.get('FIN_LIBRARY_READ_QUALIFICATION') != '1':
    raise RuntimeError('explicit_library_read_qualification_required')
os.environ['FINSIGHT_AUTH_MODE'] = 'local'
app = FastAPI()
app.include_router(build_data_library_router(
    Path(os.environ['FIN_LIBRARY_READ_STATE']),
    research_library=Path(os.environ['FIN_LIBRARY_READ_DATABASE'])), prefix='/api/v1')
