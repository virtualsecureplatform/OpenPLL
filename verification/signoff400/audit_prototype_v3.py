"""Audit scoped prototype evidence without promoting historical qualification flags."""
import argparse
import json
import math
from pathlib import Path
from common import sha,verify,save

PROFILE=Path(__file__).with_name('requirements_v3.json')
CHECKS={
 'physical_integrity':{'drc','lvs','antenna','density','power_bulk_connectivity','device_parameters','electrical_rules'},
 'analog_models_and_tuning':{'passive_extraction','compatible_device_models','target_bracket','startup_headroom','native_interface_validation','independent_holdouts','numerical_convergence','uncertainty_included'},
 'digital_timing_and_cdc':{'setup_hold','recovery_removal','pulse_electrical','startup_frequency_coverage','all_crossings_reviewed','complete_interstage_paths'},
 'closed_loop_operation':{'native_correlated_models','uncertainty_holdouts','functional_limits','reference_phase_coverage'},
 'reproducible_handoff':{'complete_artifacts','portable_paths','clean_environment_replay','representative_native_replay','integration_contract'}}


def audit(manifest):
    profile=json.loads(PROFILE.read_text());candidate=manifest['candidate'];gates={};gains=set()
    for gate in profile['gates']:
        failures=[];covered=set();records=manifest.get('evidence',{}).get(gate,[])
        if not records:failures.append('missing direct prototype evidence')
        for entry in records:
            try:
                path=Path(entry['path'])
                if sha(path)!=entry['sha256']:raise ValueError('receipt hash mismatch')
                r=json.loads(path.read_text())
                if r.get('synthetic') or r.get('diagnostic') or r.get('status')!='pass':raise ValueError('nonpassing or diagnostic evidence')
                if r.get('profile_sha256')!=sha(PROFILE) or r.get('candidate')!=candidate:raise ValueError('candidate/profile mismatch')
                if not r.get('input_sha256') or not r.get('artifacts'):raise ValueError('native provenance required')
                verify(r['input_sha256']);verify(r['artifacts'])
                if r.get('gate')!=gate or r.get('validated_for_prototype') is not True:raise ValueError('wrong evidence scope')
                if not CHECKS[gate].issubset(r.get('checks',{})) or any(v is not True for v in r['checks'].values()):raise ValueError('required checks incomplete')
                if r.get('model_route') in profile['rejected_release_models']:raise ValueError('known invalid release model')
                if gate in ('analog_models_and_tuning','digital_timing_and_cdc','closed_loop_operation'):
                    point=(r['corner'],r['temperature_c'],r['supply_v'])
                    if point not in {(c,27,1.8) for c in profile['corners']} or point in covered:raise ValueError('duplicate/unsupported corner')
                    covered.add(point)
                if gate=='closed_loop_operation':
                    gains.add((r['ki'],r['kp']))
                    expected={(s,p) for s in profile['scenarios'] for p in profile['reference_phase_offsets_ns']}
                    cases=r['records']
                    if any(x.get('reference_phase_coverage_pass') is not True for x in cases):raise ValueError('reference phase coverage not demonstrated')
                    for case in cases:
                        initializations=case.get('reference_phase_initializations',[])
                        count=1 if case['scenario']=='cold_start' else 2
                        if [x['epoch'] for x in initializations]!=list(range(count)):raise ValueError('incomplete phase coordinate evidence')
                        for point in initializations:
                            reference,feedback=float(point['reference_ns']),float(point['feedback_ns'])
                            if not math.isfinite(reference) or not math.isfinite(feedback) or abs(reference-feedback-case['phase_offset_ns'])>.001:raise ValueError('phase coordinates do not realize requested offset')
                    if len(cases)!=12 or {(x['scenario'],x['phase_offset_ns']) for x in cases}!=expected or any(x.get('passed') is not True for x in cases):raise ValueError('incomplete functional matrix')
            except (ValueError,KeyError,TypeError,OSError) as error:failures.append(str(error))
        if gate in ('analog_models_and_tuning','digital_timing_and_cdc','closed_loop_operation') and len(covered)!=5:failures.append('five process corners at 27C required')
        gates[gate]=dict(status='fail' if failures else 'pass',failures=failures)
    if len(gains)!=1:
        gates['closed_loop_operation']['status']='fail'
        gates['closed_loop_operation']['failures'].append('one common gain pair required')
    identity=[]
    try:
        if not candidate.get('source_sha256') or not candidate.get('physical_sha256'):raise ValueError('frozen source and physical identity required')
        verify(candidate['source_sha256']);verify(candidate['physical_sha256'])
    except (ValueError,KeyError,OSError) as error:identity.append(str(error))
    return dict(release_level='prototype_tapeout_macro',profile_sha256=sha(PROFILE),gates=gates,
        identity_failures=identity,release_ready=not identity and all(g['status']=='pass' for g in gates.values()),production_qualified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('fresh output required')
    result=audit(json.loads(a.manifest.read_text()));save(a.output,result)
    print(json.dumps(result));raise SystemExit(0 if result['release_ready'] else 1)
