"""Run a final capture grid with scope and counts derived from verified point results."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import time
from common_v3 import save, sha, verify
from compiled_charge import execute
from resources import identity
from audit_prototype_final_campaign_coverage import LOADS
from itertools import product


def run(extraction, kind, output):
    if kind!='aperture':raise ValueError('supported capture grid required')
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    worker=Path(__file__).with_name('run_prototype_final_capture_aperture_point.py').resolve()
    reviewer=Path(__file__).with_name('review_prototype_capture_point_v6.py').resolve()
    source=extraction/'assessment.json';r=json.loads(source.read_text());verify(r['artifacts'])
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
                                 automatic_identical_retry=False))
    pins={str(p):sha(p) for p in (source,worker,reviewer,Path(__file__).resolve(),
          Path(__file__).with_name('audit_prototype_final_campaign_coverage.py'))}
    points=sorted(product(('tt','ff','ss','sf','fs'),('dfrtp_1','dfstp_1'),(20,200,2000),(20,200,400)))
    save(output/'status.json',dict(state='native_capture_campaign_running',grid=kind,
                                  planned_operating_points=len(points),release_ready=False))
    def point(case):
        c,m,d,k=case;name=f'{c}_{m}_d{d}_c{k}';where=output/name
        execute([sys.executable,worker,'--extraction',extraction,'--output',where,
                 '--corner',c,'--master',m,'--load-ff',str(LOADS[m]),
                 '--data-ramp-ps',str(d),'--clock-ramp-ps',str(k)],output/(name+'.log'),deadline,4)
        receipt=where/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        if (a['corner'],a['master'],a['input_full_ramp_ps'],a['clock_full_ramp_ps'],a['load_fF'],a['cases'])!=(c,'sky130_fd_sc_hs__'+m,d,k,LOADS[m],39):
            raise ValueError('native point scope differs from plan')
        if a['input_sha256'].get(str(worker))!=pins[str(worker)] or a['input_sha256'].get(str(source))!=pins[str(source)]:
            raise ValueError('native source lineage mismatch')
        review=output/(name+'_review')
        execute([sys.executable,reviewer,'--point',where,'--output',review],output/(name+'_review.log'),deadline,4)
        reviewed=json.loads((review/'assessment.json').read_text())
        if reviewed['reviewed_native_cases']!=a['cases']:raise ValueError('native review scope differs')
        return dict(corner=c,master=m,load_fF=a['load_fF'],data_ramp_ps=d,clock_ramp_ps=k,
             directory=str(where),assessment_sha256=sha(receipt),native_cases=a['cases'],
             review_directory=str(review),review_sha256=sha(review/'assessment.json'),
             unresolved_or_glitching_cases=reviewed['unresolved_or_glitching_cases'])
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:records=list(pool.map(point,points))
        summary=dict(native_cases=sum(x['native_cases'] for x in records),operating_points=len(records),masters=sorted({x['master'] for x in records}),corners=sorted({x['corner'] for x in records}))
        for row in records:
            for directory,digest in ((row['directory'],row['assessment_sha256']),(row['review_directory'],row['review_sha256'])):
                p=Path(directory)/'assessment.json'
                if sha(p)!=digest:raise ValueError('point receipt changed during campaign')
                pins[str(p)]=digest
        verify(pins);detail=output/'points.json';save(detail,records)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},**summary,
             grid=kind,all_fixture_and_pretest_waveforms_valid=True,
             unresolved_or_glitching_cases=sum(x['unresolved_or_glitching_cases'] for x in records),
             load_is_qualified_route_bound=False,numerical_uncertainty_bounded=False,
             constraints_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='native_capture_campaign_complete',**summary,release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(error),release_ready=False))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--extraction',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--grid',choices=('aperture',),required=True)
    a=p.parse_args();run(a.extraction.resolve(),a.grid,a.output.resolve())
