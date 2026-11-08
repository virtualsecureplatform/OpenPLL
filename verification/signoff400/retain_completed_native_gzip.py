"""Publish a lossless archive only after closed-source and round-trip verification."""
import gzip
import hashlib
import os
from pathlib import Path
from runtime_common import sha


def fingerprint(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def retain(source, destination, *, native_completed):
    source, destination = Path(source), Path(destination)
    if native_completed is not True:
        raise ValueError('normal native completion required')
    if source.is_symlink() or not source.is_file() or destination.exists() or destination.is_symlink():
        raise ValueError('regular source and new archive destination required')
    before = source.stat()
    temporary = destination.with_name(destination.name + '.compressing')
    digest = hashlib.sha256()
    with source.open('rb') as src, temporary.open('xb') as dst:
        with gzip.GzipFile(filename='', mode='wb', compresslevel=1, fileobj=dst, mtime=0) as archive:
            for block in iter(lambda: src.read(8 * 1024**2), b''):
                digest.update(block)
                archive.write(block)
        dst.flush()
        os.fsync(dst.fileno())
    expected = digest.hexdigest()
    if fingerprint(source.stat()) != fingerprint(before) or sha(source) != expected:
        raise ValueError('closed native source changed during compression')
    restored = hashlib.sha256()
    restored_bytes = 0
    with gzip.open(temporary, 'rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            restored.update(block)
            restored_bytes += len(block)
    if restored.hexdigest() != expected or restored_bytes != before.st_size or fingerprint(source.stat()) != fingerprint(before):
        raise ValueError('archive round-trip differs or closed source changed')
    compressed_hash = sha(temporary)
    compressed_bytes = temporary.stat().st_size
    os.link(temporary, destination)  # Atomic publication without replacing an existing archive.
    temporary.unlink()
    return dict(source=str(source), archive=str(destination), uncompressed_bytes=before.st_size,
                uncompressed_sha256=expected, compressed_bytes=compressed_bytes,
                compressed_sha256=compressed_hash, archive_format='gzip', compression_level=1,
                normal_native_completion_required=True, original_source_preserved=True,
                lossless_archive_roundtrip_verified=True)
