"""Check that a clock-cone control only expands the retained physical circuit."""
import argparse,collections,json
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources


def run(reference,prepared,plan,output):
    if output.exists():raise FileExistsError(output)
    p=json.loads(plan.read_text());verify(p['input_sha256'])
    old,new=[{n:v for n,(_,v) in sources(folder/'sources.spice').items()} for folder in [reference,prepared]]
    differences=[n for n in old.keys()&new.keys() if old[n]!=new[n]]
    if differences:raise ValueError('shared boundary values changed: '+repr(differences[:10]))
    before=collections.Counter((reference/'devices.spice').read_text().splitlines());after=collections.Counter((prepared/'devices.spice').read_text().splitlines())
    if before-after:raise ValueError('original physical device/passive lines removed or changed')
    private=set(p['private_unknown_nodes'])
    if not set(p['resolved_dynamic_boundary_nodes'])<=private or set(p['resolved_dynamic_boundary_nodes'])&set(new):raise ValueError('resolved clock outputs must be native unknowns')
    for folder in [reference,prepared]:
        m=json.loads((folder/'manifest.json').read_text())
        if {m['observed_roles'][role] for role in ['oscillator','DCO_reset']}&set(new):raise ValueError('observed DCO output/reset voltage clamp')
    def options(folder):return [l for l in (folder/'control.spice').read_text().splitlines() if l.startswith(('.lib ','.options ','.tran '))]
    if options(reference)!=options(prepared):raise ValueError('native physical corner or solver settings changed')
    paths=[plan,Path(__file__).resolve(),Path(__file__).with_name('audit_selected_dco_history_inputs.py')]+[folder/name for folder in [reference,prepared] for name in ['manifest.json','devices.spice','sources.spice','control.spice']]
    pins={str(q):sha(q) for q in paths};verify(pins)
    save(output,dict(input_sha256=pins,all_original_device_and_passive_lines_retained=True,
        all_shared_boundary_values_unchanged=True,corner_solver_and_horizon_unchanged=True,
        common_boundary_nodes=len(old.keys()&new.keys()),removed_voltage_cuts=len(old.keys()-new.keys()),added_voltage_cuts=len(new.keys()-old.keys()),
        resolved_clock_nodes=p['resolved_dynamic_boundary_nodes'],added_physical_cells=len(p['added_clock_driver_cells']),added_primitives=len(p['added_primitives']),
        unresolved_clock_nodes=p['unresolved_dynamic_boundary_nodes'],native_comparison_complete=False,physical_models_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','prepared','plan','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','prepared','plan','output']))
