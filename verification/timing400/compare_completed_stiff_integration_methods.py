#!/usr/bin/env python3
"""Compare existing stock-simulator control traces across integration methods.

No native rerun; this is a fixture observation, not DCO frequency convergence.
"""
from array import array
import json,math
from pathlib import Path
import numpy as np
from compile_local_C_operators_v2 import digest,save

root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
old=base/'wire_preconditioned_native_controls_002';new=base/'wire_preconditioned_native_controls_004'
out=base/'completed_stiff_integration_comparison_001';out.mkdir(exist_ok=False)
prior=json.loads((old/'timeout_assessment.json').read_text());verified=json.loads((new/'assessment.json').read_text())
assert prior['stock_baseline_completed'] and verified['native_adapter_controls_passed']
pins={str(p.resolve()):digest(p) for p in [Path(__file__),old/'timeout_assessment.json',new/'assessment.json']}

def wave(path,expected_sha):
    assert digest(path)==expected_sha
    values=array('d');count=0;ended=False;previous=-1.
    with path.open() as handle:
        assert handle.readline().split()==['Index','TIME','V(A)','V(B)','V(OUTPUT)','I(VDD)']
        for line in handle:
            f=line.split()
            if f and f[0].isdigit():
                assert not ended and len(f)==6 and int(f[0])==count
                row=[float(v) for v in f[1:]]
                assert all(math.isfinite(v) for v in row) and row[0]>previous
                values.extend(row);count+=1;previous=row[0]
            elif 'End of Xyce(TM) Simulation' in line:ended=True
    a=np.asarray(values).reshape(count,5);assert ended and a[0,0]==0 and a[-1,0]>=8e-9*(1-1e-8)
    pins[str(path)]=expected_sha;return a

def crossing(a,rising):
    i=np.flatnonzero((a[:-1,3]<.9)&(a[1:,3]>=.9) if rising else (a[:-1,3]>.9)&(a[1:,3]<=.9))
    return a[i,0]+(.9-a[i,3])*(a[i+1,0]-a[i,0])/(a[i+1,3]-a[i,3])

def mean_current(a,start=6.2e-9,end=8e-9):
    selected=a[(a[:,0]>start)&(a[:,0]<end)]
    times=np.r_[start,selected[:,0],end]
    currents=np.r_[np.interp(start,a[:,0],a[:,4]),selected[:,4],np.interp(end,a[:,0],a[:,4])]
    return float(np.trapezoid(currents,times)/(end-start))

reference=old/'baseline_stock.cir';source=reference.read_text()
assert digest(reference)==prior['input_sha256'][str(reference.resolve())]
ref_path=Path(str(reference)+'.prn');a=wave(ref_path,prior['input_sha256'][str(ref_path.resolve())])
grid=np.linspace(0,8e-9,100001);records=[]
for label in ['gear_baseline_stock','gear_timestep_holdout_stock','gear_tolerance_holdout_stock']:
    deck=new/(label+'.cir');text=deck.read_text()
    reverse=text.replace('.options TIMEINT METHOD=GEAR ','.options TIMEINT ')
    if label=='gear_timestep_holdout_stock':reverse=reverse.replace('.tran 2p 8n 0 .47p','.tran 2p 8n 0 1p')
    if label=='gear_tolerance_holdout_stock':reverse=reverse.replace('RELTOL=1e-8 ABSTOL=1e-13','RELTOL=1e-7 ABSTOL=1e-12')
    assert reverse==source
    assert digest(deck)==verified['input_sha256'][str(deck.resolve())];pins[str(deck)]=digest(deck)
    path=Path(str(deck)+'.prn');b=wave(path,verified['artifacts'][str(path)])
    differences=[float(np.max(abs(np.interp(grid,a[:,0],a[:,i])-np.interp(grid,b[:,0],b[:,i])))) for i in range(1,5)]
    edge_errors={}
    for rising in [False,True]:
        x,y=crossing(a,rising),crossing(b,rising);assert len(x)==len(y) and len(x)>0
        edge_errors['rise' if rising else 'fall']=float(np.max(abs(x-y)))
    records.append(dict(case=label,stock_trapezoid_samples=len(a),stock_Gear_samples=len(b),
        voltage_max_differences_V=differences[:3],instantaneous_supply_current_difference_A=differences[3],
        output_threshold_edge_differences_s=edge_errors,
        trapezoid_mean_supply_current_A=mean_current(a),Gear_mean_supply_current_A=mean_current(b),
        physical_circuit_and_PVT_identical=True))
save(out/'assessment.json',dict(completed_trace_comparison=True,cases=records,input_sha256=pins,
    native_simulations_repeated=False,fixture_only_observation=True,physical_circuit_changed=False,
    DCO_frequency_convergence_tested=False,Gear_selected_for_DCO=False,
    numerical_domain_enclosure_qualified=False,release_qualified=False,adopted=False))
print(json.dumps(records))
