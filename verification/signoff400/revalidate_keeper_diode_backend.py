"""Recheck sampled diode controls using the current backend and pinned native references."""
import argparse,json,os,shutil,sys,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute

def run(output):
    base=ROOT/'build/signoff400';old=base/'prototype_v3_diode_charge_fix_controls_026';review=old/'completed_review.json';a=json.loads(review.read_text());verify(a['input_sha256'])
    smoke=base/'selected_keeper_flat_native_smoke_1210';receipt=smoke/'assessment.json';s=json.loads(receipt.read_text());verify(s['input_sha256']);verify(s['artifacts'])
    if not a['all_comparison_screens_passed'] or a['temperature_c']!=27:raise ValueError('completed five-corner 27 C references required')
    model=smoke/'backend_model.spice';text=model.read_text();end='.ends __openpll_xyce_pw2nd';fragment=text[:text.index(end)+len(end)]
    expected={f'{c}_a{g}'for c in ['tt','ff','ss','sf','fs']for g in ['0.4347','0.6417']}
    cases=sorted(p for p in old.glob('*_a*')if p.is_dir())
    if {p.name for p in cases}!=expected:raise ValueError('all ten geometry/corner controls required')
    for folder in cases:
        for deck in folder.glob('xy_*.spice'):
            t=deck.read_text();start=t.index('* Diagnostic translation, fixed at 27 C;');stop=t.index(end)+len(end)
            if t[start:stop]!=fragment.rstrip():raise ValueError('backend diode model/wrapper differs from reference control')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';checker=output/'review_completed.py';shutil.copy2(old/'review_completed.py',checker)
    pins={**s['input_sha256'],str(review):sha(review),str(model):sha(model),str(receipt):sha(receipt),str(binary):sha(binary),str(checker):sha(checker),str(Path(__file__).resolve()):sha(Path(__file__).resolve())};runs=0
    for folder in cases:
        target=output/folder.name;target.mkdir()
        for path in [*folder.glob('ng_*.tsv'),*folder.glob('xy_*.spice')]:
            pins[str(path)]=a['input_sha256'][str(path)];dest=target/path.name;shutil.copy2(path,dest);pins[str(dest)]=sha(dest)
    verify(pins);save(output/'inputs.json',dict(input_sha256=pins,reference='previous completed corrected-ngspice controls, unchanged',candidate_backend=str(binary),CPU=28,memory_GiB=2,native_cap_s=1800,maximum_native_cases=50,automatic_identical_retry=False,model_fragment_exactly_matches_current_keeper_backend=True,release_ready=False))
    try:
        with lease(1,2,deadline):
            for folder in cases:
                target=output/folder.name
                for name in ['xy_dc','xy_ac_0','xy_ac_0.9','xy_ac_1.8','xy_tran']:
                    save(output/'status.json',dict(state='rechecking_current_backend_diode',case=folder.name,analysis=name,completed_native_cases=runs,release_ready=False));execute([binary,'-linsolv','umfpack_reuse','-o',target/name,target/(name+'.spice')],target/(name+'.log'),deadline,2);runs+=1
            execute([sys.executable,checker],output/'review.log',deadline,2)
        verify(pins);result=json.loads((output/'completed_review.json').read_text())
        if len(result['results'])!=10 or not result['all_comparison_screens_passed']:raise ValueError('current executable failed retained diode comparison limits')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'completed_review.json'):sha(output/'completed_review.json'),str(output/'review.log'):sha(output/'review.log')},completed_native_cases=runs,all_ten_geometry_corner_comparison_screens_passed=True,current_backend_model_fragment_exactly_matches=True,noise_qualified=False,full_PLL_model_qualified=False,release_ready=False));save(output/'status.json',dict(state='current_backend_diode_controls_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),automatic_identical_retry=False,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
