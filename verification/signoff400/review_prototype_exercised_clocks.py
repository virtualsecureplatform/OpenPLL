"""Inventory delivered model clocks across the 105 retained loop diagnostics.

Observed model rates and code steps inform native validation; they are not a
physical startup, continuous uncertainty, or supported-clock-range certificate.
"""
import argparse
import csv
import json
from pathlib import Path
import time
from common_v3 import PROFILE,save,sha,verify
from resources import lease


def observe(rows,table):
    active=False;last_time=-1;previous=None;rising=None;tuning=None
    minimum_period=None;halves={0:None,1:None};codes=set();frequencies=set();step=0;edges=0
    for row in rows:
        kind=row['event'];now=int(row['time_ps']);level=int(row['level'])
        code=(int(row['coarse']),int(row['fine']));frequency=int(row['frequency_millihz'])
        if now<last_time or level not in (0,1):raise ValueError('invalid clock event ordering or level')
        last_time=now
        if kind=='RESET':
            active=False;previous=None;rising=None;tuning=None
            continue
        if kind not in ('TUNE','START','EDGE') or table.get(code)!=frequency or frequency<=0:
            raise ValueError('event frequency differs from the pinned model table')
        if kind=='TUNE':
            if tuning is not None and code[0]==tuning[0][0]:step=max(step,abs(code[1]-tuning[0][1]))
            active=True;tuning=(code,frequency)
            continue
        if not active or tuning!=(code,frequency):raise ValueError('delivered clock lacks matching active tuning')
        if kind=='START':continue
        if previous is not None:
            when,before=previous;duration=now-when
            if duration<=0 or level==before:raise ValueError('nonalternating or simultaneous clock edges')
            halves[before]=duration if halves[before] is None else min(halves[before],duration)
        previous=(now,level)
        if level==1:
            if rising is not None:
                period=now-rising;minimum_period=period if minimum_period is None else min(minimum_period,period)
            rising=now
        codes.add(code);frequencies.add(frequency);edges+=1
    if minimum_period is None or any(v is None for v in halves.values()) or not codes:
        raise ValueError('incomplete delivered clock observations')
    return dict(delivered_edges=edges,minimum_rising_period_ps=minimum_period,
        minimum_low_ps=halves[0],minimum_high_ps=halves[1],
        model_frequency_min_mhz=min(frequencies)/1e9,model_frequency_max_mhz=max(frequencies)/1e9,
        maximum_observed_cycle_rate_mhz=1e6/minimum_period,
        exercised_codes=[list(c) for c in sorted(codes)],maximum_programmed_fine_step=step)


def run(loops,output):
    profile=json.loads(PROFILE.read_text());inputs={str(PROFILE):sha(PROFILE),str(Path(__file__).resolve()):sha(Path(__file__).resolve()),
        str(Path(__file__).with_name('common_v3.py')):sha(Path(__file__).with_name('common_v3.py')),
        str(Path(__file__).with_name('resources.py')):sha(Path(__file__).with_name('resources.py'))}
    seen=set();results=[];sources=None;worker_flags=[]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
    with lease(1,4,deadline):
        for directory in loops:
            receipt=directory/'assessment.json';a=json.loads(receipt.read_text());verify(a['artifacts'])
            hold=a.get('dco_startup_hold_ps',0);corner=a['corner']
            if (a['profile_sha256']!=sha(PROFILE) or (a['ki'],a['kp'])!=(1,2)
                    or not a['exact_synthesized_candidate_sources_executed']
                    or hold not in (0,625,1250,1875)
                    or len(a['records'])!=(12 if hold==0 else 3)
                    or (hold==0 and not a['all_trace_cases_passed'])):
                raise ValueError('same-profile common-gain completed diagnostic required')
            # The shifted worker intentionally runs three cases; its retained
            # aggregate flag requires twelve. Inspect every case below and do
            # not rewrite that original full-matrix completion flag.
            worker_flags.append(dict(worker=str(directory),startup_hold_ps=hold,
                                     full_matrix_completion_flag=a['all_trace_cases_passed']))
            if sources is None:sources=a['candidate_source_sha256'];verify(sources)
            if a['candidate_source_sha256']!=sources:raise ValueError('mixed executed RTL sources')
            models=[Path(n) for n in a['input_sha256'] if n.endswith('/selected/models.json')]
            if len(models)!=1:raise ValueError('unique selected model definition required')
            model=models[0];m=json.loads(model.read_text());table=Path(m['dco_table'])
            if a['input_sha256'].get(str(model))!=sha(model) or a['input_sha256'].get(str(table))!=sha(table):
                raise ValueError('model/table provenance differs')
            values={}
            for line in table.read_text().splitlines():
                coarse,fine,frequency=map(int,line.split());key=(coarse,fine)
                if key in values:raise ValueError('duplicate model code')
                values[key]=frequency
            for record in a['records']:
                key=(corner,hold,record['scenario'],record['phase_offset_ns'])
                if key in seen or not record['passed'] or record['native_exit']!=0:raise ValueError('duplicate or failing diagnostic case')
                seen.add(key);control=directory/f'{record["scenario"]}_phase{record["phase_offset_ns"]}'/'controls.csv'
                if a['artifacts'].get(str(control))!=sha(control):raise ValueError('control trace changed')
                with control.open() as stream:measured=observe(csv.DictReader(stream),values)
                results.append(dict(corner=corner,startup_hold_ps=hold,scenario=record['scenario'],phase_offset_ns=record['phase_offset_ns'],**measured))
                inputs[str(control)]=sha(control)
            inputs.update({str(p):sha(p) for p in (receipt,model,table)})
        expected={(c,h,s,p) for c in profile['corners'] for h in (0,625,1250,1875)
                  for s in profile['scenarios'] for p in (profile['reference_phase_offsets_ns'] if h==0 else [0])}
        if seen!=expected:raise ValueError('complete distinct 105-case diagnostic matrix required')
        verify(inputs)
    output.mkdir(parents=True,exist_ok=False);detail=output/'cases.json';save(detail,results)
    summary={}
    for corner in profile['corners']:
        points=[r for r in results if r['corner']==corner];codes={tuple(c) for r in points for c in r['exercised_codes']}
        summary[corner]=dict(cases=len(points),model_frequency_min_mhz=min(r['model_frequency_min_mhz'] for r in points),
            model_frequency_max_mhz=max(r['model_frequency_max_mhz'] for r in points),
            minimum_rising_period_ps=min(r['minimum_rising_period_ps'] for r in points),
            minimum_high_ps=min(r['minimum_high_ps'] for r in points),minimum_low_ps=min(r['minimum_low_ps'] for r in points),
            fine_min=min(c[1] for c in codes),fine_max=max(c[1] for c in codes),
            maximum_programmed_fine_step=max(r['maximum_programmed_fine_step'] for r in points))
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(detail):sha(detail)},candidate_source_sha256=sources,
        completed_cases=len(results),ki=1,kp=2,by_corner=summary,
        source_worker_full_matrix_flags=worker_flags,
        delivered_edges_checked=sum(r['delivered_edges'] for r in results),
        native_final_parent_loading_included=False,physical_startup_clock_range_qualified=False,
        finite_model_observations_only=True,release_ready=False))
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--loop',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run([v.resolve() for v in a.loop],a.output.resolve())
