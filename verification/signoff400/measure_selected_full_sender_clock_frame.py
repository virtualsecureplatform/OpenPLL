"""Measure first receiver clock transport from one matching full-native source."""
import argparse,csv,json,math,statistics
from pathlib import Path
from common_v3 import save,sha,verify
from selected_matching_corner_sender import validate
from selected_native_clock_shapes import load
from assess_selected_detector_phase_probe_v4 import transitions
from measure_selected_receiver_clock_frame import pair


def run(native,snapshot,waveforms,reference,corner,output):
    if output.exists():raise FileExistsError(output)
    op,pins=validate(native,snapshot,waveforms,corner)
    provenance=reference/'provenance.json';p=json.loads(provenance.read_text())
    verify(p['input_sha256']);verify(p['native_input_sha256']);verify(p['artifacts'])
    manifest=native/'manifest.json';raw=native/'profile.raw';sr=json.loads((snapshot/'assessment.json').read_text())
    if p['input_sha256'].get(str(manifest))!=sha(manifest) or p['raw_sha256']!=sr['input_sha256'].get(str(raw)):
        raise ValueError('root CSV and sender must derive from the identical full-native RAW')
    assessment=reference/'assessment.json';a=json.loads(assessment.read_text())
    if a['end_ns']!=260 or a['dco_code']['window_codes']!=[op['fine']] or len(a['coarse_code']['window_codes'])!=1:
        raise ValueError('complete full-native stationary calibration window required')
    signals=reference/'signals.csv'
    if p['artifacts'].get(str(signals))!=sha(signals):raise ValueError('root CSV must be bound by provenance')
    root=[]
    with signals.open() as stream:
        for row in csv.DictReader(stream):
            t,v=float(row['time']),float(row['v(pllout)'])
            if not math.isfinite(t) or not math.isfinite(v) or (root and t<=root[-1][0]):
                raise ValueError('finite strictly ordered root waveform required')
            root.append((t,v))
    if not root or root[0][0]!=0 or root[-1][0]<260e-9:raise ValueError('complete root waveform coverage required')
    packet=json.loads((waveforms/'assessment.json').read_text());role=packet['clock_driver_waveforms']['synchronizer_clock']
    inventory_paths=[Path(x) for x in packet['input_sha256'] if x.endswith('/selected_interface_clock_reset_inventory_276.json')]
    if len(inventory_paths)!=1:raise ValueError('unique physical receiver inventory required')
    inventory=inventory_paths[0];iv=json.loads(inventory.read_text());verify(iv['input_sha256'])
    if role['node']!=iv['clock_drivers']['synchronizer_clock']['node']:
        raise ValueError('receiver waveform must match physical first-stage clock node')
    local_path=Path(role['file']);local=load(local_path)
    if local[0][0]!=0 or local[-1][0]<260e-9:raise ValueError('complete local waveform coverage required')
    root_edges=transitions(root,1)['rising_ns'];local_edges=transitions(local,1)['rising_ns']
    records=pair(root_edges,[t for t in local_edges if 200<=t<=260],limit_ns=1)
    if len(records)<20:raise ValueError('at least twenty stationary receiver edge pairs required')
    values=[r['transport_ps'] for r in records]
    paths=[provenance,assessment,signals,inventory,local_path,Path(__file__).resolve()]
    paths += [Path(__file__).with_name(n) for n in ['common_v3.py','selected_matching_corner_sender.py','selected_spice_device_conditions.py','selected_native_clock_shapes.py','assess_selected_detector_phase_probe_v4.py','measure_selected_receiver_clock_frame.py','capture_selected_native_initial_snapshot.py']]
    pins.update({str(x):sha(x) for x in paths});verify(pins);output.mkdir(parents=True)
    save(output/'assessment.json',dict(input_sha256=pins,operating_point={k:v for k,v in op.items() if k!='fine'},source_fine=op['fine'],source_coarse=a['coarse_code']['window_codes'][0],clock_pairs={'first':records},
        transport_ps=dict(minimum=min(values),median=statistics.median(values),maximum=max(values)),measurement_window_ns=[200,260],root_clock_node='PLLOUT',receiver_clock_node=role['node'],pairing_limit_ns=1,
        same_full_native_root_and_receiver_source=True,second_receiver_clock_measured=False,
        scope='first-stage clock transport at one full-native stationary code; no phase warp or extrapolation',
        native_interface_qualified=False,complete_controller_timing_qualified=False,clock_timing_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['native','snapshot','waveforms','reference','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--corner',choices=['tt','ff','ss','sf','fs'],required=True);a=p.parse_args()
    run(a.native.resolve(),a.snapshot.resolve(),a.waveforms.resolve(),a.reference.resolve(),a.corner,a.output.resolve())
