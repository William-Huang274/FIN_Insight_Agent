import json

import pytest

from scripts.deployment.local_identity import prepare, realm


def test_realm_restricts_redirect_grants_and_audience():
    value = realm('not-a-real-secret', {'owner': 'not-a-real-password'}, 'https://localhost:18866')
    client = value['clients'][0]
    assert client['redirectUris'] == ['https://localhost:18866/auth/callback']
    assert client['attributes']['pkce.code.challenge.method'] == 'S256'
    assert not any(client[k] for k in ('publicClient', 'directAccessGrantsEnabled', 'implicitFlowEnabled', 'serviceAccountsEnabled'))
    assert client['protocolMappers'][0]['config']['included.custom.audience'] == 'finsight-api'
    assert value['sslRequired'] == 'all' and value['bruteForceProtected']


def test_preparation_preserves_existing_identity_and_uses_loopback_tls(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives.asymmetric import padding
    root = tmp_path / 'identity'
    prepare(root)
    cert = x509.load_pem_x509_certificate((root / 'tls/server.pem').read_bytes())
    ca = x509.load_pem_x509_certificate((root / 'tls/ca.pem').read_bytes())
    ca.public_key().verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), cert.signature_hash_algorithm)
    assert cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName) == ['localhost']
    compose = (root / 'compose.yaml').read_text()
    assert "127.0.0.1:18443:8443" in compose and 'start-dev' not in compose
    assert 'identity-data:/var/lib/postgresql/data' in compose
    env = json.loads((root / 'bff-env.private.json').read_text())
    manifest = (root / 'identity-manifest.json').read_text()
    assert env['FINSIGHT_OIDC_CLIENT_SECRET'] not in manifest
    before = (root / 'credentials.private.json').read_bytes()
    with pytest.raises(FileExistsError):
        prepare(root)
    assert (root / 'credentials.private.json').read_bytes() == before


@pytest.mark.parametrize('options', [{'issuer_port': 18866}, {'issuer_port': 80}, {'subnet': '8.8.8.0/24'}])
def test_invalid_deployment_rejected_before_writes(tmp_path, options):
    with pytest.raises(ValueError):
        prepare(tmp_path / 'identity', **options)
    assert not (tmp_path / 'identity').exists()
