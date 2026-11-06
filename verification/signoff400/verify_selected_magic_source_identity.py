"""Verify a downloaded Magic source archive against a retained Nix source hash.

NAR serialization is streamed into SHA256; no Nix installation is needed.
This checks source identity only, never antenna behavior or qualification.
"""
import argparse
import base64
import hashlib
import json
import os
import stat
import struct
import tarfile
import tempfile
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def nar_hash(root):
    digest = hashlib.sha256()

    def string(value):
        data = value if isinstance(value, bytes) else value.encode()
        digest.update(struct.pack('<Q', len(data)))
        digest.update(data)
        digest.update(b'\0' * (-len(data) % 8))

    def node(path):
        string('(')
        string('type')
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            string('directory')
            for entry in sorted(path.iterdir(), key=lambda p: os.fsencode(p.name)):
                string('entry')
                string('(')
                string('name')
                string(os.fsencode(entry.name))
                string('node')
                node(entry)
                string(')')
        elif stat.S_ISREG(mode):
            string('regular')
            if mode & stat.S_IXUSR:
                string('executable')
                string('')
            string('contents')
            size = path.stat().st_size
            digest.update(struct.pack('<Q', size))
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            digest.update(b'\0' * (-size % 8))
        elif stat.S_ISLNK(mode):
            string('symlink')
            string('target')
            string(os.fsencode(os.readlink(path)))
        else:
            raise ValueError('unsupported source file type: ' + str(path))
        string(')')

    string('nix-archive-1')
    node(root)
    return 'sha256-' + base64.b64encode(digest.digest()).decode()


def run(archive, identity, output):
    if output.exists():
        raise FileExistsError(output)
    expected = json.loads(identity.read_text())
    archive_sha = sha(archive)
    if archive_sha != expected['archive_sha256']:
        raise ValueError('archive SHA256 differs from retained source review')
    with tempfile.TemporaryDirectory(prefix='openpll-magic-source-') as directory:
        dest = Path(directory)
        with tarfile.open(archive) as source:
            source.extractall(dest, filter='data')
        roots = list(dest.iterdir())
        if len(roots) != 1 or not roots[0].is_dir() or roots[0].is_symlink():
            raise ValueError('unique real source directory required')
        actual = nar_hash(roots[0])
    if actual != expected['recursive_NAR_sha256']:
        raise ValueError('recursive NAR hash differs from pinned Nix source')
    output.write_text(json.dumps(dict(
        input_sha256={str(p.resolve()): sha(p) for p in [Path(__file__), archive, identity]},
        archive_sha256=archive_sha, recursive_NAR_sha256=actual,
        matches_retained_pinned_source=True,
        source_revision=expected['source_revision'],
        antenna_behavior_qualified=False, release_ready=False), indent=2) + '\n')
    print(actual)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['archive', 'identity', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.archive.resolve(), args.identity.resolve(), args.output.resolve())
