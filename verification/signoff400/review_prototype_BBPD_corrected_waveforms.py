"""Review corrected native BBPD captures with explicit full-horizon input guard edges."""
import argparse
import json
import math
import os
from pathlib import Path
import time
from common_v3 import save,sha,verify
from resources import identity,lease
from run_prototype_BBPD_coupled_pilot import read_table
from assess_prototype_native_waveform import crossings


def measure(rows,phase_ps):
    start,stop=5e-9,85e-9
    def edges(column):return crossings([(r[0],r[column]) for r in rows],.9)
    for column,offset in ((1,0),(2,phase_ps/1000)):
        expected=[(10.1+offset+40*i)*1e-9 for i in range(3) if 10.1+offset+40*i<=90]
        actual=edges(column)[0]
        if len(actual)!=len(expected) or any(abs(a-b)>1e-12 for a,b in zip(actual,expected)):raise ValueError('native input clock/phase/guard mismatch')
    reset=edges(3)[0]
    if len(reset)!=1 or abs(reset[0]-1.1e-9)>1e-12:raise ValueError('reset-release mismatch')
    ref=[t for t in edges(1)[0] if start<=t<=stop];div=[t for t in edges(2)[0] if start<=t<=stop]
    if len(ref)!=len(div) or len(ref)!=2:raise ValueError('two analysis-window clock samples required')
    result={}
    for name,clock_column,q_column in (('DN',4,6),('UP',5,7)):
        rise,fall=edges(clock_column)
        cr=[t for t in rise if start<=t<=stop];cf=[t for t in fall if start<=t<=stop]
        qr,qf=edges(q_column);q=sorted([(t,'rise') for t in qr if start<=t<=stop]+[(t,'fall') for t in qf if start<=t<=stop])
        matched=len(q)==len(cr) and all(d==('rise' if i%2==0 else 'fall') and 0<=t-cr[i]<=10e-9 for i,(t,d) in enumerate(q))
        widths=[]
        for t in cr:
            following=[f for f in cf if f>t]
            if following:widths.append((following[0]-t)*1e12)
        quiet=[r[q_column] for r in rows if start<=r[0]<=8e-9]
        result[name]=dict(detector_rising_edges_ns=[t*1e9 for t in cr],detector_falling_edges_ns=[t*1e9 for t in cf],
            complete_high_pulse_widths_ps=widths,toggle_edges=[dict(time_ns=t*1e9,direction=d) for t,d in q],
            one_toggle_per_detector_rise_observed=matched,paired_delays_ps=[(t-c)*1e12 for (t,d),c in zip(q,cr)] if matched else None,
            quiet_before_first_sample=bool(quiet) and max(quiet)<.36,
            full_horizon_detector_edge_counts=[len(rise),len(fall)])
    return dict(phase_ps=phase_ps,analysis_window_ns=[5,85],full_input_guard_edges_verified=True,
        measured_analysis_phase_ps=[(b-a)*1e12 for a,b in zip(ref,div)],outputs=result,
        native_interface_qualified=False)


def run(source,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    save(output/'status.json',dict(state='waiting_for_corrected_native_pilot',release_ready=False))
    while not (source/'assessment.json').exists():
        owner=json.loads((source/'owner.json').read_text())
        if identity(owner['pid'])!=owner['birth']:raise ValueError('native pilot disappeared without receipt')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('native review deadline')
        time.sleep(1)
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    manifest=source/'input_manifest.json';m=json.loads(manifest.read_text())
    if m.get('ng47_effective_diode_geometry_applied') is not True or m['added_shunt_capacitance_F_per_voltage_node']!=0:raise ValueError('corrected unperturbed physical model required')
    # Retain the original guard-observer failure; re-assess complete native data,
    # never treat a resource/solver failure as an observer-only failure.
    observed=json.loads((source/'observations.json').read_text())
    for failure in observed['failures']:
        if failure['reason']!="ValueError('two reference and divided-clock samples required')":raise ValueError('native failure is not the identified observer guard error')
    paths=[receipt,manifest,source/'observations.json',Path(__file__).resolve(),Path(__file__).with_name('run_prototype_BBPD_coupled_pilot.py'),Path(__file__).with_name('assess_prototype_native_waveform.py')]
    records=[]
    with lease(1,4,deadline):
        for phase in m['phase_ps']:
            log=source/('phase_'+str(phase)+'ps')/'native.log';paths.append(log)
            if r['artifacts'].get(str(log))!=sha(log):raise ValueError('unbound native waveform')
            records.append(measure(read_table(log.read_text()),phase))
    pins={str(p):sha(p) for p in paths};detail=output/'observations.json';save(detail,records);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},reviewed_native_cases=len(records),
        geometry_model=m['geometry_model'],ng47_effective_diode_geometry_applied=True,full_input_guard_edges_verified=True,
        analysis_window_ns=[5,85],old_guard_observer_superseded=True,intercell_RC_included=False,parent_coupling_included=False,
        omitted_loads_bounded=False,native_interface_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='corrected_BBPD_waveform_review_complete',release_ready=False))
    print('Reviewed corrected native cases:',len(records))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve())
