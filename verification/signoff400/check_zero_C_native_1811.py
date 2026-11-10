"""Native check: zero-C comments remove only an empty equation, preserving MNA."""
import json,time,os,struct,csv
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha,verify
from compiled_charge_v2 import execute
from resources import lease
from zero_C_placeholders_1809 import adapt

def read(p):
    _,n,m,nnz=struct.unpack('=4Q',(p/'matrix/header.u64').read_bytes());ap=np.fromfile(p/'matrix/columns.i32',dtype=np.int32);ai=np.fromfile(p/'matrix/rows.i32',dtype=np.int32);ax=np.fromfile(p/'matrix/values.f64',dtype=np.float64)
    labels={int(f[0]):f[1]for line in (p/'namesMap_deck.spice.txt').read_text().splitlines()[1:]if (f:=line.split())}
    result={(labels[int(ai[k])],labels[j]):float(ax[k])for j in range(n)for k in range(ap[j],ap[j+1])if ax[k]!=0}
    return n,labels,result

def run():
    out=ROOT/'build/signoff400/selected_zero_C_native_control_1811';out.mkdir(exist_ok=False)
    binary=ROOT/'build/tools/xyce_umfpack_BSIM_junction_1292/Xyce';build=ROOT/'build/tools/xyce_CSC_capture_1794/assessment.json';r=json.loads(build.read_text());verify(r['artifacts']);shim=build.parent/'capture_symbolic.so'
    pins={str(p):sha(p)for p in [binary,build,shim,Path(__file__).resolve(),Path(__file__).with_name('zero_C_placeholders_1809.py')]};deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+120
    body='V1 a 0 1\nR1 a b 1\nR2 b 0 1\nC0 unused a -0e-99\nC1 a b 1e-300\nCn a b -1e-18\n.options topology outputnamesfile=1\n.dc V1 1 1 1\n'
    with lease(1,4,deadline):
        for label in ['original','adapted','solve']:
            p=out/label;p.mkdir();deck=p/'deck.spice';text='* Exact zero-C backend control\n'+body+f'.print dc format=csv precision=17 file={p/"dc.csv"} v(a) v(b)\n.end\n'
            if label!='original':text,_=adapt(text)
            deck.write_text(text);os.chdir(p);command=[binary,'-a','-linsolv','umfpack_reuse',deck.name]
            if label!='solve':command=['/usr/bin/env','LD_PRELOAD='+str(shim),'OPENPLL_CSC_CAPTURE='+str(p/'matrix'),*command]
            execute(command,p/'native.log',deadline,4)
    n1,labels1,a=read(out/'original');n2,labels2,b=read(out/'adapted')
    if n1!=4 or n2!=3 or a!=b or 'unused' not in labels1.values()or 'unused' in labels2.values():raise ValueError('adapter changed participating native MNA')
    rows=list(csv.reader((out/'solve/dc.csv').read_text().splitlines()));values=list(map(float,rows[1]))
    if rows[0]!=['V(A)','V(B)'] or values!=[1,.5]:raise ValueError('normal analytical DC result required')
    verify(pins);save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in out.rglob('*')if p.is_file()},native_nonzero_MNA_entries_exactly_equal=True,only_zero_C_empty_unknown_removed=True,analytical_DC_completed=True,finite_and_signed_C_lines_unchanged=True,all_R_unchanged=True,full_PLL_qualified=False,release_ready=False))
if __name__=='__main__':run()
