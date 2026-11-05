#!/usr/bin/env python3
"""Audit completed native wave comparisons, fixture identity and metadata mapping."""
import json,math
from pathlib import Path
import numpy as np
from compile_local_C_operators_v2 import digest,save

root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
case=base/'wire_preconditioned_native_controls_004'
out=base/'wire_preconditioned_native_controls_checks_001';out.mkdir(exist_ok=False)
report=json.loads((case/'assessment.json').read_text());assert report['native_adapter_controls_passed']
for name,sha in {**report['input_sha256'],**report['artifacts']}.items():assert digest(Path(name))==sha,name
assert len(report['case_receipts'])==13 and all(r['native_exit']==0 for r in report['case_receipts'])
assert sum(bool(r.get('reused_completed_native_case')) for r in report['case_receipts'])==6

def names(path):
    rows=path.read_text().splitlines();assert rows[0]=='HEADER'
    pairs=[line.split() for line in rows[1:]]
    indices=[int(x[0]) for x in pairs];assert sorted(indices)==list(range(len(pairs)))
    d={int(i):name.upper() for i,name in pairs};return [d[i] for i in range(len(d))]

def metadata(path,variables,expected):
    with path.open('rb') as handle:
        assert handle.read(8)==b'OPLLCAP1'
        n,m=np.fromfile(handle,dtype='<i4',count=2);assert n==len(variables)
        row=np.fromfile(handle,dtype='<i4',count=n+1);col=np.fromfile(handle,dtype='<i4',count=m)
        val=np.fromfile(handle,dtype='<f8',count=m);keep=np.fromfile(handle,dtype='u1',count=m)
        sample=np.fromfile(handle,dtype='u1',count=m);assert not handle.read()
    assert row[0]==0 and row[-1]==m and np.all(np.diff(row)>=0)
    actual={}
    for i in range(n):
        for k in range(row[i],row[i+1]):
            key=(variables[i],variables[col[k]]);assert key not in actual
            actual[key]=(val[k],int(keep[k]),int(sample[k]))
    pairs={}
    for a,b,value,preserved in expected:
        for key in [(a,b),(b,a)]:pairs[key]=(value,preserved,1-preserved)
    assert actual.keys()==pairs.keys()
    for key,value in pairs.items():
        got=actual[key];assert math.isclose(got[0],value[0],rel_tol=1e-15) and got[1:]==value[1:]

full=names(case/'candidate.names');default=names(case/'default_candidate.names')
assert full==names(case/'stock.names') and default==names(case/'default_stock.names')
assert len(full)==len(default)==77 and sum('BODY' in name for name in full)==6
metadata(case/'wire_C.bin',full,[('A','B',1e-12,0),('A','INPUT',-20e-15,1),
    ('OUTPUT','INPUT',-5e-15,1),('MESH17','MESH45',-30e-15,0),('MESH0','MESH1',-7e-15,1)])
metadata(case/'wire_C_default.bin',default,[('A','B',1e-12,0)])

def wave(path):
    records=[];ended=False
    with path.open() as handle:
        assert handle.readline().split()==['Index','TIME','V(A)','V(B)','V(OUTPUT)','I(VDD)']
        for line in handle:
            fields=line.split()
            if fields and fields[0].isdigit():
                assert len(fields)==6 and int(fields[0])==len(records)
                records.append([float(v) for v in fields[1:]])
            elif 'End of Xyce(TM) Simulation' in line:ended=True
    a=np.array(records);assert ended and a.shape[1]==5 and np.isfinite(a).all()
    assert a[0,0]==0 and np.all(np.diff(a[:,0])>0) and a[-1,0]>=8e-9*(1-1e-8)
    return a

def edges(a):
    i=np.flatnonzero((a[:-1,3]<.9)&(a[1:,3]>=.9))
    return a[i,0]+(.9-a[i,3])*(a[i+1,0]-a[i,0])/(a[i+1,3]-a[i,3])

checks=[];grid=np.linspace(0,8e-9,8001)
for published in report['comparisons']:
    label=published['case'];variant=label.rsplit('_',1)[0]
    reference=case/(variant+'_stock.cir');candidate=case/(label+'.cir')
    assert reference.read_bytes()==candidate.read_bytes()
    text=candidate.read_text()
    assert ('METHOD=GEAR' in text)==variant.startswith('gear_')
    a=wave(Path(str(reference)+'.prn'));b=wave(Path(str(candidate)+'.prn'))
    difference=[float(np.max(abs(np.interp(grid,a[:,0],a[:,i])-np.interp(grid,b[:,0],b[:,i])))) for i in range(1,5)]
    first,second=edges(a),edges(b);assert len(first)==len(second) and len(first)>0
    edge=float(np.max(abs(first-second)))
    expected=published['voltage_differences_V']+[published['supply_current_difference_A']]
    assert np.allclose(difference,expected,rtol=1e-10,atol=1e-25)
    assert math.isclose(edge,published['rising_crossing_difference_s'],rel_tol=1e-9,abs_tol=1e-25)
    checks.append(dict(case=label,stock_samples=len(a),candidate_samples=len(b),
        independently_recomputed_voltage_difference_max_V=max(difference[:3]),rising_edge_error_s=edge))
linear=0
for published in report['adapter_checks']:
    count=0;maximum=0.;alpha=[]
    for line in (case/published['case']/'native.log').open():
        if line.startswith('OpenPLL_wire_PC call='):
            values=dict(token.split('=',1) for token in line.split()[1:])
            count+=1;assert int(values['call'])==count and int(values['status'])==0
            error=float(values['scaled_true_relative_residual']);assert math.isfinite(error) and error<=1e-12
            maximum=max(maximum,error);alpha.append(float(values['alpha']))
    assert count==published['linear_solves'] and maximum==published['maximum_true_scaled_relative_residual']
    assert math.isclose(min(alpha),1e-20,rel_tol=1e-12) and max(alpha)>1 and len(set(alpha))>=4
    linear+=count
baseline=(case/'gear_baseline_adapter.cir').read_text()
assert (case/'gear_timestep_holdout_adapter.cir').read_text()==baseline.replace('.tran 2p 8n 0 1p','.tran 2p 8n 0 .47p')
assert (case/'gear_tolerance_holdout_adapter.cir').read_text()==baseline.replace('RELTOL=1e-7 ABSTOL=1e-12','RELTOL=1e-8 ABSTOL=1e-13')
save(out/'assessment.json',dict(completed_native_control_audit_passed=True,wave_comparisons=checks,
    successful_linear_solves_audited=linear,native_GID_and_preservation_mask_verified=True,
    separate_timestep_and_tolerance_holdouts_verified=True,original_equations_match_for_each_comparison=True,
    integration_method_frequency_convergence_tested=False,full_DCO_performance_tested=False,
    input_sha256={str(p.resolve()):digest(p) for p in [Path(__file__),case/'assessment.json']},
    audited_artifact_sha256=report['artifacts'],release_qualified=False,adopted=False))
print(json.dumps(dict(audited_linear_solves=linear,wave_comparisons=len(checks))))
