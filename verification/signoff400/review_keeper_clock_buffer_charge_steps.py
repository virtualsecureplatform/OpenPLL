"""Compare completed 2 ps and 1 ps clock-buffer charge measurements."""
import json
import math
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity


def compare(coarse,fine):
    def indexed(rows):
        result={}
        for r in rows:
            key=tuple(r[k] for k in ('corner','full_ramp_ps','output_load_fF'))
            if key in result:
                raise ValueError('duplicate charge fixture')
            if not r['input_levels_verified'] or not r['noninverting_response_verified']:
                raise ValueError('verified fixture response required')
            result[key]=r
        expected={(c,r,l) for c in ('tt','ff','ss','sf','fs') for r in (20,400,1600) for l in (0,100,400)}
        if result.keys()!=expected:
            raise ValueError('all 45 declared charge fixtures required')
        return result
    a,b=indexed(coarse),indexed(fine)
    rows=[]
    for key in sorted(a):
        row=dict(corner=key[0],full_ramp_ps=key[1],output_load_fF=key[2])
        for field in ('effective_20_80_capacitance_F','full_window_charge_C'):
            x,y=a[key][field],b[key][field]
            if len(x)!=2 or len(y)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in [*x,*y]):
                raise ValueError('positive finite charge/capacitance observations required')
            row[field+'_coarser_minus_finer_ppm']=[(v/w-1)*1e6 for v,w in zip(x,y)]
        components=b[key].get('deembedded_charge',{})
        if set(components)!={'rising_20_80','falling_80_20','rising_full','falling_full'}:
            raise ValueError('all observed deembedding windows required')
        row['deembedded_charge']=components
        rows.append(row)
    return rows


def run():
    base=ROOT/'build/signoff400'
    output=base/'selected_keeper_clock_charge_step_review_1528'
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{24})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    coarse=base/'selected_keeper_clock_buffer_charge_1526'
    fine=base/'selected_keeper_clock_buffer_charge_deembedded_1527'
    try:
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
        while True:
            state=json.loads((fine/'status.json').read_text())['state']
            if state=='native_clock_buffer_input_charge_measured':
                break
            if state=='stopped_without_qualification':
                raise RuntimeError('finer charge measurement stopped')
            owner=json.loads((fine/'owner.json').read_text())
            if identity(owner['pid'])!=owner['birth']:
                raise RuntimeError('measurement owner missing without completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
                raise TimeoutError('completed charge observation deadline')
            save(output/'status.json',dict(state='waiting_for_completed_1ps_charge_measurement',release_ready=False))
            time.sleep(10)
        pins={str(Path(__file__).resolve()):sha(Path(__file__).resolve())}
        values=[]
        for folder in (coarse,fine):
            receipt=folder/'assessment.json'
            a=json.loads(receipt.read_text())
            verify(a['input_sha256'])
            verify(a['artifacts'])
            values.append(a)
            pins.update({str(p):sha(p) for p in [receipt,folder/'plan.json',folder/'observations.json']})
        for name in ('cell.spice','explicit_input_capacitors.json'):
            if sha(coarse/name)!=sha(fine/name):
                raise ValueError('same cell and explicit input capacitances required')
        for folder,expected in ((coarse,2),(fine,1)):
            p=json.loads((folder/'plan.json').read_text())
            if p['maximum_step_ps']!=expected:
                raise ValueError('declared 2 ps and 1 ps measurements required')
        if values[1]['explicit_input_C_deembedding_complete'] is not True:
            raise ValueError('complete explicit input capacitor accounting required')
        rows=compare(*[json.loads((p/'observations.json').read_text()) for p in (coarse,fine)])
        detail=output/'comparisons.json'
        save(detail,rows)
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
             compared_fixtures=len(rows),coarse_step_ps=2,fine_step_ps=1,
             maximum_absolute_20_80_capacitance_difference_ppm=max(abs(v) for r in rows for v in r['effective_20_80_capacitance_F_coarser_minus_finer_ppm']),
             maximum_absolute_full_charge_difference_ppm=max(abs(v) for r in rows for v in r['full_window_charge_C_coarser_minus_finer_ppm']),
             same_extracted_cell_models=True,extra_internal_voltage_observation_added=True,
             finer_step_control_compared=True,frequency_error_bound_qualified=False,
             full_flat_C_stitching_qualified=False,causal_receiver_model_available=False,
             clock_receiver_model_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='completed_clock_buffer_charge_steps_compared',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise


if __name__=='__main__':
    run()
