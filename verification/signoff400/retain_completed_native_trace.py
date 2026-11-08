"""Retain a closed native trace without publishing an unchecked partial copy."""
import hashlib,os
from pathlib import Path
from common_v3 import sha


def retain(source,destination,*,native_completed):
    source=Path(source);destination=Path(destination)
    if native_completed is not True:raise ValueError('normal native completion required')
    if source.is_symlink() or not source.is_file() or destination.exists() or destination.is_symlink():raise ValueError('regular source and new destination required')
    before=source.stat();fingerprint=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    temporary=destination.with_name(destination.name+'.copying');digest=hashlib.sha256()
    with source.open('rb') as src,temporary.open('xb') as dst:
        for block in iter(lambda:src.read(8*1024*1024),b''):
            digest.update(block);dst.write(block)
        dst.flush();os.fsync(dst.fileno())
    expected=digest.hexdigest()
    if fingerprint(source.stat())!=fingerprint(before) or sha(source)!=expected or sha(temporary)!=expected or fingerprint(source.stat())!=fingerprint(before):raise ValueError('closed native trace changed or retained copy differs')
    temporary.rename(destination)
    return dict(source=str(source),retained=str(destination),bytes=before.st_size,sha256=expected,closed_native_trace_copy_verified=True)
