"""Private DeepSeek credentials for the personal research graph."""
import hashlib
import os
import sqlite3
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr


class ResearchKeys:
    def __init__(self, directory, master_key_file):
        self.database = Path(directory) / "personal-research-keys.sqlite3"
        self.cipher = Fernet(Path(master_key_file).read_bytes().strip())

    @classmethod
    def configured(cls):
        path = os.getenv("FINSIGHT_PERSONAL_KEY_STORE")
        master = os.getenv("FINSIGHT_PERSONAL_KEY_FILE")
        if not path and not master:
            return None
        if not path or not master:
            raise ValueError("incomplete_personal_key_store_configuration")
        return cls(path, master)

    def transact(self, statement, arguments):
        from contextlib import closing
        self.database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS keys (owner TEXT PRIMARY KEY, ciphertext BLOB NOT NULL)")
            return db.execute(statement, arguments).fetchone()

    @staticmethod
    def identity(owner):
        return hashlib.sha256(owner.encode()).hexdigest()

    def save(self, owner, key):
        if not key or len(key) > 512 or not key.isascii() or not key.isprintable() or any(c.isspace() for c in key):
            raise ValueError("invalid_personal_provider_key")
        identity = self.identity(owner)
        encrypted = self.cipher.encrypt(identity.encode() + b"\0" + key.encode())
        self.transact("INSERT OR REPLACE INTO keys VALUES (?, ?)", (identity, encrypted))

    def remove(self, owner):
        self.transact("DELETE FROM keys WHERE owner = ?", (self.identity(owner),))

    def contains(self, owner):
        return bool(self.transact("SELECT 1 FROM keys WHERE owner = ?", (self.identity(owner),)))

    def read(self, owner):
        identity = self.identity(owner)
        row = self.transact("SELECT ciphertext FROM keys WHERE owner = ?", (identity,))
        if not row:
            raise ValueError("personal_provider_key_required")
        try:
            binding, key = self.cipher.decrypt(row[0]).split(b"\0", 1)
        except (InvalidToken, ValueError):
            raise ValueError("personal_provider_key_unavailable") from None
        if binding != identity.encode():
            raise ValueError("personal_provider_key_owner_mismatch")
        return SecretStr(key.decode())


def requires_personal_key(owner):
    return owner != "local-pilot" or os.getenv("FINSIGHT_ALLOW_LOCAL_PROVIDER_KEY") != "1"


def personal_research_key(metadata):
    owner = metadata.get("owner_id", "local-pilot")
    if requires_personal_key(owner) or metadata.get("personal_provider_key"):
        store = ResearchKeys.configured()
        if not store:
            raise ValueError("personal_provider_key_required")
        return store.read(owner)
    store = ResearchKeys.configured()
    if store and store.contains(owner):
        return store.read(owner)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise ValueError("local_provider_key_unavailable")
    return SecretStr(os.environ["DEEPSEEK_API_KEY"])
