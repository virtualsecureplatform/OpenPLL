"""Complete the missing final dfstp_2 capture grid, preserving the existing pilot."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time
from common_v3 import save, sha, verify
from compiled_charge import execute


def run(extraction, pilot, output):
    worker=Path(__file__).with_name('run_prototype_final_capture_slew_point.py').resolve()
    reviewer=Path(__file__).with_name('review_prototype_capture_point_v4.py').resolve()
    output.mkdir(parents=True,exist_ok=False)
    pins={str(p):sha(p) for p in (extraction/'assessment.json',worker,reviewer,Path(__file__).resolve())}
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    points=[(c,d,k) for c in ('tt','ff','ss','sf','fs') for d in (200,2000) for k in (200,400)]
    save(output/'status.json',dict(state='final_capture_supplement_running',grids=20,release_ready=False))
    def point(case):
        c,d,k=case;name=f'{c}_d{d}_c{k}'
        reuse=case==('tt',2000,400)
        where=pilot if reuse else output/name
        if not reuse:
            execute([sys.executable,worker,'--extraction',extraction,'--output',where,
                     '--corner',c,'--master','dfstp_2','--load-ff','250',
                     '--data-ramp-ps',str(d),'--clock-ramp-ps',str(k)],output/(name+'.log'),deadline,4)
        receipt=where/'assessment.json'
        # A live pilot is observed by its owning turn; it must be terminal
        # before starting this supplement. Never retry or overwrite it here.
        r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if (r['corner'],r['master'],r['input_full_ramp_ps'],r['clock_full_ramp_ps'],r['load_fF'],r['cases'])!=(c,'sky130_fd_sc_hs__dfstp_2',d,k,250,30):
            raise ValueError('supplement point mismatch')
        if r['input_sha256'].get(str(worker))!=pins[str(worker)] or r['input_sha256'].get(str(extraction/'assessment.json'))!=pins[str(extraction/'assessment.json')]:
            raise ValueError('supplement source/worker mismatch')
        review=output/(name+'_review')
        execute([sys.executable,reviewer,'--point',where,'--output',review],output/(name+'_review.log'),deadline,4)
        reviewed=json.loads((review/'assessment.json').read_text())
        return dict(corner=c,data_ramp_ps=d,clock_ramp_ps=k,directory=str(where),
                    assessment_sha256=sha(receipt),reused=reuse,review_directory=str(review),
                    review_sha256=sha(review/'assessment.json'),
                    unresolved_or_glitching_cases=reviewed['unresolved_or_glitching_cases'])
    with ThreadPoolExecutor(max_workers=4) as pool: records=list(pool.map(point,points))
    for row in records:
        for directory,digest in ((row['directory'],row['assessment_sha256']),(row['review_directory'],row['review_sha256'])):
            p=Path(directory)/'assessment.json'
            if sha(p)!=digest:raise ValueError('point changed during supplement')
            pins[str(p)]=digest
    detail=output/'points.json';save(detail,records);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         master='sky130_fd_sc_hs__dfstp_2',complete_five_corner_slew_rectangle_grids=20,native_cases=600,
         all_fixture_and_pretest_waveforms_valid=True,
         unresolved_or_glitching_cases=sum(r['unresolved_or_glitching_cases'] for r in records),
         characterized_output_load_fF=250,load_is_qualified_route_bound=False,
         numerical_uncertainty_bounded=False,constraints_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='final_capture_supplement_complete',grids=20,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('extraction','pilot','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.extraction.resolve(),a.pilot.resolve(),a.output.resolve())
