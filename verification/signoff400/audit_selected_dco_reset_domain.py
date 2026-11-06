"""Trace the retained reset-release state cells to the actual DCO reset buffer."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import Union
from audit_selected_dco_history_inputs import sources
from assess_selected_detector_prefix import read_prefix


def run(plan,halo,model,native,output):
    if output.exists():raise FileExistsError(output)
    p,h,m=[json.loads(x.read_text()) for x in [plan,halo,native/'manifest.json']]
    for x in [p,h,m]:verify(x['input_sha256'])
    if any(x['input_sha256'].get(str(model))!=sha(model) for x in [p,m]):raise ValueError('same actual native circuit required')
    selected=set(p['selected_primitives']);state=[c for c in h['added_cells'] if 'dfrtp' in c['master'] and set(c['primitives'])<=selected]
    if len(state)!=4:raise ValueError('four original retained state cells required')
    reset=m['observed_roles']['DCO_reset'];union=Union()
    for line in model.open():
        fields=line.split()
        if fields and fields[0][0].upper()=='R':union.join(fields[1],fields[2])
    if any(union.find(c['pins']['RESET_B'])!=union.find(reset) for c in state):raise ValueError('state resets not in DCO reset component')
    drivers=[c for c in h['added_cells'] if c['master']=='sky130_fd_sc_hs__clkbuf_4' and union.find(c['pins']['X'])==union.find(reset)]
    if len(drivers)!=1 or drivers[0]['pins']['A']!=p['prescribed_reset_driver_input']:raise ValueError('unique actual prescribed reset buffer required')
    src=sources(native/'sources.spice');driver_input=p['prescribed_reset_driver_input']
    if src[driver_input][1]!='PULSE(0 1.8 5n 50p 50p 80n 160n)':raise ValueError('declared initial low reset protocol differs')
    clamps=[n for n in src if union.find(n)==union.find(reset)]
    if clamps:raise ValueError('actual reset output voltage prescribed')
    a=json.loads((native/'assessment.json').read_text());verify(a['artifacts']);rows,info=read_prefix(native/'control.raw',m['observed_roles']);first_reset=rows[0][list(m['observed_roles']).index('DCO_reset')+1]
    files=[plan,halo,model,native/'manifest.json',native/'assessment.json',native/'sources.spice',native/'control.raw',Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py'),Path(__file__).with_name('assess_selected_detector_prefix.py')]
    save(output,dict(input_sha256={str(x):sha(x) for x in files},state_cells=[dict(master=c['master'],pins=c['pins'],primitives=c['primitives']) for c in state],all_four_reset_pins_on_actual_DCO_reset_R_component=True,reset_buffer=drivers[0],prescribed_driver_input=driver_input,reset_input_protocol=src[driver_input][1],reset_output_voltage_prescribed=False,baseline_initial_reset_voltage_V=first_reset,scope='physical reset-domain connectivity and completed baseline initial voltage; not failed-load DC state or uniqueness proof',DC_failure_cause_identified=False,release_ready=False));print('four state resets use actual reset buffer; baseline initial reset voltage',first_reset)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['plan','halo','model','native','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['plan','halo','model','native','output']))
