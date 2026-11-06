"""Compare neighboring-code native tuning increments with recorded histories.

Requires identical circuits, solver settings, observations and quiet boundaries.
Each code retains its own native programming/reset history; no frequency offset
or slope is fitted. This sampled diagnostic is not a uniform model qualification.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import time

from common_v3 import save, sha, verify
from resources import identity
from audit_selected_dco_history_inputs import sources
from selected_spice_device_conditions import matching
from selected_native_clock_shapes import load


def increments(first, second):
    records=[]
    for window in ('common','early','late'):
        a,b=[x['frequency_comparisons'][window] for x in (first,second)]
        if a['window_after_first_rise_ns'] != b['window_after_first_rise_ns']:
            raise ValueError('matching oscillator-age windows required')
        if a['window_after_first_rise_ns'] not in ([10,40],[10,25],[25,40]):
            raise ValueError('complete declared 10--40 ns common-age coverage required')
        values=[x[k]['frequency_mhz'] for x in (a,b) for k in ('candidate','full_native')]
        if not all(math.isfinite(v) and v>0 for v in values):raise ValueError('finite positive measured frequencies required')
        reduced=b['candidate']['frequency_mhz']-a['candidate']['frequency_mhz']
        full=b['full_native']['frequency_mhz']-a['full_native']['frequency_mhz']
        if min(reduced,full)<=0:raise ValueError('positive independently measured tuning increments required')
        records.append(dict(window=window,oscillator_age_ns=a['window_after_first_rise_ns'],
            reduced_increment_mhz=reduced,full_increment_mhz=full,
            increment_error_percent=100*(reduced/full-1),fine111_error_ppm=a['difference_ppm'],fine112_error_ppm=b['difference_ppm']))
    return records


def run(base,target,first,second,inventory,output,wait=False):
    os.sched_setaffinity(0,{31});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    owners=[json.loads((d/'owner.json').read_text()) for d in (base,target)]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12600
    try:
        while not (first.exists() and second.exists()):
            if not wait:raise ValueError('terminal native comparison receipts required')
            for directory,path,owner in zip((base,target),(first,second),owners):
                if path.exists():continue
                status=json.loads((directory/'status.json').read_text())
                live=status['state'] in ('preparing_real_driver_DCO_diagnostic','real_driver_DCO_native_running')
                if live and identity(owner['pid'])!=owner['birth']:raise RuntimeError('original controller disappeared without terminal assessment')
                if not live and status['state'] not in ('real_driver_DCO_diagnostic_complete','stopped_without_qualification'):
                    raise ValueError('unexpected original native state')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('comparison observation deadline; native jobs unchanged')
            save(output/'status.json',dict(state='waiting_for_original_history_code_comparisons',release_ready=False));time.sleep(10)
        a,b=[json.loads(p.read_text())for p in (first,second)]
        bm,tm=[json.loads((d/'manifest.json').read_text())for d in (base,target)]
        iv=json.loads(inventory.read_text())
        for x in (a,b,bm,tm,iv):verify(x['input_sha256'])
        for x in (a,b):
            if not (x.get('normal_full_window_completed') or x.get('native_budget_stopped')):raise ValueError('terminal native assessment required')
            if x.get('expected_end_ns')!=260:raise ValueError('declared 260 ns histories required')
        if (a['coarse'],a['fine'],b['coarse'],b['fine'])!=(20,111,20,112):raise ValueError('independent native 111/112 code pair required')
        if (base/'devices.spice').read_bytes()!=(target/'devices.spice').read_bytes() or bm['observed_roles']!=tm['observed_roles']:
            raise ValueError('identical physical network and observation nodes required')
        def canonical(directory):
            s=(directory/'control.spice').read_text()
            for name in ('devices.spice','sources.spice','control.raw'):
                path=str(directory/name)
                if s.count(path)!=1:raise ValueError('unique native file reference required')
                s=s.replace(path,'<'+name+'>')
            expected='.tran 10p 260n {schedule(0,1n,100n,10p,112n,1n,175n,10p)}'
            if s.splitlines().count(expected)!=1:raise ValueError('same declared native timestep schedule required')
            return s
        if canonical(base)!=canonical(target):raise ValueError('solver or physical model settings differ')
        conditions=matching(base/'control.spice',target/'control.spice')
        if conditions.get('corner')!='tt':raise ValueError('same TT physical conditions required')
        history_nodes={r['driver_input_node'] for r in iv['controls'].values()}|{bm['observed_roles']['reset_driver_input']}
        x,y=[sources(d/'sources.spice')for d in (base,target)]
        if x.keys()!=y.keys() or any(x[n]!=y[n]for n in x.keys()-history_nodes):raise ValueError('quiet boundary sources differ')
        for directory,manifest,fine in ((base,bm,111),(target,tm,112)):
            if manifest['controls']['coarse']!=20 or manifest['controls']['fine']!=fine:raise ValueError('candidate declared code differs')
            hr=json.loads((directory/'history_sources/assessment.json').read_text());verify(hr['input_sha256'])
            actual=sources(directory/'sources.spice')
            for role,record in hr['sources'].items():
                node=record['node'];limit=1e-6 if role=='DCO_reset_driver_input' else 1e-3
                if record['uniform_voltage_bound_V']!=limit or record['maximum_voltage_difference_V']>limit or not record['union_knot_voltage_certificate']:
                    raise ValueError('complete explicit source-voltage certificates required')
                match=re.fullmatch(r'PWL FILE "([^"]+)"',actual[node][1])
                if match is None:raise ValueError('actual recorded PWL source required')
                path=Path(match[1])
                if hr['input_sha256'].get(str(path))!=sha(path):raise ValueError('actual bounded source not certified')
                last=load(path)[-1][1]
                if role=='DCO_reset_driver_input':expected=1.8
                else:
                    if node!=iv['controls'][role]['driver_input_node']:raise ValueError('physical programming input binding differs')
                    index=int(role.split('[')[1][:-1])
                    expected=1.8 if (index<fine if role.startswith('DCO_THERM[') else index>=20) else 0
                if abs(last-expected)>.01:raise ValueError('actual final recorded programming code differs')
            if {r['node']for r in hr['sources'].values()}!=history_nodes:raise ValueError('exactly 303 independent history channels required')
        records=increments(a,b)
        paths=[first,second,inventory,Path(__file__).resolve()]
        paths += [Path(__file__).with_name(n)for n in ('common_v3.py','resources.py','audit_selected_dco_history_inputs.py','selected_spice_device_conditions.py','selected_native_clock_shapes.py')]
        paths += [d/n for d in (base,target)for n in ('manifest.json','devices.spice','sources.spice','control.spice','history_sources/assessment.json')]
        pins={str(p):sha(p)for p in paths};verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,records=records,
            same_reduced_physical_circuit=True,same_solver_and_quiet_boundaries=True,
            independently_recorded_programming_and_reset_histories=True,
            constant_frequency_offset_or_slope_fit_applied=False,
            normal_full_windows_completed=all(x['normal_full_window_completed']for x in (a,b)),
            native_budget_stopped=any(x['native_budget_stopped']for x in (a,b)),
            tuning_curve_qualified=False,uniform_uncertainty_bound_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='history_code_pair_increment_assessed',release_ready=False));print(json.dumps(records))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('base','target','first','second','inventory','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--wait',action='store_true');a=p.parse_args()
    run(*(getattr(a,n).resolve()for n in ('base','target','first','second','inventory','output')),a.wait)
