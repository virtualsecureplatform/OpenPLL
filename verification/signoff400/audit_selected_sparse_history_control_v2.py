"""Bind a sparse-history diagnostic to its original physical circuit and bounds."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources
from selected_spice_device_conditions import matching
from selected_native_clock_shapes import load


def run(baseline,candidate,schedule_probe,output):
    if output.exists():raise FileExistsError(output)
    bm,cm=[json.loads((d/'manifest.json').read_text()) for d in [baseline,candidate]]
    for m in [bm,cm]:verify(m['input_sha256'])
    if (baseline/'devices.spice').read_bytes()!=(candidate/'devices.spice').read_bytes():raise ValueError('physical cards changed')
    if bm['controls']!=cm['controls'] or bm['observed_roles']!=cm['observed_roles']:raise ValueError('physical controls or observations changed')
    conditions=matching(baseline/'control.spice',candidate/'control.spice')
    def body(p,expected):
        text=p.read_text()
        if text.splitlines().count(expected)!=1:raise ValueError('explicit expected 260 ns protocol required')
        text,n=re.subn(r'(?m)^\.include "[^"\n]+/(devices|sources)\.spice"$',lambda m:'.include "<'+m[1]+'>"',text)
        if n!=2:raise ValueError('two physical/source includes required')
        text,n=re.subn(r'(?i)\bfile=\S+','file=<RAW>',text)
        if n!=1:raise ValueError('one waveform output required')
        return text.replace(expected,'<explicit changed timestep schedule>')
    if body(baseline/'control.spice','.tran 10p 260n 0 10p')!=body(candidate/'control.spice','.tran 10p 260n {schedule(0,1n,100n,10p,112n,1n,175n,10p)}'):raise ValueError('other native solver protocol changed')
    br,cr=[json.loads((d/'history_sources/assessment.json').read_text()) for d in [baseline,candidate]]
    for r in [br,cr]:verify(r['input_sha256'])
    if set(br['sources'])!=set(cr['sources']):raise ValueError('history source roles changed')
    files=[Path(__file__).resolve(),schedule_probe]+[Path(__file__).with_name(n) for n in ['audit_selected_dco_history_inputs.py','selected_spice_device_conditions.py','selected_native_clock_shapes.py']];records=[]
    for role,x in cr['sources'].items():
        y=br['sources'][role];limit=1e-6 if role=='DCO_reset_driver_input' else 1e-3
        if x['node']!=y['node'] or x['source']!=y['source'] or x['hold_after_ns']!=y['hold_after_ns']:raise ValueError('physical history identity changed')
        if x['uniform_voltage_bound_V']!=limit or x['maximum_voltage_difference_V']>limit or not x['union_knot_voltage_certificate']:raise ValueError('missing uniform source-voltage certificate')
        if any(z['maximum_crossing_time_difference_s']>1e-18 for z in x['threshold_crossings']):raise ValueError('threshold timing changed')
        records.append(dict(role=role,bound_V=limit,maximum_error_V=x['maximum_voltage_difference_V'],original_knots=x['original_knots'],bounded_knots=x['bounded_knots']))
    x,y=sources(baseline/'sources.spice'),sources(candidate/'sources.spice');nodes={v['node'] for v in cr['sources'].values()}
    if x.keys()!=y.keys() or any(x[n]!=y[n] for n in x.keys()-nodes):raise ValueError('unrelated boundary source changed')
    for n in nodes:
        paths=[]
        for entry in [x[n][1],y[n][1]]:
            m=re.fullmatch(r'PWL FILE "([^"]+)"',entry)
            if not m:raise ValueError('explicit PWL file source required')
            paths.append(Path(m[1]))
        a,b=map(load,paths)
        if a[0]!=b[0] or a[-1]!=b[-1]:raise ValueError('initial or final source values changed')
        files+=paths
    probe=json.loads(schedule_probe.read_text());verify(probe['input_sha256']);verify(probe['artifacts'])
    if not probe['actual_native_schedule_verified']:raise ValueError('actual native timestep schedule probe required')
    files += [d/n for d in [baseline,candidate] for n in ['manifest.json','devices.spice','sources.spice','control.spice','history_sources/assessment.json']]
    pins={str(p):sha(p) for p in files};verify(pins)
    save(output,dict(input_sha256=pins,device_conditions=conditions,physical_cards_controls_observations_and_other_boundaries_identical=True,initial_and_final_prescribed_values_identical=True,source_certificates=records,timestep_schedule_actual_native_verified=True,source_voltage_and_schedule_changes_explicit=True,charge_error_bounded=False,DCO_response_equivalence_qualified=False,release_ready=False))
    print('audited',len(records),'bounded history sources')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['baseline','candidate','schedule-probe','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.baseline.resolve(),a.candidate.resolve(),a.schedule_probe.resolve(),a.output.resolve())
