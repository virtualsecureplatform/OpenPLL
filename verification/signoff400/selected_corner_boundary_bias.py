"""Bind a completed full-circuit reset-state vector to one matching corner."""
import json,math
from pathlib import Path
from common_v3 import sha,verify
from check_selected_boundary_waveforms import bind

def select(vector,boundaries):
    names,values=vector['variable_names'],vector['voltage_values']
    if vector['time_s']!=0 or len(names)!=len(values) or len(set(names))!=len(names):
        raise ValueError('unique complete time-zero vector required')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
        raise ValueError('finite native voltages required')
    binding=bind(boundaries,names)
    if not binding['all_bound']:raise ValueError('all exterior nodes must bind')
    return {n:values[binding['bindings'][n]['index']]for n in boundaries}

def load(folder,corner,model,boundaries):
    receipt=folder/'assessment.json';a=json.loads(receipt.read_text())
    if (a.get('corner'),a.get('temperature_c'),a.get('supply_v'))!=(corner,27,1.8):
        raise ValueError('matching exterior corner/temperature/supply required')
    if not all(a.get(k) is True for k in ('reset_state_only','native_exit_zero','all_saved_values_finite')):
        raise ValueError('completed finite reset-state solve required')
    verify(a['input_sha256']);verify(a['artifacts'])
    if a['input_sha256'].get(str(model))!=sha(model):raise ValueError('same full physical model required')
    vectors=[Path(p)for p in a['artifacts']if p.endswith('/initial_voltage_vector.json')]
    if len(vectors)!=1:raise ValueError('one pinned native voltage vector required')
    quiet=select(json.loads(vectors[0].read_text()),boundaries)
    return quiet,{str(p):sha(p)for p in (receipt,vectors[0])}
