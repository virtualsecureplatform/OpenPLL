"""Cache only a container image hash between full checks in diagnostic matrices.

All other pins are hashed on every check. Image inode, size, mtime and ctime
must remain stable; any change triggers a new full hash. Finalization must use
full=True. This is a local filesystem change detector, not hostile-write isolation.
"""
from pathlib import Path
from common_v3 import sha,verify


def signature(path):
    s=Path(path).stat()
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


class ImageGuard:
    def __init__(self,image):
        self.image=str(Path(image));self.cached=None;self.hash_checks=0;self.metadata_hits=0

    def check(self,pins,full=False):
        if self.image not in pins:raise ValueError('container image must remain pinned')
        before=signature(self.image);expected=pins[self.image]
        if full or self.cached!=(before,expected):
            actual=sha(self.image);after=signature(self.image);self.hash_checks+=1
            if before!=after:raise ValueError('container image changed while hashing')
            if actual!=expected:raise ValueError('container image hash differs')
            self.cached=(after,expected)
        else:self.metadata_hits+=1
        verify({p:d for p,d in pins.items()if p!=self.image})
        if signature(self.image)!=before:raise ValueError('container image changed during pin verification')
