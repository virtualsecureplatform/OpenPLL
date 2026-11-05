#!/usr/bin/env python3
"""Execute one corner's 12 programmed-startup cases with identity-gated models.

Synthetic models are allowed only with --diagnostic and can never qualify.
"""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import time
from common_v3 import ROOT, PROFILE, RTL, source_pins, sha, save, spec, verify
from acceptance_v3 import evaluate
from resources import lease


def load_models(path, diagnostic):
    value=json.loads(path.read_text())
    if value['corner'] not in spec()['corners'] or value.get('temperature_c') not in spec()['temperatures_c'] or value.get('supply_v') != 1.8:
        raise ValueError('unsupported corner')
    if value['profile_sha256']!=sha(PROFILE):
        raise ValueError('model profile mismatch')
    verify(value['input_sha256'])
    current=source_pins()
    if any(value['candidate_source_sha256'].get(k)!=v for k,v in current.items()):
        raise ValueError('model candidate identity mismatch')
    if value['synthetic']:
        if not diagnostic:
            raise ValueError('synthetic models cannot qualify')
    else:
        if not value['candidate_physical_sha256']:
            raise ValueError('final physical candidate identity required')
        verify(value['candidate_physical_sha256'])
        for key,flag in [('dco_receipt','validated_for_prototype'),('interface_receipt','validated_for_prototype')]:
            receipt=Path(value[key])
            if str(receipt) not in value['input_sha256']:
                raise ValueError('unpinned model receipt')
            report=json.loads(receipt.read_text())
            if (report.get('diagnostic') or report.get('synthetic') or report.get('status')!='pass'
                    or report.get('gate')!='analog_models_and_tuning' or not report[flag] or report['corner']!=value['corner'] or report.get('temperature_c')!=value['temperature_c'] or report.get('supply_v')!=value['supply_v'] or report.get('profile_sha256')!=sha(PROFILE)):
                raise ValueError('unqualified physical model')
            if report['candidate']['physical_sha256']!=value['candidate_physical_sha256']:
                raise ValueError('physical model candidate mismatch')
            if report['candidate']['source_sha256']!=value['candidate_source_sha256']:
                raise ValueError('physical model source mismatch')
            from audit_prototype_v3 import CHECKS
            if not CHECKS['analog_models_and_tuning'].issubset(report.get('checks',{})) or any(v is not True for v in report['checks'].values()):
                raise ValueError('prototype analog evidence incomplete')
            if report.get('model_route') in spec()['rejected_release_models']:
                raise ValueError('known invalid analog model route')
            verify(report['input_sha256']);verify(report['artifacts'])
            artifact=value['dco_table' if key=='dco_receipt' else 'detector_rtl']
            if artifact not in report['artifacts']:
                raise ValueError('model artifact not covered by receipt')
    for key in ('dco_table','detector_rtl'):
        if value[key] not in value['input_sha256']:
            raise ValueError('unpinned model artifact')
    if not (0<=value['coarse']<=47 and 8<=value['seed']<=247 and value['polarity'] in (0,1)):
        raise ValueError('invalid startup preset')
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--models',required=True,type=Path)
    p.add_argument('--candidate',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--ki',required=True,type=int)
    p.add_argument('--kp',required=True,type=int)
    p.add_argument('--diagnostic',action='store_true')
    p.add_argument('--phase-zero-only',action='store_true')
    a=p.parse_args();started=time.monotonic();value=spec()
    if not a.diagnostic:p.error('unqualified physical models require explicit --diagnostic')
    if not(1<=a.ki<=255 and 0<=a.kp<=31):p.error('gain out of range')
    if a.phase_zero_only and not a.diagnostic:p.error('reduced matrix is diagnostic only')
    models=load_models(a.models.resolve(),a.diagnostic)
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    candidate=a.candidate.resolve(); receipt=candidate/'assessment.json'; cr=json.loads(receipt.read_text())
    verify(cr['artifacts'])
    sources=candidate/'sources.json'; definition=json.loads(sources.read_text())
    actual_rtl=[candidate/n for n in definition['files']]
    actual_pins={str(path):sha(path) for path in actual_rtl}
    if any(cr['candidate_source_sha256'].get(n)!=h for n,h in actual_pins.items()):raise ValueError('exact synthesized candidate sources required')
    verify(actual_pins)
    bench=ROOT/'tb/tb_programmed400_closed_loop.v'
    bridge=ROOT/'verification/timing400/phase_clock_vpi.cpp'
    pins=source_pins()
    pins.update(models['input_sha256']);pins.update(actual_pins);pins[str(sources)]=sha(sources);pins[str(receipt)]=sha(receipt)
    for path in (a.models.resolve(),bench,bridge,bridge.with_name('phase_clock.h'),
                 Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'),
                 Path(__file__).with_name('acceptance_v3.py'),
                 Path('/usr/bin/iverilog'),Path('/usr/bin/iverilog-vpi'),Path('/usr/bin/vvp')):
        pins[str(path)]=sha(path)

    def run(command,log):
        verify(pins)
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+max(.001,43200-(time.monotonic()-started))
        with lease(1,2,deadline), log.open('x') as stream:
            code=subprocess.run(list(map(str,command)),cwd=out,stdout=stream,
                stderr=subprocess.STDOUT,timeout=max(.001,43200-(time.monotonic()-started))).returncode
        return code

    assert run(['/usr/bin/iverilog-vpi',bridge],out/'vpi_compile.log')==0
    binary=out/'loop.vvp'
    assert run(['/usr/bin/iverilog','-g2012','-s','tb_programmed400_closed_loop','-o',binary,
                *actual_rtl,bench,models['detector_rtl']],out/'compile.log')==0
    records=[]
    phases=[0] if a.phase_zero_only else value['reference_phase_offsets_ns']
    for scenario,name in enumerate(value['scenarios']):
        for phase in phases:
            directory=out/f'{name}_phase{phase}';directory.mkdir()
            edges,control,segments=(directory/n for n in ('edges.csv','controls.csv','segments.csv'))
            code=run(['/usr/bin/vvp','-M',out,'-m','phase_clock_vpi',binary,
                f'+phase400_table={models["dco_table"]}',f'+phase400_trace={control}',
                f'+scenario={scenario}',f'+phase_ns={phase}',f'+coarse={models["coarse"]}',
                f'+seed={models["seed"]}',f'+polarity={models["polarity"]}',f'+ki={a.ki}',f'+kp={a.kp}',
                f'+edge_trace={edges}',f'+segment_trace={segments}'],directory/'run.log')
            record=dict(scenario=name,phase_offset_ns=phase,native_exit=code,segments=[],passed=False)
            if code==0 and 'PROGRAMMED400_LOOP_END' in (directory/'run.log').read_text():
                events={kind:[] for kind in ('REF','DIV','OUT')}
                for row in csv.DictReader(edges.open()):
                    events[row['event']].append([float(row['time_ns']),int(row['code']),int(row['bbpd'])])
                tunes=[]
                for row in csv.DictReader(control.open()):
                    if row['event']=='ERROR':raise ValueError('phase driver reported error')
                    if row['event']=='TUNE':tunes.append([int(row['time_ps'])/1000,int(row['fine'])])
                for segment in csv.DictReader(segments.open()):
                    result=evaluate(events,tunes,400,float(segment['enabled_ns']),float(segment['stop_ns']),value)
                    save(directory/('segment'+segment['segment']+'.json'),result)
                    record['segments'].append(dict(segment=int(segment['segment']),passed=result['passed']))
                record['passed']=len(record['segments'])==(1 if scenario==0 else 2) and all(s['passed'] for s in record['segments'])
            records.append(record)
            save(out/'status.json',dict(state='loop_cases_running',completed_cases=len(records),
                 passed_trace_cases=sum(r['passed'] for r in records),synthetic=models['synthetic'],
                 macro_handoff_qualified=False))
    verify(pins)
    complete=len(records)==12 and all(r['passed'] for r in records)
    save(out/'assessment.json',dict(input_sha256=pins,
         candidate_source_sha256=actual_pins,baseline_candidate_source_sha256=source_pins(),exact_synthesized_candidate_sources_executed=True,decision_register_clock_edge="falling",feedback_divider_constant_from_reset=16,related_clock_transfer_timing_qualified=False,candidate_physical_sha256=models.get('candidate_physical_sha256',{}),
         artifacts={str(path):sha(path) for path in out.rglob('*') if path.is_file() and path.name!='status.json'},
         corner=models['corner'],temperature_c=models['temperature_c'],supply_v=models['supply_v'],profile_sha256=sha(PROFILE),ki=a.ki,kp=a.kp,records=records,
         physical_models_qualified=False,all_trace_cases_passed=complete,
         prototype_trace_pass=False,experimental_trace_limits_passed=bool(complete),
         validated_for_prototype=False,uncertainty_holdouts_complete=False,release_ready=False,production_qualified=False,
         macro_handoff_qualified=False,release_qualified=False))
    save(out/'status.json',dict(state='loop_cases_completed',completed_cases=len(records),
         passed_trace_cases=sum(r['passed'] for r in records),synthetic=models['synthetic'],
         macro_handoff_qualified=False))
    print(json.dumps(records))


if __name__=='__main__':main()
