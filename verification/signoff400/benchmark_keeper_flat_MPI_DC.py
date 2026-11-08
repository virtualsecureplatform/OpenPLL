"""One bounded four-rank scaling comparison against an existing reset DC reference."""
import argparse,csv,json,math,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from compiled_charge_v2 import execute
from resources import lease,identity

def point(path):
    rows=list(csv.reader(path.read_text().splitlines())); headers=rows[0]
    data=[r for r in rows[1:] if r and not r[0].startswith('End of')]
    if len(data)!=1 or len(data[0])!=len(headers):raise ValueError('one complete DC point required')
    values={k:float(v) for k,v in zip(headers,data[0])}
    if not all(math.isfinite(v) for v in values.values()):raise ValueError('finite DC point required')
    return values

def run(reference,output):
    receipt=reference/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if not a['normal_native_exit']:raise ValueError('completed native baseline required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24,25,26,27});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+900
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    deck=output/'smoke.spice';data=output/'dc.csv';original=reference/'smoke.spice'
    text=original.read_text();old=str(reference/'dc.csv')
    if text.count(old)!=1:raise ValueError('unique output path substitution required')
    deck.write_text(text.replace(old,str(data)))
    binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';mpi=Path('/usr/bin/mpirun')
    files=[receipt,original,reference/'dc.csv',deck,binary,mpi,Path(__file__).resolve(),Path(__file__).with_name('compiled_charge_v2.py')]
    pins={**a['input_sha256'],**{str(p):sha(p) for p in files}};verify(pins)
    command=[mpi,'--bind-to','core','--map-by','core','-np','4',binary,'-a','-linsolv','umfpack_reuse',deck]
    save(output/'inputs.json',dict(input_sha256=pins,command=list(map(str,command)),ranks=4,CPU_set=[24,25,26,27],memory_GiB=64,native_cap_s=900,maximum_native_cases=1,automatic_identical_retry=False,only_deck_change='output filename',release_ready=False))
    save(output/'status.json',dict(state='four_rank_reset_DC_running',release_ready=False))
    try:
        start=time.monotonic()
        with lease(4,64,deadline):execute(command,output/'native.log',deadline,64)
        elapsed=time.monotonic()-start;verify(pins);baseline=point(reference/'dc.csv');observed=point(data)
        if baseline.keys()!=observed.keys():raise ValueError('same output columns required')
        differences={k:abs(observed[k]-baseline[k]) for k in observed};maximum=max(differences.values())
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [deck,data,output/'native.log']},normal_native_exit=True,baseline_elapsed_s=a['elapsed_s'],four_rank_elapsed_s=elapsed,DC_wall_speedup=a['elapsed_s']/elapsed,maximum_output_absolute_difference=maximum,outputs_agree_within_1e_8=maximum<=1e-8,differences=differences,transient_scaling_measured=False,model_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='four_rank_reset_DC_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_scaling_result',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.reference.resolve(),a.output.resolve())
