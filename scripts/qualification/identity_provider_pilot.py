"""Create isolated Keycloak TLS/two-user qualification assets. No model calls.

Private output contains generated test credentials and keys; never commit it.
The qualification-only password-grant client is not a product login flow.
Product browser login uses Authlib authorization code with PKCE.
"""
import argparse
from datetime import datetime, timedelta, timezone
import ipaddress
import json
from pathlib import Path
import secrets
import subprocess

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def prepare(args):
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    now = datetime.now(timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'FinSight local qualification CA')])
    ca = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=7))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True).sign(key, hashes.SHA256()))
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')]))
        .issuer_name(subject).public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=7))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True).sign(key, hashes.SHA256()))
    (root/'ca.pem').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (root/'server.pem').write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    (root/'server.key').write_bytes(leaf_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    users = {name: secrets.token_urlsafe(24) for name in ('alice', 'bob')}
    mapper = {'name': 'finsight audience', 'protocol': 'openid-connect', 'protocolMapper': 'oidc-audience-mapper',
        'config': {'included.custom.audience': 'finsight-api', 'access.token.claim': 'true', 'id.token.claim': 'false'}}
    realm = {'realm': 'finsight-qualification', 'enabled': True, 'sslRequired': 'all',
        'users': [{'username': name, 'enabled': True, 'emailVerified': True, 'firstName': name, 'lastName': 'Qualification',
            'email': name+'@example.invalid', 'credentials': [{'type': 'password', 'value': password, 'temporary': False}]} for name, password in users.items()],
        'clients': [{'clientId': 'finsight-workbench', 'publicClient': True, 'standardFlowEnabled': True,
            'directAccessGrantsEnabled': False, 'redirectUris': ['https://localhost:18815/auth/callback'],
            'attributes': {'pkce.code.challenge.method': 'S256'}, 'protocolMappers': [mapper]},
            {'clientId': 'finsight-qualification', 'publicClient': True, 'standardFlowEnabled': False,
             'directAccessGrantsEnabled': True, 'protocolMappers': [mapper]}]}
    imports = root/'import'; imports.mkdir()
    (imports/'realm.json').write_text(json.dumps(realm), encoding='utf-8')
    env = {'FINSIGHT_AUTH_MODE': 'oidc_product', 'FINSIGHT_OIDC_ISSUER': 'https://localhost:18814/realms/finsight-qualification',
        'FINSIGHT_OIDC_AUDIENCE': 'finsight-api', 'FINSIGHT_OIDC_JWKS_URL': 'https://localhost:18814/realms/finsight-qualification/protocol/openid-connect/certs',
        'FINSIGHT_OIDC_CLIENT_ID': 'finsight-workbench', 'FINSIGHT_PUBLIC_ORIGIN': 'https://localhost:18815',
        'FINSIGHT_SESSION_SECRET': secrets.token_urlsafe(48), 'SSL_CERT_FILE': str(root/'ca.pem')}
    (root/'connection.private.json').write_text(json.dumps({'users': users, 'environment': env}, indent=2), encoding='utf-8')
    command = [args.docker, 'run', '-d', '--name', args.container, '--memory', '1g',
        '-p', '127.0.0.1:18814:8443', '-v', f'{imports.as_posix()}:/opt/keycloak/data/import:ro',
        '-v', f'{root.as_posix()}:/qualification:ro', args.image,
        'start-dev', '--import-realm', '--http-enabled=false', '--hostname=https://localhost:18814',
        '--https-certificate-file=/qualification/server.pem', '--https-certificate-key-file=/qualification/server.key']
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    (root/'container.json').write_text(json.dumps({'container_id': result.stdout.strip(), 'image': args.image,
        'public_ports': 'loopback18814 only', 'model_calls': 0}), encoding='utf-8')
    print('Isolated identity provider started; private credentials saved without display.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--docker', default='docker')
    p.add_argument('--image', required=True)
    p.add_argument('--container', default='finsight-208-identity-a1')
    prepare(p.parse_args())
