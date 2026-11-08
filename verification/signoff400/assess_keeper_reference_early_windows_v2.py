"""Measure startup-window frequency using verified completed reference extraction."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import json
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha,verify
from assess_selected_isolated_control import frequency
from assess_keeper_physical_tuning import expected


def run():
    b=ROOT/'build/signoff400'
    waves=b/'selected_keeper_corrected_receiver_waveforms_1467'
    physical=b/'selected_keeper_corrected_BSIM_physical_1296'
    reference=b/'selected_keeper_corrected_BSIM_fine149_1295'
    output=b/'selected_keeper_reference_early_windows_1534'
    output.mkdir(exist_ok=False)
    receipts=[p/'assessment.json' for p in (waves,physical,reference)]
    records=[json.loads(p.read_text()) for p in receipts]
    for record in records[:2]:
        verify(record['input_sha256']);verify(record['artifacts'])
    if not records[0]['completed_boundary_waveforms_available'] or not records[2]['normal_native_completion']:
        raise ValueError('completed normal reference required')
    columns=waves/'columns.json'
    names=json.loads(columns.read_text())['ordered_physical_ports']
    index=names.index('PLLOUT')+1
    data=np.load(waves/'boundary.npy',mmap_mode='r')
    rows=np.column_stack((data[:,0],data[:,index])).tolist()
    plan=physical/'plan.json'
    observations=json.loads(plan.read_text())['observations']
    controls=np.load(physical/'controls.npy',mmap_mode='r')
    if not np.array_equal(data[:,0],controls[:,0]):raise ValueError('identical sample grid required')
    results=[]
    final=records[2]['frequency_diagnostic']['frequency_mhz']
    for low,high in [(20,60),(60,100),(100,140),(140,180),(200,260)]:
        mask=(controls[:,0]>=low*1e-9)&(controls[:,0]<=high*1e-9)
        checks=[]
        for i,observation in enumerate(observations.values(),1):
            v=controls[mask,i]
            high_bit=expected(observation['bus'],observation['bit'],20,149)
            checks.append(bool(v.min()>=1.44 if high_bit else v.max()<=.36))
        reason=None
        try:f=frequency(rows,low,high)
        except ValueError as error:f=None;reason=str(error)
        results.append(dict(window_ns=[low,high],frequency_diagnostic=f,
             frequency_unavailable_reason=reason,
             difference_from_final_ppm=(f['frequency_mhz']/final-1)*1e6 if f else None,
             physical_endpoints_checked=len(checks),all_controls_match=all(checks)))
    files=[*receipts,columns,plan,Path(__file__).resolve(),
           Path(__file__).with_name('assess_selected_isolated_control.py'),
           Path(__file__).with_name('assess_keeper_physical_tuning.py')]
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},artifacts={},
         completed_reference_only=True,windows=results,
         startup_convergence_qualified=False,independent_model_qualified=False,release_ready=False))


if __name__=='__main__':run()
