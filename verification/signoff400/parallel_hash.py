"""Bounded parallel I/O, standard ordered SHA-256 (not a different digest)."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import time


def sha_prefetch(path, readers=8, block_size=8*1024*1024, deadline=None, cancel=None):
    if readers<1 or block_size<1: raise ValueError('invalid prefetch bounds')
    fd=os.open(path,os.O_RDONLY)
    initial=os.fstat(fd)
    h=hashlib.sha256()
    def read(offset,length):
        chunks=[]
        while length:
            chunk=os.pread(fd,length,offset)
            if not chunk:raise ValueError('file truncated during hashing: '+str(path))
            chunks.append(chunk);offset+=len(chunk);length-=len(chunk)
        return b''.join(chunks)
    def check():
        if cancel is not None and cancel.is_set():raise InterruptedError('hashing cancelled')
        if deadline is not None and time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
            raise TimeoutError('input hashing exceeded whole-check budget')
    try:
        with ThreadPoolExecutor(max_workers=readers) as pool:
            pending=deque();offset=0
            while offset<initial.st_size or pending:
                check()
                while offset<initial.st_size and len(pending)<readers:
                    length=min(block_size,initial.st_size-offset)
                    pending.append(pool.submit(read,offset,length));offset+=length
                # Submission and consumption order is file byte order, irrespective
                # of completion order. Memory is bounded by readers*block_size.
                h.update(pending.popleft().result())
        final=os.fstat(fd)
        if (initial.st_size,initial.st_mtime_ns,initial.st_ctime_ns,initial.st_ino)!=(final.st_size,final.st_mtime_ns,final.st_ctime_ns,final.st_ino):
            raise ValueError('file changed during hashing: '+str(path))
        check()
        return h.hexdigest()
    finally:
        os.close(fd)
