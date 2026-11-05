"""Translate native CLK/D/RESET_B curves while solving the real feedback Q.

Use the recorded Q only as a time anchor. Its output voltage is never driven.
Retain a recorded asserted-reset interval so physical initialization does not
require forcing storage or inventing floating-node initial voltages.
"""
import json
from pathlib import Path
from common_v3 import save,sha,verify
from selected_native_clock_shapes import load,rising,shift_window


def prepare(folder,drives,phase_ns,output):
    receipt=folder/'assessment.json';a=json.loads(receipt.read_text());verify(a['artifacts'])
    if not a.get('exact_saved_knots_preserved') or not a.get('source_complete_and_all_values_finite'):raise ValueError('exact finite native input curves required')
    items=a['clock_driver_waveforms'];q=Path(items['CLKDIVR']['file']);anchor=rising(load(q),180e-9)
    pins={str(receipt):sha(receipt),str(q):sha(q),str(Path(__file__).resolve()):sha(Path(__file__)),str(Path(__file__).with_name('selected_native_clock_shapes.py')):sha(Path(__file__).with_name('selected_native_clock_shapes.py'))};waveforms={};details={}
    for role,key in [('reference','REF'),('feedback_ff_clock','feedback_ff_clock'),('feedback_ff_data','feedback_ff_data'),('feedback_ff_reset','feedback_ff_reset')]:
        item=items[key]
        if drives.get(role)!=item['node']:raise ValueError('recorded input curve belongs to another physical pin')
        path=Path(item['file']);rows=load(path)
        shift=rising(rows,0)-20e-9 if role=='reference' else anchor-(20+phase_ns)*1e-9
        shifted=shift_window(rows,shift,80e-9)
        if role=='feedback_ff_reset' and max(v for t,v in shifted if t<=1e-9)>=.18:raise ValueError('recorded window must retain an asserted driver reset interval')
        destination=output/(role+'_native.pwl')
        with destination.open('x') as f:
            for t,v in shifted:f.write(f'{t:.17g} {v:.17g}\n')
        pins[str(path)]=sha(path);pins[str(destination)]=sha(destination);waveforms[role]=f'PWL FILE "{destination}"'
        details[role]=dict(source=str(path),physical_input_node=item['node'],time_translation_s=shift,knots=len(shifted),
            voltage_values_approximated=False,time_warp_applied=False,extrapolation_applied=False)
    metadata=output/'native_shape_construction.json';verify(pins)
    save(metadata,dict(input_sha256=pins,clock_sources=details,original_recorded_feedback_Q_anchor_s=anchor,
        feedback_driver_Q_voltage_prescribed=False,driver_reset_initially_asserted=True,
        physical_driver_clock_and_data_history_retained=True,waveform_construction_qualifies_interface=False,release_ready=False))
    pins[str(metadata)]=sha(metadata);return waveforms,pins
