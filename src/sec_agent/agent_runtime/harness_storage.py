"""Host-configured native state placement; audit/workspace identities stay fixed."""
from hashlib import sha256
from pathlib import Path


def native_home(environment, directory):
    directory = Path(directory).resolve()
    root = environment.get('FINSIGHT_HARNESS_NATIVE_STORAGE_ROOT')
    if not root:
        return directory / 'native'
    root = Path(root).resolve(strict=True)
    target = root / 'sessions' / sha256(str(directory).encode()).hexdigest() / 'native'
    # Existing deployments remain readable until explicitly migrated. New
    # sessions use the shared storage immediately; never create an empty
    # replacement for an established conversation.
    legacy = directory / 'native'
    if not target.exists() and (directory / 'session-binding.json').exists() and legacy.is_dir():
        return legacy
    return target


def process_environment(environment, directory, token):
    directory = Path(directory).resolve()
    native = native_home(environment, directory)
    if native != directory / 'native':
        # Never silently replace an existing native conversation with an empty
        # one when deployment storage changes. Operations migrate bytes first.
        if (directory / 'session-binding.json').exists() and not native.exists():
            raise ValueError('harness_native_storage_requires_verified_migration')
        native.mkdir(parents=True, exist_ok=True)
        home = Path(environment['FINSIGHT_HARNESS_NATIVE_STORAGE_ROOT']).resolve() / 'package-home'
        home.mkdir(parents=True, exist_ok=True)
    else:
        home = directory
    env = {k: v for k, v in environment.items() if k.upper() in {
        'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC', 'PATHEXT'}}
    env.update(DSH_HOME=str(native), HOME=str(home), USERPROFILE=str(home),
               FIN_HARNESS_LOCAL_TOKEN=token, NO_PROXY='127.0.0.1,localhost')
    return env
