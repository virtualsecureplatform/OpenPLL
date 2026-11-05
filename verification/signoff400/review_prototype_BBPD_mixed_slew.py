"""Review divided-clock slew sensitivity with measured native input ramps."""
import argparse
import json
from pathlib import Path
import time
from common_v3 import save,sha,verify
from resources import identity
from run_prototype_BBPD_mixed_slew import read_table
from assess_prototype_native_waveform import crossings
from prototype_BBPD_guard_v2 import measure
from review_prototype_BBPD_with_sync import sync_metrics


def decision(outputs,sync):
    active=[name for name,row in outputs.items() if row['detector_rising_edges_ns']]
    if len(active)!=1:return None
    if any(not row['one_toggle_per_detector_rise_observed'] for row in outputs.values()):return None
    if any(not row['quiet_output_low_rail_screen_pass'] or not row['one_delayed_capture_per_source_toggle_observed'] for row in sync.values()):return None
    row=outputs[active[0]]
    return active[0] if len(row['detector_rising_edges_ns'])==len(row['detector_falling_edges_ns'])==2 else None


def bracket(rows):
    seen=set();dn=[];up=[];unknown=[]
    for row in rows:
        phase=row['phase_ps']
        if phase in seen:raise ValueError('duplicate loaded phase observation')
        seen.add(phase);role=decision(row['outputs'],row['first_synchronizers'])
        if role=='DN':dn.append(phase)
        elif role=='UP':up.append(phase)
        else:unknown.append(phase)
    ordered=bool(dn and up and max(dn)<min(up))
    return dict(observed_transition_bracket_ps=[max(dn),min(up)] if ordered else None,
        decisions=[dict(phase_ps=row['phase_ps'],decision=decision(row['outputs'],row['first_synchronizers'])) for row in sorted(rows,key=lambda r:r['phase_ps'])],
        unresolved_phase_points_ps=sorted(unknown),single_ordered_transition_observed=ordered,
        unresolved_points_not_forced_to_binary=True,qualified_uncertainty_bound=False)


def run(sources,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    pins={str(p):sha(p) for p in (Path(__file__).resolve(),Path(__file__).with_name('run_prototype_BBPD_mixed_slew.py'),Path(__file__).with_name('prototype_BBPD_guard_v2.py'),Path(__file__).with_name('review_prototype_BBPD_with_sync.py'))};results=[];seen=set()
    for source in sources:
        while not (source/'assessment.json').exists():
            o=json.loads((source/'owner.json').read_text())
            if identity(o['pid'])!=o['birth']:raise ValueError('loaded phase controller stopped without receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('loaded phase review deadline')
            time.sleep(1)
        receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if not r['all_declared_native_waveforms_complete'] or not r['first_sync_input_loads_included']:raise ValueError('completed loaded native source required')
        corner=r['corner']
        if corner not in ('tt','ff','ss','sf','fs') or corner in seen:raise ValueError('unique supported phase corner required')
        if (r['reference_full_ramp_ps'],r['divided_full_ramp_ps'])!=(200,1500):raise ValueError('declared mixed-slew point required')
        seen.add(corner);mp=source/'input_manifest.json';m=json.loads(mp.read_text());verify(m['input_sha256']);records=[]
        if (r['aggressor_phase_ps'],r['sync_clock_phase_ps'])!=(325,345):raise ValueError('matching loaded stress fixture required')
        obs=source/'observations.json';old=json.loads(obs.read_text())
        salvaged=set()
        for failure in old['failures']:
            if failure['phase_ps']!=-100 or failure['reason']!="ValueError('native input clock/phase/guard mismatch')":raise ValueError('native failure is not the identified endpoint observer error')
            salvaged.add(failure['phase_ps'])
        if old['failures'] or set(m['phase_ps'])!={-500,-250,0,250,500} or len(m['phase_ps'])!=5:raise ValueError('complete mixed-slew native matrix required')
        declared={row['phase_ps']:row for row in old['results']}
        for phase in m['phase_ps']:
            if phase not in (-500,-250,0,250,500):raise ValueError('declared mixed-slew phase grid required')
            log=source/f'phase_{phase}ps/native.log'
            if r['artifacts'].get(str(log))!=sha(log):raise ValueError('unbound loaded transition waveform')
            rows=read_table(log.read_text());a=measure([row[:8] for row in rows],phase);sync=sync_metrics(rows)
            if phase not in salvaged and (any(declared[phase][k]!=v for k,v in a.items()) or declared[phase]['first_synchronizers']!=sync):raise ValueError('loaded transition observations differ')
            slopes={}
            for column,role,expected in ((1,'REF',120),(2,'DIV',900)):
                lo=crossings([(row[0],row[column]) for row in rows],.36)[0]
                hi=crossings([(row[0],row[column]) for row in rows],1.44)[0]
                if min(len(lo),len(hi))<2:raise ValueError('two complete measured clock ramps required')
                values=[(b-a)*1e12 for a,b in zip(lo[:2],hi[:2])]
                if any(abs(v-expected)>1 for v in values):raise ValueError('measured input slew differs from declared fixture')
                slopes[role]=values
            records.append(dict(phase_ps=phase,outputs=a['outputs'],first_synchronizers=sync,measured_rise_20_to_80_ps=slopes));pins[str(log)]=sha(log)
        results.append(dict(corner=corner,observations=records,**bracket(records)));pins.update({str(p):sha(p) for p in (receipt,mp,obs)})
    if seen!={'tt','ff','ss','sf','fs'}:raise ValueError('all five loaded phase corners required')
    detail=output/'corners.json';save(detail,results);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},native_cases=sum(len(r['observations']) for r in results),
        all_corners_have_observed_transition=all(r['single_ordered_transition_observed'] for r in results),
        actual_first_sync_D_loads_and_wire_RC_included=True,measured_mixed_clock_slews_verified=True,reference_full_ramp_ps=200,divided_full_ramp_ps=1500,original_event_wire_quiet_screen_results_retained=True,
        omitted_loading_and_activity_uncertainty_bounded=False,diagnostic=True,native_interface_qualified=False,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sources',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run([p.resolve() for p in a.sources],a.output.resolve())
