"""Wait for target calibration, then run finite observed-frequency stress cases.

No native simulations are launched. Missing tuning coverage is retained rather
than extrapolated. Stress applicability and complete physical qualification stay
open; this is a fast controller sensitivity experiment.
"""
import argparse
import itertools
import json
import os
from pathlib import Path
import subprocess
import time
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compose_selected_diagnostic_registry import compose
from selected_model_registry import validate
from follow_selected_publication_matrix_v3 import result_record


def run(pipeline,composition,cache,packets,cpu,output,ki,kp):
    from common_v3 import spec
    grid=spec()["gain_search"]
    if ki not in grid["ki"] or kp not in grid["kp"]:raise ValueError("declared gain pair required")
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{cpu})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        owner = json.loads((pipeline/'owner.json').read_text())
        image = ROOT/'build/apptainer/openpll-release-modern.sif'
        worker = Path(__file__).with_name('run_selected_mixed_signal_v8.py')
        names = ('nominal','gain','offset','gain_offset')
        paths = [Path(__file__).resolve(),worker,image,pipeline/'owner.json',cache/'assessment.json',
            composition/'assessment.json',*(packets/(name+'.json') for name in names),
            *(Path(__file__).with_name(n) for n in ('common_v3.py','resources.py',
                'compose_selected_diagnostic_registry.py','selected_model_registry.py',
                'selected_dco_frequency_stress_v2.py','selected_mixed_signal_build_cache_v2.py',
                'follow_selected_publication_matrix_v3.py','acceptance_v4.py','selected_loop_assessment_v2.py'))]
        pins = {str(p):sha(p) for p in paths}
        save(output/'inputs.json',dict(input_sha256=pins,original_calibration_owner=owner,
            gain_pair=[ki,kp],finite_frequency_stress_scenarios=list(names),expected_cases=96,
            automatic_native_launch=False,automatic_identical_retry=False,release_ready=False))
        registry_path = pipeline/'selected_interface/models.json'
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+176400
        while not registry_path.exists():
            state = json.loads((pipeline/'status.json').read_text())['state']
            if state == 'stopped_without_qualification' or identity(owner['pid']) != owner['birth']:
                raise ValueError('original calibration stopped before its registry')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('calibration observation deadline; original native unchanged')
            save(output/'status.json',dict(state='waiting_for_original_target_calibration',release_ready=False))
            time.sleep(10)
        verify(pins)
        registry = output/'models.json'
        r = compose(registry_path,composition,registry)
        if r['analog']['operating_point'] != dict(corner='tt',temperature_c=27,supply_v=1.8):
            raise ValueError('observed stress scope is TT27C1.8V only')
        points = [p for p in r['points'] if p['coarse']==20]
        if not points:raise ValueError('measured coarse20 target family required')
        seed = min(points,key=lambda p:(abs(p['frequency_hz']-400e6),p['fine']))['fine']
        clock = Path(r['interface']['clock_timing'])
        pins.update({str(p):sha(p) for p in (registry_path,registry,clock,composition/'detector.v')})
        records = []
        for name,kind,scenario,phase in itertools.product(names,('linear_period','linear_frequency'),range(3),(0,10,20,30)):
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:raise TimeoutError('stress matrix budget exhausted')
            verify(pins)
            case = output/f'{name}_{kind}_scenario{scenario}_phase{phase}'
            command = ['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,
                '/usr/bin/python3',worker,'--registry',registry,'--detector',composition/'detector.v',
                '--clock-timing',clock,'--build-cache',cache,'--frequency-stress',packets/(name+'.json'),
                '--output',case,'--seed',seed,'--coarse',20,'--ki',ki,'--kp',kp,'--polarity',1,
                '--scenario',scenario,'--phase-ns',phase,'--interpolation',kind]
            save(output/'status.json',dict(state='diagnostic_frequency_stress_case_running',
                completed_cases=len(records),current_case=[name,kind,scenario,phase],release_ready=False))
            with lease(1,4,deadline):
                with (output/(case.name+'.log')).open('x') as log:
                    result = subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,
                        timeout=min(180,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
            assessment = case/'assessment.json'
            a = json.loads(assessment.read_text())
            if result.returncode not in (0,1,3) or a['release_ready'] is not False:
                raise ValueError('complete explicitly diagnostic case assessment required')
            checked=result_record(a,scenario,phase)
            case_inputs=case/'inputs.json';ci=json.loads(case_inputs.read_text());verify(ci['input_sha256'])
            if ci.get('compiled_build_reused')is not True or ci.get('runtime_namespace_checked_by_cache_loader')is not True or ci.get('build_cache')!=str(cache):raise ValueError('same verified shared RTL build required')
            records.append(dict(inputs=str(case_inputs),inputs_sha256=sha(case_inputs),reference_phase_coverage_pass=checked['reference_phase_coverage_pass'],stress=name,interpolation=kind,scenario=scenario,phase_ns=phase,
                assessment=str(assessment),assessment_sha256=sha(assessment),state=a['state'],
                functional_trace_pass=checked['functional_trace_pass'],measurement_requests=a['measurement_requests']))
        verify(pins)
        expected=set(itertools.product(names,('linear_period','linear_frequency'),range(3),(0,10,20,30)))
        observed={(r['stress'],r['interpolation'],r['scenario'],r['phase_ns'])for r in records}
        if observed!=expected or len(records)!=96:raise ValueError('complete unique frozen stress matrix required')
        detail = output/'cases.json';save(detail,records)
        artifacts={str(detail):sha(detail)}
        artifacts.update({r['assessment']:r['assessment_sha256']for r in records})
        artifacts.update({r['inputs']:r['inputs_sha256']for r in records});verify(artifacts)
        missing = sorted({(p['coarse'],p['fine']) for row in records for p in row['measurement_requests']})
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
            acceptance_statistics='exact_integer_ps_rational_on_uniform_grid',
            expected_cases=96,completed_cases=len(records),seed=seed,gain_pair=[ki,kp],
            all_finite_cases_functional=all(r['functional_trace_pass'] for r in records),
            needed_native_points=[dict(coarse=c,fine=f) for c,f in missing],
            full_60_case_five_corner_matrix=False,common_gain_pair_selected=False,
            wide_code_stress_applicability_qualified=False,physical_models_qualified=False,
            lock_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='diagnostic_frequency_stress_matrix_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),
            original_calibration_and_native_jobs_unchanged=True,release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('pipeline','composition','cache','packets','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--cpu',type=int,choices=(23,24),required=True)
    p.add_argument('--ki',type=int,required=True);p.add_argument('--kp',type=int,required=True)
    a = p.parse_args();run(a.pipeline.resolve(),a.composition.resolve(),a.cache.resolve(),a.packets.resolve(),a.cpu,a.output.resolve(),a.ki,a.kp)
