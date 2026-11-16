"""Bounded native controls and full-RC DC diagnostics for alternative solvers."""
import json, os, time
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from resources import lease, identity
from compiled_charge_v2 import execute


def run():
    base=ROOT/'build/signoff400'; source=base/'selected_seeded_full_RC_DC_1825'
    record=json.loads((source/'assessment.json').read_text())
    verify(record['input_sha256']); verify(record['artifacts'])
    binary=ROOT/'build/tools/xyce_metis_ordering_1790/Xyce'
    if record['input_sha256'][str(binary)]!=sha(binary): raise ValueError('checked binary required')
    out=base/'selected_RC_alternative_solvers_1829';out.mkdir(exist_ok=False)
    pins={str(p):sha(p) for p in [binary,source/'assessment.json',source/'smoke.spice',Path(__file__).resolve()]}
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1500
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    save(out/'inputs.json',dict(input_sha256=pins,solvers=['basker','klu2'],threads=4,per_full_case_cap_s=600,
         memory_GiB=64,automatic_identical_retry=False,release_ready=False))
    results=[]
    with lease(4,64,deadline):
        os.sched_setaffinity(0,{20,21,22,23})
        os.environ.update(OMP_NUM_THREADS='4',OMP_THREAD_LIMIT='4',OPENBLAS_NUM_THREADS='4')
        for solver in ['basker','klu2']:
            case=out/solver;case.mkdir()
            control=case/'control.spice'
            control.write_text('Alternative solver divider control\nV1 a 0 1\nR1 a b 1k\nR2 b 0 1k\n.dc V1 1 1 1\n.print dc format=csv precision=17 file='+str(case/'control.csv')+' v(a) v(b)\n.end\n')
            save(out/'status.json',dict(state='native_solver_control',solver=solver))
            try:
                execute([binary,'-a','-linsolv',solver,control],case/'control.log',min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+60),4)
                import csv
                rows=list(csv.reader((case/'control.csv').open()))
                values=[float(x) for x in rows[-1]]
                if abs(values[-1]-.5)>1e-12 or abs(values[-2]-1)>1e-12:raise ValueError('divider mismatch')
                deck=case/'full.spice'
                text=(source/'smoke.spice').read_text().replace(str(source/'dc.csv'),str(case/'dc.csv'))
                deck.write_text(text)
                save(out/'status.json',dict(state='full_RC_DC_diagnostic',solver=solver))
                start=time.monotonic()
                try:
                    execute([binary,'-a','-linsolv',solver,deck],case/'native.log',min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+600),64)
                    status='normal_exit_requires_completed_result_review'
                except (TimeoutError,RuntimeError) as error:status=repr(error)
                results.append(dict(solver=solver,control_pass=True,elapsed_s=time.monotonic()-start,status=status))
            except (TimeoutError,RuntimeError,ValueError) as error:
                results.append(dict(solver=solver,control_pass=False,status=repr(error)))
            save(out/'results.json',results)
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,results=results,release_ready=False,simulation_qualified=False))
    save(out/'status.json',dict(state='bounded_solver_comparison_complete'))

if __name__=='__main__':run()
