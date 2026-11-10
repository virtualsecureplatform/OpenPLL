"""Bind completed native zero rows to exported nodes and classify their connections."""
import json,struct,time
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease

def arrays(p):
    magic,n,m,nnz=struct.unpack('=4Q',(p/'header.u64').read_bytes())
    if magic!=0x4f504c4c43534331 or n!=m:raise ValueError('square native CSC required')
    ap=np.fromfile(p/'columns.i32',dtype=np.int32);ai=np.fromfile(p/'rows.i32',dtype=np.int32);ax=np.fromfile(p/'values.f64',dtype=np.float64)
    if len(ap)!=n+1 or len(ai)!=nnz or len(ax)!=nnz or ap[-1]!=nnz:raise ValueError('CSC dimensions differ')
    return n,ap,ai,ax

def names(path,n):
    result={}
    for line in path.read_text().splitlines()[1:]:
        f=line.split()
        if len(f)!=2:raise ValueError('one index/name required')
        i=int(f[0])
        if i in result:raise ValueError('duplicate index')
        result[i]=f[1].lower()
    if set(result)!=set(range(n)) or len(set(result.values()))!=n:raise ValueError('complete unique name population required')
    return result

def run():
    base=ROOT/'build/signoff400';source=base/'selected_full_RC_CSC_capture_1800';receipt=source/'assessment.json';r=json.loads(receipt.read_text())
    o=json.loads((source/'native.process.json').read_text())
    if identity(o['pid'])==o['birth'] or not r['native_diagnostic_completed']:raise ValueError('completed named capture required')
    verify(r['input_sha256']);verify(r['artifacts'])
    previous=base/'selected_full_RC_CSC_capture_1797/assessment.json';pr=json.loads(previous.read_text());verify(pr['artifacts'])
    for name in ['header.u64','columns.i32','rows.i32','values.f64']:
        if sha(source/'matrix'/name)!=pr['artifacts'][str(previous.parent/'matrix'/name)]:raise ValueError('name export changed captured matrix')
    control=base/'selected_CSC_capture_control_1799/assessment.json';cr=json.loads(control.read_text());verify(cr['input_sha256']);verify(cr['artifacts'])
    cn,cp,ci,cx=arrays(control.parent/'capture/matrix');labels=names(control.parent/'capture/namesMap_deck.spice.txt',cn)
    expected={('a','a'):1.,('a','b'):-1.,('b','a'):-1.,('b','b'):2.,('a','v1_branch'):1.,('v1_branch','a'):1.}
    observed={(labels[int(ci[k])],labels[j]):float(cx[k])for j in range(cn)for k in range(cp[j],cp[j+1])if cx[k]!=0}
    if observed!=expected:raise ValueError('native index convention failed analytical MNA check')
    model=base/'selected_reference_alias_native_RC_model_1768';mr=json.loads((model/'assessment.json').read_text());verify(mr['artifacts'])
    pins={str(p):sha(p)for p in [receipt,previous,control,model/'assessment.json',Path(__file__).resolve()]}
    out=base/'selected_zero_RC_row_mapping_1801';out.mkdir(exist_ok=False)
    with lease(1,12,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        n,ap,ai,ax=arrays(source/'matrix');label=names(source/'namesMap_capture.spice.txt',n);nz=ax!=0
        row=np.bincount(ai[nz],minlength=n);col=np.repeat(np.arange(n,dtype=np.int32),np.diff(ap));columns=np.bincount(col[nz],minlength=n)
        zero=np.flatnonzero(row==0)
        if not np.array_equal(zero,np.flatnonzero(columns==0)):raise ValueError('zero row and column populations differ')
        caps=set();resistors=set();devices=set();roles=defaultdict(set);templates={};active=None
        for line in (model/'model.spice').read_text().splitlines():
            f=line.lower().split()
            if not f or f[0].startswith('*'):continue
            if f[0]=='.subckt':active=f[1];continue
            if f[0]=='.ends':active=None;continue
            if active and active.startswith('__openpll_literal_leaf_') and f[0]=='xdevice':
                if any('nfet' in t or 'pfet' in t for t in f):templates[active]=['drain','gate','source','bulk']
                else:templates[active]=['passive']*(len(f)-2)
            if f[0].startswith('xflat'):
                nodes=f[1:-1];devices.update(nodes)
                role=templates.get(f[-1],['passive']*len(nodes))
                for node,rname in zip(nodes,role):roles[node].add(rname)
            elif active and not active.startswith('__openpll_'):
                if f[0].startswith('c'):caps.update(f[1:3])
                elif f[0].startswith('r'):resistors.update(f[1:3])
        counts=Counter();examples=defaultdict(list)
        inverse={v.lower():k for k,v in json.loads((model/'nodes.json').read_text()).items()}
        for i in zero:
            full=label[int(i)];node=full.removeprefix('xdut:')
            if node in caps and node not in resistors and node not in devices:category='C_only'
            elif node in resistors:category='resistor_terminal'
            elif node in devices:category='device_'+','.join(sorted(roles[node]))
            elif node in caps:category='C_other'
            else:category='unmapped_or_internal'
            counts[category]+=1
            if len(examples[category])<10:examples[category].append(dict(index=int(i),native_name=full,original_name=inverse.get(node)))
        save(out/'report.json',dict(unknowns=n,zero_rows=len(zero),categories=dict(counts),examples=dict(examples),matrix_bytes_unchanged_by_names_export=True,analytical_named_MNA_binding_pass=True,matrix_modified=False,simulation_solved=False))
        verify(pins);save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(out/'report.json'):sha(out/'report.json')},completed_named_zero_rows_classified=True,RC_backend_qualified=False,release_ready=False))
if __name__=='__main__':run()
