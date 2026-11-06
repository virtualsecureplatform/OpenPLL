"""Verify a prepared reference-forcing experiment changes only two source values."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources
from compare_selected_dco_load_controls import canonical_deck


def run(reference,prepared,proof,output):
    if output.exists():raise FileExistsError(output)
    r=json.loads(proof.read_text());verify(r['input_sha256'])
    expected={x['node'] for x in r['switching_cuts_above_0p1V']}
    if len(expected)!=2 or any(x['resistively_connected_top_ports']!=['REFCLK'] for x in r['switching_cuts_above_0p1V']):raise ValueError('exact two reference boundaries required')
    m=json.loads((prepared/'manifest.json').read_text());verify(m['input_sha256'])
    if sha(reference/'devices.spice')!=sha(prepared/'devices.spice'):raise ValueError('physical device/passive file changed')
    a,b=[sources(p/'sources.spice') for p in [reference,prepared]]
    if a.keys()!=b.keys() or any(a[n][0]!=b[n][0] for n in a):raise ValueError('source identity or inventory changed')
    changed={n for n in a if a[n][1]!=b[n][1]}
    if changed!=expected or changed!=set(m['changed_voltage_sources']):raise ValueError('unexpected source changes')
    if canonical_deck((reference/'control.spice').read_text())!=canonical_deck((prepared/'control.spice').read_text()):raise ValueError('physical corner, solver or observation protocol changed')
    bm=json.loads((reference/'manifest.json').read_text())
    if any(m[k]!=bm[k] for k in ['operating_point','controls','observed_roles']):raise ValueError('programming/physical observations changed')
    if {m['observed_roles'][k] for k in ['oscillator','DCO_reset']}&changed:raise ValueError('DCO output/reset may not be prescribed')
    paths=[proof,Path(__file__).resolve(),Path(__file__).with_name('audit_selected_dco_history_inputs.py'),Path(__file__).with_name('compare_selected_dco_load_controls.py')]
    paths += [p/name for p in [reference,prepared] for name in ['manifest.json','devices.spice','sources.spice','control.spice']]
    pins={str(p):sha(p) for p in paths};verify(pins)
    save(output,dict(input_sha256=pins,physical_devices_and_passives_identical=True,source_inventory_and_names_unchanged=True,
        changed_source_values=sorted(changed),all_other_source_values_unchanged=True,corner_solver_programming_and_observations_unchanged=True,
        native_comparison_complete=False,universal_exterior_model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','prepared','proof','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','prepared','proof','output']))
