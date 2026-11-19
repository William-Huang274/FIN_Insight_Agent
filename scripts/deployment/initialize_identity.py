"""Prepare the loopback OIDC Compose overlay and a self-registering Keycloak realm."""
import argparse
import json
from pathlib import Path

from local_identity import prepare


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=root / ".secrets/identity")
    parser.add_argument("--issuer-port", type=int, default=18443)
    parser.add_argument("--https-port", type=int, default=18866)
    args = parser.parse_args()
    private = args.directory.resolve()
    prepare(private, issuer_port=args.issuer_port, app_port=args.https_port, self_registration=True)
    settings = json.loads((private / "bff-env.private.json").read_text(encoding="utf8"))
    settings.pop("SSL_CERT_FILE")  # Host path; the container uses its mounted CA.
    settings.update(
        FINSIGHT_IDENTITY_DIRECTORY=private.as_posix(),
        FINSIGHT_IDENTITY_PORT=str(args.issuer_port),
        FINSIGHT_HTTPS_PORT=str(args.https_port),
        FINSIGHT_RESOURCE_SPACES_ENABLED="1",
    )
    content = (private / "compose.env").read_text(encoding="utf8")
    for name, value in settings.items():
        value = value.replace("'", "\\'")
        content += f"{name}='{value}'\n"
    # The parent is owner-only. Each service mounts only its own required files.
    env_file = private / "identity.env"
    env_file.write_text(content, encoding="utf8")
    env_file.chmod(0o600)
    for name in ("tls/ca.pem", "tls/server.pem", "tls/server-key.pem", "import/finsight-realm.json"):
        (private / name).chmod(0o444)
    print(f"Prepared {private}. Open https://localhost:{args.https_port} after Compose starts.")


if __name__ == "__main__":
    main()
