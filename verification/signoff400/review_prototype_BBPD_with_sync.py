"""Independently review the detector, wire network and loaded first synchronizer captures."""
import argparse
import json
from pathlib import Path
import time
from common_v3 import save,sha,verify
from resources import identity
from run_prototype_BBPD_with_sync import read_table
from review_prototype_BBPD_corrected_waveforms import measure
from assess_prototype_native_waveform import crossings


def sync_metrics(rows):
    results={}
    for role,source_column,output_column in (('DN',6,8),('UP',7,9)):
        def events(column):
            rise,fall=crossings([(r[0],r[column]) for r in rows],.9)
            return sorted([(t,'rise') for t in rise if 5e-9<=t<=85e-9]+[(t,'fall') for t in fall if 5e-9<=t<=85e-9])
        source,output=events(source_column),events(output_column)
        quiet=[r[output_column] for r in rows if 5e-9<=r[0]<=8e-9]
        matched=len(source)==len(output) and all(d==e and 0<=b-a<=5e-9 for (a,d),(b,e) in zip(source,output))
        results[role]=dict(quiet_output_voltage_interval_v=[min(quiet),max(quiet)],quiet_output_low_rail_screen_pass=max(quiet)<.18,
            source_events=len(source),captured_events=len(output),one_delayed_capture_per_source_toggle_observed=matched)
    return results


def run(sources,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    pins={str(p):sha(p) for p in (Path(__file__).resolve(),Path(__file__).with_name('run_prototype_BBPD_with_sync.py'),Path(__file__).with_name('review_prototype_BBPD_corrected_waveforms.py'),Path(__file__).with_name('assess_prototype_native_waveform.py'))};records=[];seen=set()
    for source in sources:
        while not (source/'assessment.json').exists():
            owner=json.loads((source/'owner.json').read_text())
            if identity(owner['pid'])!=owner['birth']:raise ValueError('extended receiver stopped without receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('extended receiver review deadline')
            time.sleep(1)
        receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if not r.get('all_declared_native_waveforms_complete') or not r.get('first_sync_input_loads_included') or r['geometry_model']!='signal':raise ValueError('completed corrected loaded receiver required')
        corner=r['corner']
        if corner in seen or corner not in ('tt','ff','ss','sf','fs'):raise ValueError('duplicate/unsupported receiver corner')
        seen.add(corner)
        if r['aggressor_phase_ps']!=325 or r['sync_clock_phase_ps']!=345 or r['sync_Q_load_fF']!=20:raise ValueError('declared peak-aligned receiver fixture required')
        manifest=source/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
        if set(m['phase_ps'])!={-1000,0,1000} or len(m['phase_ps'])!=3:raise ValueError('complete three-phase grid required')
        observed=source/'observations.json';old=json.loads(observed.read_text())
        if old['failures'] or len(old['results'])!=3:raise ValueError('native failures cannot be concealed by review')
        declared={row['phase_ps']:row for row in old['results']}
        for phase in m['phase_ps']:
            log=source/f'phase_{phase}ps/native.log'
            if r['artifacts'].get(str(log))!=sha(log):raise ValueError('unbound native loaded waveform')
            rows=read_table(log.read_text());detector=measure([row[:8] for row in rows],phase);sync=sync_metrics(rows)
            if any(declared[phase][k]!=v for k,v in detector.items()) or declared[phase]['first_synchronizers']!=sync:raise ValueError('loaded receiver observation differs')
            quiet=[row for row in rows if 5e-9<=row[0]<=8e-9]
            records.append(dict(corner=corner,phase_ps=phase,first_synchronizers=sync,
                event_wire_quiet_peak_V={role:max(row[column] for row in quiet) for role,column in (('DN',6),('UP',7))},
                detector_to_event_capture=detector['outputs']))
            pins[str(log)]=sha(log)
        pins.update({str(p):sha(p) for p in (receipt,manifest,observed)})
    if seen!={'tt','ff','ss','sf','fs'}:raise ValueError('five loaded receiver corners required')
    detail=output/'observations.json';save(detail,records);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},complete_native_cases=len(records),
        first_sync_D_loads_and_wire_RCs_included=True,
        all_quiet_sync_outputs_at_low_rail=all(s['quiet_output_low_rail_screen_pass'] for r in records for s in r['first_synchronizers'].values()),
        all_sync_event_captures_match=all(s['one_delayed_capture_per_source_toggle_observed'] for r in records for s in r['first_synchronizers'].values()),
        other_receiver_pin_loads_bounded=False,sync_clock_tree_RC_included=False,parent_and_fill_coupling_included=False,
        actual_sequencer_timing_included=False,phase_and_activity_continuum_covered=False,
        diagnostic=True,native_interface_qualified=False,validated_for_prototype=False,release_ready=False))
    print('Reviewed five-corner loaded receiver captures:',len(records))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sources',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run([p.resolve() for p in a.sources],a.output.resolve())
