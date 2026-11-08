"""Diagnostic frequency comparison at equal elapsed time since native reset release."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import json
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha,verify
from assess_selected_detector_phase_probe_v2 import read_selected,transitions
from assess_selected_isolated_control import frequency


def run():
    base=ROOT/'build/signoff400'
    pilot=base/'selected_keeper_static_terminated_DCO_1531'
    waves=base/'selected_keeper_corrected_receiver_waveforms_1467'
    timing=base/'selected_keeper_reference_startup_timing_1539'
    output=base/'selected_keeper_static_reset_aligned_1540'
    output.mkdir(exist_ok=False)
    receipts=[p/'assessment.json' for p in (pilot,waves,timing)]
    records=[json.loads(p.read_text()) for p in receipts]
    for record in records:
        verify(record['input_sha256']);verify(record['artifacts'])
    if not records[0]['normal_native_completion'] or not records[0]['all_native_DCO_leaves_match']:
        raise ValueError('completed checked native pilot required')
    rows=read_selected(pilot/'transient.raw',{'PLLOUT':'PLLOUT','RESET_DRIVER':'RESET_DRIVER'},60e-9)
    reset_edges=transitions(rows,2)['rising_ns']
    if len(reset_edges)!=1:raise ValueError('one pilot reset release required')
    pilot_reset=reset_edges[0]
    reference_edges=records[2]['startup_timing']['reset_threshold_transitions']['rising_ns']
    if len(reference_edges)!=1:raise ValueError('one reference reset release required')
    reference_reset=reference_edges[0]
    metadata=json.loads((waves/'columns.json').read_text())
    col=metadata['ordered_physical_ports'].index('PLLOUT')+1
    data=np.load(waves/'boundary.npy',mmap_mode='r')
    reference=np.column_stack((data[:,0],data[:,col])).tolist()
    windows=[]
    for low,high in [(20,40),(40,54),(20,54)]:
        a=frequency(rows,pilot_reset+low,pilot_reset+high)
        b=frequency(reference,reference_reset+low,reference_reset+high)
        windows.append(dict(age_since_reset_ns=[low,high],
             pilot_window_ns=[pilot_reset+low,pilot_reset+high],
             reference_window_ns=[reference_reset+low,reference_reset+high],
             pilot_frequency=a,reference_frequency=b,
             pilot_relative_to_reference_ppm=(a['frequency_mhz']/b['frequency_mhz']-1)*1e6))
    files=[*receipts,Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py'),
           Path(__file__).with_name('assess_selected_isolated_control.py')]
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},artifacts={},
         pilot_reset_crossing_ns=pilot_reset,reference_reset_crossing_ns=reference_reset,
         windows=windows,threshold_V=0.9,matched_time_since_reset=True,
         reset_slew_and_history_matched=False,receiver_load_qualified=False,
         analog_model_qualified=False,release_ready=False))


if __name__=='__main__':run()
