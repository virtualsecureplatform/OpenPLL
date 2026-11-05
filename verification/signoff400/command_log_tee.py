"""Copy a child's combined output verbatim to a live log and the caller."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys


def relay(command, logpath):
    # A completed or interrupted native log must never be overwritten.
    with Path(logpath).open('xb') as log:
        child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        try:
            while True:
                chunk=os.read(child.stdout.fileno(),65536)
                if not chunk:break
                log.write(chunk);log.flush()
                sys.stdout.buffer.write(chunk);sys.stdout.buffer.flush()
            return child.wait()
        finally:
            child.stdout.close()
            if child.poll() is None:
                child.terminate();child.wait()


def finish(code):
    if code<0:
        signal.signal(-code,signal.SIG_DFL)
        os.kill(os.getpid(),-code)
    raise SystemExit(code)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args();command=args.command
    if command[:1]==['--']:command=command[1:]
    if not command:parser.error('child command required')
    finish(relay(command,args.output))
