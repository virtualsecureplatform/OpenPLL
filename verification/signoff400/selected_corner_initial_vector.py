"""Bind a solved non-TT full-circuit reset snapshot to conditional boundaries."""
import json,math,re
from pathlib import Path
from common_v3 import sha,verify
from check_selected_boundary_waveforms import bind


def reuse(folder,corner,base_manifest,model,boundaries):
    receipt=folder/'assessment.json';manifest=folder/'manifest.json'
    a=json.loads(receipt.read_text());m=json.loads(manifest.read_text())
    if corner not in ['ff','ss','sf','fs']:raise ValueError('non-TT initialization corner required')
    for report in [a,m]:
        if (report.get('corner'),report.get('temperature_c'),report.get('supply_v'))!=(corner,27,1.8) or report.get('reset_state_only') is not True:raise ValueError('matching corner reset-state source required')
    if a.get('native_exit_zero') is not True or a.get('all_saved_values_finite') is not True:raise ValueError('normally solved finite initial state required')
    if a['input_sha256']!=m['input_sha256']:raise ValueError('native initialization receipt identity mismatch')
    verify(a['input_sha256']);verify(a['artifacts'])
    if a['input_sha256'].get(str(base_manifest))!=sha(base_manifest) or a['input_sha256'].get(str(model))!=sha(model):raise ValueError('same assembled native circuit required')
    deck=folder/'profile.spice'
    if len(re.findall(r'^\.lib .+ '+corner+r'$',deck.read_text(),re.MULTILINE))!=1:raise ValueError('declared native PDK corner required')
    vector=folder/'initial_voltage_vector.json';raw=folder/'profile.raw'
    if str(vector) not in a['artifacts'] or str(raw) not in a['artifacts']:raise ValueError('pinned raw initialization and vector required')
    v=json.loads(vector.read_text());names=v['variable_names'];values=v['voltage_values']
    if v['time_s']!=0 or len(names)!=len(values) or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in values):raise ValueError('finite native voltage vector required')
    binding=bind(boundaries,names)
    if not binding['all_bound']:raise ValueError('all conditional exterior nodes require solved corner voltages')
    paths=[receipt,manifest,vector,deck,Path(__file__).resolve()]
    return {n:values[binding['bindings'][n]['index']] for n in boundaries},{str(p):sha(p) for p in paths},a['artifacts'][str(raw)]
