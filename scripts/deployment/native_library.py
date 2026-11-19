"""Copy/verify one immutable library in a Docker volume; never start research."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def validate(directory, expected):
    root = Path(directory)
    manifest = json.loads((root / 'library.sqlite.manifest.json').read_text(encoding='utf-8'))
    with (root / 'library.sqlite').open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != expected or manifest['sha256'] != expected:
        raise ValueError('native_library_version_mismatch')
    return actual


def install(source, destination, expected):
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    # Existing releases are immutable. A new release requires a new volume.
    if any(target.iterdir()):
        return validate(target, expected)
    for name in ('library.sqlite', 'library.sqlite.manifest.json'):
        shutil.copyfile(Path(source) / name, target / name)
    return validate(target, expected)


def volume_operation(docker, volume, expected, *, image, library=None):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]+', volume):
        raise ValueError('invalid_library_volume_name')
    if library is not None:
        subprocess.run([docker, 'volume', 'create', volume], check=True, capture_output=True)
    else:
        # Inspect first: docker run must not silently create an empty volume.
        subprocess.run([docker, 'volume', 'inspect', volume], check=True, capture_output=True)
    command = [docker, 'run', '--rm', '--pull', 'never', '--network', 'none',
               '--entrypoint', 'python', '--mount',
               f'type=volume,source={volume},target=/library' + ('' if library else ',readonly'),
               '--mount', f'type=bind,source={Path(__file__).resolve()},target=/verify.py,readonly']
    if library is not None:
        library = Path(library).resolve(strict=True)
        for source, name in ((library, 'library.sqlite'), (library.with_suffix(library.suffix+'.manifest.json'), 'library.sqlite.manifest.json')):
            command += ['--mount', f'type=bind,source={source},target=/source/{name},readonly']
    command += [image, '/verify.py', '--inside', 'install' if library else 'verify', '--sha256', expected]
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside', choices=['install', 'verify'])
    parser.add_argument('--sha256')
    parser.add_argument('--library', type=Path)
    parser.add_argument('--volume')
    parser.add_argument('--image', default='finsight-dell-report-workbench-langgraph-api')
    args = parser.parse_args()
    if args.inside:
        value = install('/source', '/library', args.sha256) if args.inside == 'install' else validate('/library', args.sha256)
        print(json.dumps({'library_sha256': value, 'status': 'verified'}))
    else:
        if not args.library or not args.volume:
            parser.error('--library and --volume required')
        from sec_agent.research_foundation.research_library import open_library
        release = open_library(args.library)
        docker = shutil.which('docker')
        if not docker:
            raise FileNotFoundError('Docker CLI not found')
        volume_operation(docker, args.volume, release.manifest['sha256'], image=args.image, library=args.library)


if __name__ == '__main__':
    main()
