"""Compare a prepared second-stage control to the original same-phase native deck."""
import argparse,collections,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources


def normalized(folder):
    result={}
    for node,(name,value) in sources(folder/'sources.spice').items():
        match=re.fullmatch(r'PWL FILE "([^"]+)"',value)
        result[node]=('PWL_FILE_SHA256',sha(Path(match[1]))) if match else ('expression',value)
    return result


def run(reference,prepared,plan,output):
    if output.exists():raise FileExistsError(output)
    x,y=normalized(reference),normalized(prepared)
    s=json.loads((plan/'stimulus_ports.json').read_text());p=json.loads((plan/'plan.json').read_text())
    verify(s['input_sha256']);verify(p['input_sha256'])
    clock=s['prescribed_voltage_roles']['second_synchronizer_clock']
    differences={n for n in x.keys()&y.keys() if x[n]!=y[n]}
    if differences!={clock} or y[clock][0]!='PWL_FILE_SHA256':raise ValueError('only the newly activated next-stage clock may change on shared cuts')
    a=collections.Counter((reference/'devices.spice').read_text().splitlines())
    b=collections.Counter((prepared/'devices.spice').read_text().splitlines())
    if a-b:raise ValueError('original physical device lines removed or changed')
    if set(s['observed_unknown_roles'].values())&set(y):raise ValueError('observed circuit output voltage clamped')
    files=[Path(__file__).resolve(),plan/'plan.json',plan/'stimulus_ports.json']
    files += [folder/name for folder in [reference,prepared] for name in ['manifest.json','sources.spice','devices.spice']]
    pins={str(f):sha(f) for f in files};verify(pins)
    save(output,dict(input_sha256=pins,all_original_device_lines_retained_identically=True,
        shared_boundary_sources_identical_except_newly_activated_second_clock=True,
        activated_recorded_clock_node=clock,common_boundary_nodes=len(x.keys()&y.keys()),
        added_boundary_nodes=len(y.keys()-x.keys()),removed_boundary_nodes=len(x.keys()-y.keys()),
        all_observed_outputs_unclamped=True,added_physical_primitives=len(p['added_primitives']),
        native_execution_completed=False,full_controller_timing_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','prepared','plan','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','prepared','plan','output']))
