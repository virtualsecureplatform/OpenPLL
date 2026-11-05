"""Prepare an explicitly bounded native replay window with a right guard knot."""
import argparse,math
from pathlib import Path
from prepare_selected_replay_prefix import run

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['bench','replay','output']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--stop-ns',type=float,required=True);a=p.parse_args()
    if not math.isfinite(a.stop_ns) or not 0<a.stop_ns<=260:p.error('endpoint must be within native trace: 0 < ns <= 260')
    run(a.bench.resolve(),a.replay.resolve(),a.output.resolve(),a.stop_ns*1e-9)
