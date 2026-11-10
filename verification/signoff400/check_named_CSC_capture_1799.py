"""Check exact capture against an analytical MNA matrix and pass-through DC output."""
import itertools,json,os,struct,time,subprocess
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from compiled_charge_v2 import execute
from resources import lease

def run():
    out=ROOT/'build/signoff400/selected_CSC_capture_control_1799';out.mkdir(exist_ok=False)
    build=ROOT/'build/tools/xyce_CSC_capture_1794/assessment.json';r=json.loads(build.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    shim=build.parent/'capture_symbolic.so';binary=ROOT/'build/tools/xyce_umfpack_BSIM_junction_1292/Xyce';deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+60
    pins={str(p):sha(p)for p in [build,shim,binary,Path(__file__).resolve()]};outputs=[]
    with lease(1,4,deadline):
        for label in ['base','passthrough','capture']:
            folder=out/label;folder.mkdir();deck=folder/'deck.spice';data=folder/'dc.csv'
            deck.write_text(f'* Exact MNA control\nV1 a 0 1\nR1 a b 1\nR2 b 0 1\n.options topology outputnamesfile=1\n.dc V1 1 1 1\n.print dc format=csv precision=17 file={data} v(a) v(b)\n.end\n')
            os.chdir(folder)
            command=[str(binary),'-a','-linsolv','umfpack_reuse',deck.name]
            if label!='base':command=['/usr/bin/env','LD_PRELOAD='+str(shim),*command]
            if label=='capture':command=command[:2]+['OPENPLL_CSC_CAPTURE='+str(folder/'matrix')]+command[2:]
            execute(command,folder/'native.log',deadline,4)
            if label!='capture':outputs.append(data.read_text())
    p=out/'capture/matrix';done=json.loads((p/'completion.json').read_text());header=struct.unpack('=4Q',(p/'header.u64').read_bytes());_,nr,nc,nnz=header
    if header[0]!=0x4f504c4c43534331 or nr!=nc or nr!=3:raise ValueError('unexpected control matrix dimensions')
    ap=struct.unpack('='+str(nc+1)+'i',(p/'columns.i32').read_bytes());ai=struct.unpack('='+str(nnz)+'i',(p/'rows.i32').read_bytes());ax=struct.unpack('='+str(nnz)+'d',(p/'values.f64').read_bytes());matrix=[[0.]*3 for _ in range(3)]
    for c in range(nc):
        for k in range(ap[c],ap[c+1]):matrix[ai[k]][c]=ax[k]
    expected=[[1.,-1.,1.],[-1.,2.,0.],[1.,0.,0.]]
    if not any(all(matrix[i][j]==expected[q[i]][q[j]]for i in range(3)for j in range(3))for q in itertools.permutations(range(3))):raise ValueError('captured matrix differs from exact resistor/source MNA')
    if outputs[0]!=outputs[1] or not done['exact_binary_CSC_capture_complete'] or done['simulation_solved']:raise ValueError('pass-through or capture mode differs')
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in out.rglob('*')if p.is_file()},exact_analytical_MNA_capture=True,pass_through_DC_unchanged=True,capture_is_not_a_simulation_result=True,release_ready=False))
if __name__=='__main__':run()
