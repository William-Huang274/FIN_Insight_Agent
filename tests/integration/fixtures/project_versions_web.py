"""Saved synthetic SEC revisions over the real project BFF; never contacts SEC/models."""
from hashlib import sha256
import json
import os
from pathlib import Path

from tests.integration.fixtures.project_library_web import app  # noqa: F401
from sec_agent.research_foundation.project_library import ProjectLibrary
from sec_agent.research_foundation.project_sec_sources import ProjectSecSources

library=ProjectLibrary(Path(os.environ['FINSIGHT_LOCAL_STATE_ROOT'])/'project-library')
ProjectSecSources(library)
project='00000000-0000-4000-8000-000000000051'
library.save('local-pilot',0,{'projects':[{'id':project,'name':'合成 SEC 版本验收'}],'assignments':{},'pinned':[]})
scope=library.scope('local-pilot',project)
for number in (1,2):
    version=f'00000000-0000-4000-8000-00000000000{number}'
    payload={'facts':{'us-gaap':{'Revenue':{'label':'Synthetic revenue','units':{'USD':[
        {'val':9007199254740992+number,'start':'2025-01-01','end':'2025-03-31','filed':f'2025-05-0{number}','accn':f'synthetic-{number}','form':'10-Q'}]}}}}}
    raw=json.dumps(payload).encode()
    folder=library.documents.root/'sec-snapshots'/scope/version/'raw'/'SYN'
    folder.mkdir(parents=True);(folder/'sec_companyfacts.json').write_bytes(raw)
    body={'version':version,'ticker':'SYN','cik':'0000000001','company_name':'Synthetic only',
          'requested_at':f'2026-09-1{number}T00:00:00Z','captured_at':f'2026-09-1{number}T00:00:00Z',
          'status':'complete','sources':[{'kind':'sec_companyfacts','sha256':sha256(raw).hexdigest(),'bytes':len(raw),'url':'https://data.sec.gov/synthetic-fixture'}]}
    with library.documents.connect() as db:
        db.execute('INSERT INTO project_sec_versions VALUES(?,?,?)',(scope,version,json.dumps(body)))
