"""Validate zero-charge UIC startup on an analytical floating signed-C divider."""
import csv,json,math,os,time,struct
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha,verify
from compiled_charge_v2 import execute
from resources import lease
from capture_selected_native_runtime import closure

def run():
    out=ROOT/'build/signoff400/selected_PDK_floating_C_startup_1807';out.mkdir(exist_ok=False)
    binary=ROOT/'build/tools/xyce_linear_trace_1786/Xyce';build=ROOT/'build/tools/xyce_CSC_capture_1794/assessment.json';r=json.loads(build.read_text());verify(r['input_sha256']);verify(r['artifacts']);shim=build.parent/'capture_symbolic.so'
    pdk,_=closure(os.getpid(),'/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice')
    pins={**pdk,**{str(p):sha(p)for p in [binary,build,shim,Path(__file__).resolve()]}};deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+120
    with lease(1,4,deadline):
        for label in ['transient','capture']:
            p=out/label;p.mkdir();deck=p/'startup.spice';data=p/'transient.csv'
            deck.write_text('* Initially uncharged floating capacitor divider\n.lib "/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice" tt\n.options parser model_binning=true\n.options device temp=27\nV1 a 0 PWL(0 0 100p 1 200p 1)\nC1 a f 1e-18\nC2 f 0 4e-18\nC3 f 0 -1e-18\n.model dm D (IS=1e-14 N=1)\nD1 a 0 dm\n.options topology outputnamesfile=1\n.tran 1p 200p 0 10p UIC\n.print tran format=csv precision=17 file='+str(data)+' v(a) v(f)\n.end\n')
            os.chdir(p);command=[binary,'-a','-linsolv','umfpack_reuse',deck.name]
            if label=='capture':command=['/usr/bin/env','LD_PRELOAD='+str(shim),'OPENPLL_CSC_CAPTURE='+str(p/'matrix'),*command]
            execute(command,p/'native.log',deadline,4)
    rows=list(csv.DictReader((out/'transient/transient.csv').read_text().splitlines()));values=[]
    for row in rows:
        if not row.get('TIME') or row['TIME'].startswith('End'):continue
        t,a,f=[float(row[k])for k in ['TIME','V(A)','V(F)']]
        if not all(math.isfinite(v)for v in [t,a,f]) or abs(4*f-a)>1e-12:raise ValueError('floating charge relation changed')
        values.append((t,a,f))
    if not values or abs(values[-1][0]-200e-12)>1e-22 or abs(values[-1][1]-1)>1e-12:raise ValueError('complete supply-ramp transient required')
    p=out/'capture/matrix';magic,n,m,nnz=struct.unpack('=4Q',(p/'header.u64').read_bytes());ai=np.fromfile(p/'rows.i32',dtype=np.int32);ax=np.fromfile(p/'values.f64',dtype=np.float64)
    if magic!=0x4f504c4c43534331 or n!=m or len(ai)!=nnz or not np.all(np.bincount(ai[ax!=0],minlength=n)>0):raise ValueError('transient Jacobian has empty row')
    done=json.loads((p/'completion.json').read_text())
    if not done['exact_binary_CSC_capture_complete']:raise ValueError('normal capture completion required')
    verify(pins);save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in out.rglob('*')if p.is_file()},normal_native_transient_completed=True,analytical_floating_charge_relation_verified=True,first_transient_matrix_has_no_zero_rows=True,initial_state='zero capacitor voltage/charge; source ramp from zero',no_artificial_resistors=True,no_physical_connections_added=True,full_PLL_qualified=False,release_ready=False))
if __name__=='__main__':run()
