"""Java-authorized, fixed organization evidence for a server-bound execution.

No user impersonation, browser endpoint, native dispatch, positive ACL cache,
personal memory, general SQL connection, or automatic retry is provided here.
"""
from hashlib import sha256
import json
import re
import sqlite3
import time
from urllib.parse import urlsplit
from typing import Any
from uuid import UUID

import httpx
from sec_agent.adapters.delegated_http import delegated_ssl_context

from .asset_workspace import AssetRef, AssetConflict
from .project_asset_access import ProjectAssetUnavailable


class OrganizationExecutionUnavailable(ProjectAssetUnavailable):
    """Failure must stop tools and the next model request, not become empty evidence."""


def _unavailable():
    return OrganizationExecutionUnavailable('组织执行授权或固定资料当前不可核实；停止本次读取，不自动重试。')


class OrganizationExecutionAuthority:
    def __init__(self, *, base_url, secret, execution_id, manifest_digest, transport=None,
                 network_profile='loopback'):
        parsed = urlsplit(base_url)
        hosts = {'loopback': {'localhost', '127.0.0.1'},
                 'docker-desktop-host': {'host.docker.internal'}}
        if (network_profile not in hosts or parsed.scheme != 'http' or parsed.hostname not in hosts[network_profile]
                or parsed.username or parsed.password or parsed.path not in ('', '/')
                or parsed.query or parsed.fragment):
            raise ValueError('organization_authority_network_profile_mismatch')
        # Validate the port before a signed request is constructed. Container host
        # access is an explicit deployment choice, never a URL from run config.
        if parsed.port is None or not 1 <= parsed.port <= 65535:
            raise ValueError('organization_authority_requires_explicit_port')
        if len(secret.encode()) < 32:
            raise ValueError('organization_runtime_secret_requires_32_bytes')
        self.base_url, self._secret = base_url.rstrip('/'), secret
        self.execution_id = str(UUID(str(execution_id)))
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', manifest_digest):
            raise ValueError('invalid_manifest_digest')
        self.manifest_digest, self._transport = manifest_digest, transport

    def __call__(self):
        path = f'/v1/runtime/organization-executions/{self.execution_id}/access'
        result = self.request(path, {'thread_id': self.execution_id, 'manifest_digest': self.manifest_digest})
        validate_execution_grant(result, self.execution_id, self.manifest_digest)
        return result

    def request(self, path, payload):
        """Signed internal workload request; no user principal or retry authority."""
        import jwt
        body = json.dumps(payload, separators=(',', ':')).encode()
        now = int(time.time())
        token = jwt.encode({'iss': 'finsight-agent-runtime', 'aud': 'finsight-java-organization-runtime',
                            'sub': 'finsight-agent-runtime', 'iat': now, 'exp': now + 60,
                            'method': 'POST', 'path': path, 'body_sha256': sha256(body).hexdigest()}, self._secret, algorithm='HS256')
        try:
            with httpx.Client(timeout=httpx.Timeout(10, connect=3), trust_env=False, follow_redirects=False,
                              transport=self._transport or httpx.HTTPTransport(
                                  retries=0, trust_env=False, verify=delegated_ssl_context())) as client:
                response = client.post(self.base_url + path, content=body,
                                       headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                if response.status_code != 200:
                    raise _unavailable()
                result = response.json()
            return result
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise _unavailable() from None


def validate_execution_grant(grant, execution_id, manifest_digest):
    """Validate byte-exact Java manifest before using any server-supplied path/ref."""
    try:
        if (grant['contract_version'] != 'organization_execution_binding.v1'
                or grant['status'] != 'bound' or grant['execution_id'] != execution_id
                or grant['thread_id'] != execution_id or grant['manifest_digest'] != manifest_digest
                or 'sha256:' + sha256(grant['manifest_text'].encode()).hexdigest() != manifest_digest):
            raise ValueError('scope')
        manifest = json.loads(grant['manifest_text'])
        if (manifest['contract_version'] != 'organization_research_inputs.v1'
                or manifest['visibility_policy'] != 'current_project_and_all_inputs'
                or any(manifest[key] != str(UUID(grant[key])) for key in ('draft_id', 'project_id', 'organization_id'))):
            raise ValueError('manifest_scope')
        if 'retrieval_index' in manifest:
            from .organization_index_release import validate_contract
            validate_contract(manifest['retrieval_index'])
        selected = {str(UUID(item['resource_id'])): item for item in manifest['inputs']}
        inputs = grant['inputs']
        if not 1 <= len(inputs) <= 12 or len(selected) != len(manifest['inputs']) or len(inputs) != len(selected):
            raise ValueError('input_count')
        seen = set()
        for item in inputs:
            identifier = str(UUID(item['resource_id']))
            binding, frozen = item['binding'], selected[identifier]
            ref = AssetRef.model_validate(binding['ref'])
            if (identifier in seen or binding['organization_id'] != grant['organization_id']
                    or binding['space_id'] != frozen['space_id'] or str(ref.project_id) != binding['space_id']
                    or binding['ref'] != frozen['ref'] or ref.kind != 'document'):
                raise ValueError('input_scope')
            seen.add(identifier)
        return manifest, {item['resource_id']: item['binding'] for item in inputs}
    except (ValueError, KeyError, TypeError, AttributeError):
        raise _unavailable() from None


class OrganizationExecutionReader:
    """Only resource IDs in the fixed manifest are tool arguments. Identity is injected."""
    def __init__(self, workspace, authority):
        self.workspace, self.authority = workspace, authority

    def _grant(self):
        grant = self.authority()
        manifest, inputs = validate_execution_grant(grant, self.authority.execution_id, self.authority.manifest_digest)
        return grant, manifest, inputs

    def _after(self, before):
        after, _, _ = self._grant()
        if after != before:
            raise _unavailable()

    def check(self):
        """Compatible with ResearchAuditMiddleware.source_access_check before providers."""
        self._grant()

    def catalog(self):
        _, manifest, _ = self._grant()
        # Does not return principals, storage addresses, secrets or hidden source provenance.
        return {'execution_id': self.authority.execution_id, 'manifest_digest': self.authority.manifest_digest,
                'research_as_of': manifest['research_as_of'], 'items': manifest['inputs']}

    def _read(self, resource_id):
        before, manifest, inputs = self._grant()
        if resource_id not in inputs:
            raise _unavailable()
        binding = inputs[resource_id]
        try:
            result = self.workspace.read_source('organization:' + manifest['organization_id'], binding['ref'])
            if result['version']['ref'] != binding['ref']:
                raise _unavailable()
            from .project_source_captures import validate_metric_cutoff, financial_capture_text
            capture = result.get('capture') or {}
            if capture.get('kind') == 'library_source':
                from .organization_source_projection import validate_source_cutoff
                validate_source_cutoff(result['source_bundle'], manifest['research_as_of'])
            validate_metric_cutoff(capture, manifest['research_as_of'])
            if capture.get('kind') == 'financial':
                text = financial_capture_text(capture)
                result = {**result, 'text': text[:100000], 'truncated': len(text) > 100000}
        except (KeyError, OSError, ValueError, AssetConflict, sqlite3.Error):
            raise _unavailable() from None
        self._after(before)  # An authorization response is never a lease across storage I/O.
        return result

    @staticmethod
    def _page(offset, limit, maximum):
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= maximum:
            raise ValueError('invalid_evidence_page')

    def read_text(self, resource_id, offset=0, limit=8000):
        self._page(offset, limit, 16000)
        result = self._read(resource_id)
        text = result['text']
        end = min(len(text), offset + limit)
        capture = result.get('capture') or {}
        return {'resource_id': resource_id, 'version': result['version'], 'text': text[offset:end],
                'offset': offset, 'next_offset': end if end < len(text) else None,
                'source_truncated': result['truncated'], 'needs_vision': result.get('needs_vision', False),
                'capture': {k: v for k, v in capture.items() if k != 'rows'},
                'structured_rows_available': 'rows' in capture}

    def read_rows(self, resource_id, offset=0, limit=30):
        self._page(offset, limit, 100)
        result = self._read(resource_id)
        capture = result.get('capture') or {}
        if 'rows' not in capture:
            raise ValueError('selected_evidence_has_no_structured_rows')
        rows = capture['rows']
        end = min(len(rows), offset + limit)
        return {'resource_id': resource_id, 'version': result['version'], 'rows': rows[offset:end],
                'offset': offset, 'next_offset': end if end < len(rows) else None, 'total': len(rows),
                'capture': {k: v for k, v in capture.items() if k != 'rows'}}


def build_organization_evidence_server(reader):
    """Narrow MCP composition; never adds the host's unrestricted SQL/search tools."""
    import asyncio
    from mcp.server import MCPServer
    server = MCPServer(name='finsight-organization-evidence', version='1.0.0',
                       instructions='Read only this execution\'s fixed published evidence. Preserve version, source, period and unit. Missing access is an execution failure, not missing financial evidence.')

    @server.tool(name='list_organization_evidence', structured_output=True)
    async def catalog() -> dict[str, Any]:
        """List the fixed inputs under current project AND all-source permissions."""
        return await asyncio.to_thread(reader.catalog)

    @server.tool(name='read_organization_evidence', structured_output=True)
    async def read(resource_id: str, offset: int = 0, limit: int = 8000) -> dict[str, Any]:
        """Read a fixed original's text; offset is a character offset, with explicit truncation."""
        return await asyncio.to_thread(reader.read_text, resource_id, offset, limit)

    @server.tool(name='read_organization_evidence_rows', structured_output=True)
    async def rows(resource_id: str, offset: int = 0, limit: int = 30) -> dict[str, Any]:
        """Read published financial snapshot rows without SQL or numeric coercion."""
        return await asyncio.to_thread(reader.read_rows, resource_id, offset, limit)

    return server
