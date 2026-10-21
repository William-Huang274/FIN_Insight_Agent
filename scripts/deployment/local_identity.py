"""Prepare an isolated, loopback-only Keycloak installation; never print secrets.

Run in an access-controlled directory outside Git. Starting Compose and trusting
the generated CA are explicit operator steps; existing installations are refused.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import ipaddress
import json
from pathlib import Path
import secrets

KEYCLOAK_IMAGE = 'quay.io/keycloak/keycloak@sha256:ff4257d0d64efbe99ed1ddfaf07765cc3c36dc7518bf8324d41961327f441c54'


def realm(client_secret: str, passwords: dict[str, str], origin: str) -> dict:
    return {
        'realm': 'finsight', 'enabled': True, 'sslRequired': 'all',
        'registrationAllowed': False, 'resetPasswordAllowed': False,
        'bruteForceProtected': True, 'accessTokenLifespan': 300,
        'ssoSessionIdleTimeout': 1800, 'ssoSessionMaxLifespan': 28800,
        'clients': [{
            'clientId': 'finsight-workbench', 'name': 'FinSight Workbench',
            'protocol': 'openid-connect', 'publicClient': False,
            'secret': client_secret, 'standardFlowEnabled': True,
            'directAccessGrantsEnabled': False, 'implicitFlowEnabled': False,
            'serviceAccountsEnabled': False,
            'redirectUris': [origin + '/auth/callback'], 'webOrigins': [origin],
            'attributes': {'pkce.code.challenge.method': 'S256'},
            'protocolMappers': [{
                'name': 'finsight-api-audience', 'protocol': 'openid-connect',
                'protocolMapper': 'oidc-audience-mapper',
                'config': {'included.custom.audience': 'finsight-api',
                           'access.token.claim': 'true', 'id.token.claim': 'false'},
            }],
        }],
        'users': [{'username': username, 'enabled': True,
                   'firstName': 'FinSight', 'lastName': username,
                   'email': username + '@example.invalid', 'emailVerified': False,
                   'credentials': [{'type': 'password', 'value': password, 'temporary': False}]}
                  for username, password in passwords.items()],
    }


def prepare(root: Path, *, issuer_port: int = 18443, app_port: int = 18866,
            subnet: str = '10.248.42.0/24') -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    if not root.is_absolute():
        raise ValueError('absolute_private_directory_required')
    if not all(1024 <= port <= 65535 for port in (issuer_port, app_port)) or issuer_port == app_port:
        raise ValueError('distinct_unprivileged_ports_required')
    network = ipaddress.ip_network(subnet)
    if network.version != 4 or not network.is_private:
        raise ValueError('private_ipv4_subnet_required')
    if root.exists():
        raise FileExistsError('refusing_to_overwrite_identity_or_credentials')
    root.mkdir(parents=True, mode=0o700)
    for directory in ('tls', 'import'):
        (root / directory).mkdir(mode=0o700)
    issuer = f'https://localhost:{issuer_port}/realms/finsight'
    origin = f'https://localhost:{app_port}'
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'FinSight local acceptance CA')])
    ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=365))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
          .sign(ca_key, hashes.SHA256()))
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')]))
            .issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=90))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),
                x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    # The CA signing key is deliberately not persisted. Renew by creating a new
    # installation/certificate and explicitly replacing this user's trust entry.
    (root / 'tls/ca.pem').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (root / 'tls/server.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (root / 'tls/server-key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    passwords = {name: secrets.token_urlsafe(24) for name in ('finsight-owner', 'finsight-reader')}
    client_secret, db_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    admin_password = secrets.token_urlsafe(32)
    write = lambda name, value: (root / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    write('import/finsight-realm.json', realm(client_secret, passwords, origin))
    write('credentials.private.json', {'users': passwords, 'admin_user': 'finsight-admin', 'admin_password': admin_password})
    write('bff-env.private.json', {
        'FINSIGHT_AUTH_MODE': 'oidc_product', 'FINSIGHT_OIDC_ISSUER': issuer,
        'FINSIGHT_OIDC_AUDIENCE': 'finsight-api',
        'FINSIGHT_OIDC_JWKS_URL': issuer + '/protocol/openid-connect/certs',
        'FINSIGHT_OIDC_CLIENT_ID': 'finsight-workbench', 'FINSIGHT_OIDC_CLIENT_SECRET': client_secret,
        'FINSIGHT_PUBLIC_ORIGIN': origin, 'FINSIGHT_SESSION_SECRET': secrets.token_urlsafe(48),
        'SSL_CERT_FILE': str(root / 'tls/ca.pem'),
    })
    (root / 'compose.env').write_text(f'OIDC_DB_PASSWORD={db_password}\nOIDC_ADMIN_PASSWORD={admin_password}\n', encoding='utf-8')
    (root / 'compose.yaml').write_text(f'''services:
  identity-db:
    image: postgres:16.15-alpine
    environment:
      POSTGRES_DB: identity
      POSTGRES_USER: identity
      POSTGRES_PASSWORD: ${{OIDC_DB_PASSWORD:?required}}
    volumes:
      - identity-data:/var/lib/postgresql/data
    healthcheck:
      test: [CMD-SHELL, "pg_isready -U identity -d identity"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped
  identity:
    image: {KEYCLOAK_IMAGE}
    command: [start, --import-realm]
    environment:
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://identity-db:5432/identity
      KC_DB_USERNAME: identity
      KC_DB_PASSWORD: ${{OIDC_DB_PASSWORD:?required}}
      KC_BOOTSTRAP_ADMIN_USERNAME: finsight-admin
      KC_BOOTSTRAP_ADMIN_PASSWORD: ${{OIDC_ADMIN_PASSWORD:?required}}
      KC_HOSTNAME: https://localhost:{issuer_port}
      KC_HTTPS_CERTIFICATE_FILE: /opt/keycloak/conf/server.pem
      KC_HTTPS_CERTIFICATE_KEY_FILE: /opt/keycloak/conf/server-key.pem
      KC_HTTP_ENABLED: 'false'
      KC_HEALTH_ENABLED: 'true'
      JAVA_OPTS_KC_HEAP: '-Xms128m -Xmx512m'
    ports:
      - '127.0.0.1:{issuer_port}:8443'
    volumes:
      - ./tls/server.pem:/opt/keycloak/conf/server.pem:ro
      - ./tls/server-key.pem:/opt/keycloak/conf/server-key.pem:ro
      - ./import:/opt/keycloak/data/import:ro
    depends_on:
      identity-db:
        condition: service_healthy
    restart: unless-stopped
volumes:
  identity-data:
networks:
  default:
    ipam:
      config:
        - subnet: {subnet}
''', encoding='utf-8')
    write('identity-manifest.json', {'issuer': issuer, 'origin': origin,
        'keycloak_image': KEYCLOAK_IMAGE, 'ca_sha256': ca.fingerprint(hashes.SHA256()).hex(),
        'ca_sha1_thumbprint': ca.fingerprint(hashes.SHA1()).hex(),
        'certificate_expires': cert.not_valid_after_utc.isoformat(),
        'status': 'prepared', 'provider_calls': 0, 'scope': 'local acceptance only'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--issuer-port', type=int, default=18443)
    parser.add_argument('--app-port', type=int, default=18866)
    parser.add_argument('--subnet', default='10.248.42.0/24')
    args = parser.parse_args()
    prepare(args.private_root, issuer_port=args.issuer_port, app_port=args.app_port, subnet=args.subnet)
    print('Prepared identity files; no services started and no credentials printed.')
