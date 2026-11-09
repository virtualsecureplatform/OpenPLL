"""Diagnostic selected-RTL simulation with static tuning points, explicit case arguments and complete trace hashes.

Interpolate only within native tuning knots; unsupported codes request measurement.
Interpolated rows are explicit estimates, with no qualified frequency-error bound.
Detector timing is explicitly supplied and unqualified; this runner never signs off.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import subprocess
import time
from common_v3 import ROOT, sha, save, verify
from selected_physical_rtl import source_pins


from selected_static_DCO_point import measured_point,point_pins


def run(receipts,detector,output,ki=4,kp=0,coarse=20,seed=111,polarity=1,scenario=0,phase_ns=0,registry_path=None,clock_timing_path=None,interpolation_kind='linear_period',build_cache=None,frequency_stress_path=None):
    if clock_timing_path is None:raise ValueError('explicit clock timing packet required')
    from selected_clock_timing import load,arguments
    timing=load(clock_timing_path)
    if timing['operating_point']!={'corner':'tt','temperature_c':27,'supply_v':1.8}:raise ValueError('static subsystem points currently support TT27C1.8V only')
    points={}
    for receipt in receipts:
        c,f,mhz=measured_point(receipt)
        if (c,f) in points:raise ValueError('duplicate measured code')
        points[c,f]=mhz
    if (coarse,seed) not in points:raise ValueError('measured startup point required')
    if scenario not in (0,1,2) or phase_ns not in (0,10,20,30) or polarity not in (0,1):raise ValueError('unsupported case')
    if not 1<=ki<=255 or not 0<=kp<=31:raise ValueError('invalid gains')
    output.mkdir(parents=True,exist_ok=False)
    from selected_frequency_interpolation import build
    dense,curve=build(points,interpolation_kind)
    stress_record=None
    if frequency_stress_path is not None:
        if registry_path is None:raise ValueError('frequency stress requires an explicit model registry')
        from selected_dco_frequency_stress_v2 import apply
        dense,stress_record=apply(dense,points,registry_path,frequency_stress_path)
        save(output/'frequency_stress.json',stress_record)
    curve_path=output/'dco_frequency_model.json';save(curve_path,curve)
    pins=source_pins();pins.update(point_pins(receipts));pins[str(curve_path)]=sha(curve_path);pins[str(ROOT/'verification/signoff400/selected_frequency_interpolation.py')]=sha(ROOT/'verification/signoff400/selected_frequency_interpolation.py');pins.update({str(p):sha(p) for p in [*receipts,detector,Path(__file__).resolve(),ROOT/'tb/tb_programmed400_closed_loop_reset80.v',ROOT/'verification/timing400/phase_clock_vpi.cpp',ROOT/'verification/timing400/phase_clock.h',ROOT/'verification/signoff400/selected_loop_assessment_v4.py',ROOT/'verification/signoff400/acceptance_v5.py',ROOT/'verification/signoff400/requirements_v4.json',ROOT/'verification/signoff400/selected_model_registry.py',ROOT/'verification/signoff400/common_v3.py',clock_timing_path,ROOT/'verification/signoff400/selected_clock_timing.py',ROOT/'tb/Prototype400ClockTiming.v',ROOT/'tb/Prototype400ReferencePhase.v',ROOT/'verification/signoff400/selected_reference_phase.py']})
    if registry_path:
        from selected_model_registry import validate
        registry=validate(json.loads(registry_path.read_text()))
        timing=load(clock_timing_path,registry)
        pins[str(registry_path)]=sha(registry_path)
        for key in ['analog','interface']:pins.update(registry[key]['input_sha256'])
    table=output/'dco_table.txt';table.write_text(''.join(f'{c} {f} {v}\n' for (c,f),v in sorted(dense.items())))
    pins[str(table)]=sha(table)
    save(output/'inputs.json',dict(input_sha256=pins,case_arguments=dict(ki=ki,kp=kp,coarse=coarse,seed=seed,polarity=polarity,scenario=scenario,phase_ns=phase_ns),measured_points=[dict(coarse=c,fine=f,frequency_millihertz=v) for (c,f),v in points.items()],frequency_table_kind=('diagnostic_affine_stress_after_'+interpolation_kind if stress_record is not None else interpolation_kind),interpolated_points=len(curve['interpolated_points']),frequency_error_bound_qualified=False,clock_timing_sha256=sha(clock_timing_path),phase_observation_boundary='physical_divided_output',RTL_source_scope='exact bytes bound by selected filled physical layout',native_point_scope='unqualified static subsystem, native20–60 ns window',clock_timing_qualified=False,detector_qualified_for_selected_layout=False,diagnostic=True,minimum_reset_assertion_ns=80,release_ready=False))
    if stress_record is not None:
        pins.update(stress_record['input_sha256']);pins[str(output/'frequency_stress.json')]=sha(output/'frequency_stress.json')
        save(output/'inputs.json',dict(json.loads((output/'inputs.json').read_text()),input_sha256=pins,frequency_stress=stress_record,measured_frequency_knots_overwritten=False))
    cache_pins={}
    if build_cache is not None:
        from selected_mixed_signal_build_cache_v3 import load as load_build
        cache_all_pins=load_build(build_cache,detector)
        cache_pins={p:d for p,d in cache_all_pins.items()if Path(p).is_relative_to(ROOT)}
        namespace_pins={p:d for p,d in cache_all_pins.items()if p not in cache_pins}
        pins.update(cache_pins)
        save(output/'inputs.json',dict(json.loads((output/'inputs.json').read_text()),input_sha256=pins,compiled_build_reused=True,build_cache=str(build_cache),runtime_namespace_sha256=namespace_pins,runtime_namespace_checked_by_cache_loader=True))
    elapsed=time.monotonic()
    def execute(command,name):
        with (output/name).open('w') as log:
            return subprocess.run(list(map(str,command)),cwd=output,stdout=log,stderr=subprocess.STDOUT,timeout=60).returncode
    compiled=build_cache if build_cache is not None else output
    if build_cache is None:
        bridge=ROOT/'verification/timing400/phase_clock_vpi.cpp'
        if execute(['/usr/bin/iverilog-vpi',bridge],'vpi_compile.log')!=0:raise RuntimeError('VPI compilation failed')
        source=list(source_pins());rtl=[p for p in source if p.endswith('.v') and not p.endswith('IntegerPLL_400MHz_PrototypeTop.v')]
        if execute(['/usr/bin/iverilog','-g2012','-s','tb_programmed400_closed_loop','-o',output/'loop.vvp',*rtl,ROOT/'tb/tb_programmed400_closed_loop_reset80.v',ROOT/'tb/Prototype400ClockTiming.v',ROOT/'tb/Prototype400ReferencePhase.v',detector],'compile.log')!=0:raise RuntimeError('RTL compilation failed')
    code=execute(['/usr/bin/vvp','-M',compiled,'-m','phase_clock_vpi',compiled/'loop.vvp',f'+phase400_table={table}',f'+phase400_trace={output/"controls.csv"}',f'+scenario={scenario}',f'+phase_ns={phase_ns}',f'+coarse={coarse}',f'+seed={seed}',f'+polarity={polarity}',f'+ki={ki}',f'+kp={kp}',f'+edge_trace={output/"edges.csv"}',f'+segment_trace={output/"segments.csv"}',*arguments(timing)],'run.log')
    log=(output/'run.log').read_text();requests=[]
    if 'MODEL_LOOKUP_MISSING' in log:
        with (output/'controls.csv').open() as stream:
            for row in csv.DictReader(stream):
                if row['event']=='ERROR':requests.append(dict(coarse=int(row['coarse']),fine=int(row['fine'])))
    verify(pins)
    if build_cache is not None and load_build(build_cache,detector)!=cache_all_pins:raise ValueError('cache or runtime namespace changed during simulation')
    report=dict(diagnostic_frequency_stress_applied=stress_record is not None,state='needs_native_tuning_points' if requests else ('diagnostic_simulation_completed' if code==0 and 'PROGRAMMED400_LOOP_END' in log else 'diagnostic_failed'),elapsed_s=time.monotonic()-elapsed,compiled_build_reused=build_cache is not None,frequency_table_kind=('diagnostic_affine_stress_after_'+interpolation_kind if stress_record is not None else interpolation_kind),interpolated_points=len(curve['interpolated_points']),frequency_error_bound_qualified=False,clock_timing_applied=True,phase_observation_boundary='physical_divided_output',clock_timing_qualified=False,native_exit=code,terminal_marker_present='PROGRAMMED400_LOOP_END' in log,measurement_requests=requests,scenario=scenario,phase_offset_ns=phase_ns,diagnostic=True,physical_models_qualified=False,lock_qualified=False,release_ready=False)
    from selected_loop_assessment_v4 import assess
    report.update(assess(output,code,scenario))
    from selected_reference_phase import assess as assess_phase
    phase_result=assess_phase(output,scenario,phase_ns)
    save(output/'reference_phase.json',phase_result)
    report.update(phase_result)
    report['functional_trace_pass']=report['functional_trace_pass'] and phase_result['reference_phase_coverage_pass']
    if not requests and not report['functional_trace_pass']:report['state']='diagnostic_failed'
    pins[str(output/'inputs.json')]=sha(output/'inputs.json')
    report['input_sha256']=pins
    report['artifacts']={str(p):sha(p) for p in output.iterdir() if p.is_file() and p.name!='assessment.json'}
    save(output/'assessment.json',report);print(json.dumps(report));return report


def exit_status(report):
    if report.get('state')=='needs_native_tuning_points':return 3
    if (report.get('state')=='diagnostic_simulation_completed' and report.get('functional_trace_pass') and report.get('native_exit')==0 and report.get('terminal_marker_present')):return 0
    return 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    inputs=p.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--point',type=Path,action='append')
    inputs.add_argument('--registry',type=Path)
    p.add_argument('--detector',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--clock-timing',type=Path,required=True)
    p.add_argument('--interpolation',choices=['linear_period','linear_frequency'],default='linear_period')
    p.add_argument('--ki',type=int,default=4);p.add_argument('--kp',type=int,default=0)
    p.add_argument('--coarse',type=int,default=20);p.add_argument('--seed',type=int,default=111)
    p.add_argument('--polarity',type=int,choices=(0,1),default=1)
    p.add_argument('--scenario',type=int,choices=(0,1,2),default=0)
    p.add_argument('--phase-ns',type=int,choices=(0,10,20,30),default=0)
    p.add_argument('--build-cache',type=Path)
    p.add_argument('--frequency-stress',type=Path)
    a=p.parse_args()
    if a.registry:
        from selected_model_registry import validate
        registry=validate(json.loads(a.registry.read_text()))
        if registry['interface']['input_sha256'].get(str(a.detector.resolve()))!=sha(a.detector.resolve()):p.error('detector does not match registry interface')
        a.point=[Path(row['receipt']) for row in registry['points']]
    report=run([r.resolve() for r in a.point],a.detector.resolve(),a.output.resolve(),a.ki,a.kp,a.coarse,a.seed,a.polarity,a.scenario,a.phase_ns,a.registry.resolve() if a.registry else None,a.clock_timing.resolve(),a.interpolation,a.build_cache.resolve()if a.build_cache else None,a.frequency_stress.resolve()if a.frequency_stress else None)

    raise SystemExit(exit_status(report))
