"""Keep RAM admission waiting separate from actual diagnostic execution time."""
import math,time
from resources import lease


def execute_admitted(action,deadline,*,acquire=lease,clock=time.monotonic):
    with acquire(1,2,deadline):
        start=clock()
        result=action()
        elapsed=clock()-start
        if not math.isfinite(elapsed) or elapsed<0:raise ValueError('monotonic execution duration required')
    return result,elapsed
