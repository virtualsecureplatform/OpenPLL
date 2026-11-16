"""Check restored reuse context against fresh solves and analytical RC response."""
import csv,json,math,os,re,time
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge_v2 import execute
from pathlib import Path


def run():
    base=ROOT/'build/tools/xyce_metis_ordering_1790/Xyce'
    fixed=ROOT/'build/tools/xyce_reuse_context_1830/Xyce'
    receipt=fixed.parent/'assessment.json';r=json.loads(receipt.read_text())
    verify(r['input_sha256']);verify(r['artifacts'])
    if not r['restored_transient_context_hook']:raise ValueError('restored hook required')
    out=ROOT/'build/signoff400/selected_reuse_context_control_1831';out.mkdir(exist_ok=False)
    pins={str(p):sha(p)for p in [base,fixed,receipt,Path(__file__).resolve()]}
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+180
    results={}
    os.sched_setaffinity(0,{24});os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1')
    with lease(1,4,deadline):
        for kind in ['dc','tran']:
            for label,binary in [('base',base),('fixed',fixed)]:
                p=out/(kind+'_'+label);p.mkdir();data=p/'values.csv';deck=p/'control.spice'
                lines=['RC reuse context control','V1 a 0 PWL(0 0 1n 0 1.01n 1 20n 1)','R1 a b 1k','C1 b 0 1p']
                lines+=['.dc V1 1 1 1'] if kind=='dc' else ['.tran 10p 20n 0 10p']
                lines += [f'.print {kind} format=csv precision=17 file={data} v(b)','.end']
                deck.write_text('\n'.join(lines)+'\n')
                execute([binary,'-a','-linsolv','umfpack_reuse',deck],p/'native.log',deadline,4)
                log=(p/'native.log').read_text()
                if 'End of Xyce(TM) Simulation' not in log:raise ValueError('normal footer required')
                m=re.search(r'OpenPLL UMFPACK adapter:.*',log)
                if not m:raise ValueError('solver summary required')
                counts={k:int(v)for k,v in re.findall(r'(\w+)=(\d+)',m[0])}
                rows=[]
                for row in csv.reader(data.read_text().splitlines()):
                    try:values=[float(x)for x in row]
                    except ValueError:continue
                    if not all(math.isfinite(v)for v in values):raise ValueError('nonfinite output')
                    rows.append(values)
                if not rows:raise ValueError('missing output')
                if kind=='dc' and (abs(rows[-1][-1]-1)>1e-12 or counts['reuse_attempts']!=0 or counts['DC_reuse']!=0):raise ValueError('DC must not use transient reuse')
                if kind=='tran':
                    if rows[-1][0]<20e-9:raise ValueError('endpoint missing')
                    # Exact response to the 10 ps linear ramp, evaluated after ramp end.
                    for t,v in rows:
                        if t>=1.01e-9:
                            expected=1-(1e-9/1e-11)*math.expm1(1e-11/1e-9)*math.exp(-(t-1e-9)/1e-9)
                            if abs(v-expected)>2e-4:raise ValueError('analytical RC response mismatch')
                    if label=='fixed' and counts['exact_reuse']==0:raise ValueError('transient reuse never activated')
                results[kind+'_'+label]=dict(counts=counts,rows=rows)
        a=results['tran_base']['rows'];b=results['tran_fixed']['rows']
        if len(a)!=len(b) or any(abs(x-y)>1e-10 for ar,br in zip(a,b)for x,y in zip(ar,br)):raise ValueError('reference waveform mismatch')
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,results={k:v['counts']for k,v in results.items()},
         analytical_RC_pass=True,reference_waveforms_match=True,DC_reuse_excluded=True,
         transient_exact_reuse_activated=True,nonlinear_reuse_qualified=False,release_ready=False))

if __name__=='__main__':run()
