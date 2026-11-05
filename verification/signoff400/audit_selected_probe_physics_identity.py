"""Check exact generated circuit/stimulus identity before reusing a probe path."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from compare_selected_detector_clock_controls import canonical_deck,signature
from audit_selected_dco_history_inputs import sources


def run(reference,candidate,output):
    if output.exists():raise FileExistsError(output)
    for folder in [reference,candidate]:verify(json.loads((folder/'manifest.json').read_text())['input_sha256'])
    for name in ['devices.spice','exterior_initial_voltages.json']:
        if sha(reference/name)!=sha(candidate/name):raise ValueError('physical probe input changed: '+name)
    a,b=[sources(folder/'sources.spice') for folder in [reference,candidate]]
    if a.keys()!=b.keys() or any(a[n][0]!=b[n][0] or signature(a[n][1])!=signature(b[n][1]) for n in a):raise ValueError('exact voltage sources changed')
    if canonical_deck((reference/'probe.spice').read_text())!=canonical_deck((candidate/'probe.spice').read_text()):raise ValueError('solver or observation deck changed')
    paths=[reference/'manifest.json',candidate/'manifest.json',Path(__file__).resolve(),Path(__file__).with_name('compare_selected_detector_clock_controls.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py')]
    pins={str(p):sha(p) for p in paths};verify(pins)
    save(output,dict(input_sha256=pins,physical_circuit_identical=True,exterior_biases_identical=True,
        all_voltage_waveform_values_identical=True,solver_controls_identical=True,observed_nodes_identical=True,
        input_comparison_only=True,new_native_response_measured=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['reference','candidate','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,name).resolve() for name in ['reference','candidate','output']))
