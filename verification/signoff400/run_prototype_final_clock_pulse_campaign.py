"""Observe final loaded FF pulse capture at fast and slow clock slew endpoints."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time
from common_v3 import save, sha, verify
from compiled_charge import execute


def run(extraction, output):
    worker=Path(__file__).with_name('run_prototype_final_clock_pulse_point.py').resolve()
    output.mkdir(parents=True,exist_ok=False)
    pins={str(p):sha(p) for p in (extraction/'assessment.json',worker,Path(__file__).resolve())}
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    loads={'dfrtp_1':250,'dfrtp_2':400,'dfrtp_4':600,'dfstp_1':125,'dfstp_2':400}
    points=[(c,m,load,k) for c in ('tt','ff','ss','sf','fs') for m,load in loads.items() for k in (20,400)]
    save(output/'status.json',dict(state='final_capture_supplement_running',grids=50,release_ready=False))
    def point(case):
        c,m,load,k=case;name=f'{c}_{m}_c{k}'
        where=output/name
        execute([sys.executable,worker,'--extraction',extraction,'--output',where,
                 '--corner',c,'--master',m,'--clock-ramp-ps',str(k)],output/(name+'.log'),deadline,4)
        receipt=where/'assessment.json'
        r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if (r['corner'],r['master'],r['clock_full_ramp_ps'],r['load_fF'],r['cases'])!=(c,'sky130_fd_sc_hs__'+m,k,load,8):
            raise ValueError('supplement point mismatch')
        if r['input_sha256'].get(str(worker))!=pins[str(worker)] or r['input_sha256'].get(str(extraction/'assessment.json'))!=pins[str(extraction/'assessment.json')]:
            raise ValueError('supplement source/worker mismatch')
        return dict(corner=c,master=m,load_fF=load,clock_ramp_ps=k,directory=str(where),
                    assessment_sha256=sha(receipt),all_grid_captures_verified=r['all_grid_captures_verified'])
    with ThreadPoolExecutor(max_workers=4) as pool: records=list(pool.map(point,points))
    for row in records:
        for directory,digest in ((row['directory'],row['assessment_sha256']),):
            p=Path(directory)/'assessment.json'
            if sha(p)!=digest:raise ValueError('point changed during supplement')
            pins[str(p)]=digest
    detail=output/'points.json';save(detail,records);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         master='sky130_fd_sc_hs__dfstp_2',complete_five_corner_slew_rectangle_grids=50,native_cases=600,
         all_grid_captures_verified=all(r['all_grid_captures_verified'] for r in records),
         load_is_qualified_route_bound=False,
         numerical_uncertainty_bounded=False,constraints_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='final_capture_supplement_complete',grids=50,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('extraction','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.extraction.resolve(),a.output.resolve())
