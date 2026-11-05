#!/usr/bin/env python3
"""Fail-closed audit of matching 400 MHz hard-macro evidence."""
import argparse
import json
from pathlib import Path

from common_v2 import PROFILE, cases, save, sha, source_pins, spec, verify

FLAGS = dict(digital_startup='digital_startup_qualified', dco_model='dco_model_qualified',
             interfaces_reset_cdc='interface_model_qualified', whole_pll_lock='whole_pll_qualification_pass',
             digital_timing='digital_timing_qualified', physical_signoff='physical_signoff_qualified')
PVT_GATES = {'dco_model', 'interfaces_reset_cdc', 'whole_pll_lock', 'digital_timing'}


def validate_cdc(report):
    import math
    evidence = report['cdc_reliability']
    crossings = evidence['crossings']
    expected = evidence['expected_crossing_ids']
    inventory_ref = evidence['inventory']
    inventory_path = inventory_ref['path']
    if report['input_sha256'].get(inventory_path) != inventory_ref['sha256']:
        raise ValueError('CDC inventory must be pinned as an input')
    if sha(inventory_path) != inventory_ref['sha256']:
        raise ValueError('CDC inventory changed')
    inventory = json.loads(Path(inventory_path).read_text())
    if (inventory.get('complete_structural_inventory_qualified') is not True
            or inventory.get('candidate_source_sha256') != report['candidate_source_sha256']
            or inventory.get('candidate_physical_sha256') != report['candidate_physical_sha256']):
        raise ValueError('CDC inventory is incomplete or belongs to another candidate')
    entries = inventory['crossings']
    names = [c['id'] for c in entries]
    if (not all(isinstance(n, str) and n for n in names) or len(set(names)) != len(names)
            or any(c['scope'] not in ('command_and_reset_synchronizers', 'bbpd_decision_noise') for c in entries)):
        raise ValueError('invalid CDC inventory')
    required = {c['id'] for c in entries if c['scope'] == 'command_and_reset_synchronizers'}
    if not expected or len(set(expected)) != len(expected) or set(expected) != required:
        raise ValueError('missing/duplicate CDC crossing inventory')
    if len(crossings) != len(expected) or {c['id'] for c in crossings} != set(expected):
        raise ValueError('incomplete CDC crossing coverage')
    total = 0.0
    for c in crossings:
        for field in ('event_rate_upper_hz', 'failure_rate_upper_fit'):
            x = c[field]
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0:
                raise ValueError('invalid CDC upper bound')
        if c.get('characterization_artifact') not in report['artifacts']:
            raise ValueError('CDC characterization must be pinned')
        if not c.get('event_rate_basis') or not c.get('resolution_time_basis'):
            raise ValueError('missing CDC rate/timing justification')
        total += c['failure_rate_upper_fit']
    if total > spec()['cdc_reliability']['aggregate_max_fit']:
        raise ValueError('aggregate CDC reliability exceeds 1 FIT')


def receipt(path, expected_digest, candidate, flag):
    path=Path(path)
    if sha(path)!=expected_digest: raise ValueError('receipt hash mismatch: '+str(path))
    report=json.loads(path.read_text())
    if report.get('synthetic') or report.get('diagnostic') or report.get(flag) is not True:
        raise ValueError('receipt is diagnostic or lacks direct passing evidence: '+str(path))
    if report.get('profile_sha256')!=sha(PROFILE): raise ValueError('receipt profile mismatch')
    if report.get('candidate_source_sha256')!=candidate['source_sha256']:
        raise ValueError('receipt source mismatch')
    if report.get('candidate_physical_sha256')!=candidate['physical_sha256']:
        raise ValueError('receipt physical candidate mismatch')
    if not report.get('input_sha256') or not report.get('artifacts'):
        raise ValueError('receipt must pin native inputs and artifacts')
    verify(report['input_sha256']);verify(report['artifacts'])
    if flag == 'interface_model_qualified': validate_cdc(report)
    return report


def audit(manifest, require_handoff=True):
    value=spec();points={(c,t,1.8) for c in value['corners'] for t in value['temperatures_c']}
    candidate=manifest['candidate'];errors=[];gates={};gains=set()
    if candidate['source_sha256']!=source_pins(): errors.append('current candidate source/profile mismatch')
    if not candidate['physical_sha256']: errors.append('no frozen final physical candidate')
    try: verify(candidate['physical_sha256'])
    except (ValueError,OSError) as e: errors.append(str(e))
    for gate,flag in FLAGS.items():
        checked=[];covered=set();failed=[]
        records=manifest.get('evidence',{}).get(gate,[])
        if not records: failed.append('missing direct qualifying receipts')
        for entry in records:
            try:
                r=receipt(entry['path'],entry['sha256'],candidate,flag)
                if gate in PVT_GATES:
                    point=(r['corner'],r['temperature_c'],r['supply_v'])
                    if point not in points or point in covered: raise ValueError('duplicate/unsupported operating point')
                    covered.add(point)
                if gate=='whole_pll_lock':
                    expected={(c['scenario'],c['phase_offset_ns']) for c in cases()
                              if c['corner']==r['corner'] and c['temperature_c']==r['temperature_c']}
                    observed=[(c['scenario'],c['phase_offset_ns']) for c in r['records']]
                    if len(observed)!=12 or set(observed)!=expected or not all(c['passed'] is True and type(c['native_exit']) is int and c['native_exit']==0 for c in r['records']):
                        raise ValueError('incomplete closed-loop scenario coverage')
                    if (type(r['ki']) is not int or type(r['kp']) is not int
                            or r['ki'] not in value['gain_search']['ki']
                            or r['kp'] not in value['gain_search']['kp']):
                        raise ValueError('gain pair is outside the qualified search grid')
                    gains.add((r['ki'],r['kp']))
                checked.append(entry['path'])
            except (ValueError,KeyError,TypeError,OSError,OverflowError) as e:
                failed.append(f"{entry.get('path')}: {e}")
        if gate in PVT_GATES and covered!=points: failed.append(f'qualified PVT coverage {len(covered)}/15')
        gates[gate]=dict(passed=not failed, receipts=checked, failures=failed)
    if len(gains)!=1:
        gates['whole_pll_lock']['passed']=False
        gates['whole_pll_lock']['failures'].append('one common qualified KI/KP pair is required')
    if require_handoff:
        try:
            entry=manifest['handoff_receipt']
            receipt(entry['path'],entry['sha256'],candidate,'reproducible_handoff_qualified')
            gates['reproducible_handoff']=dict(passed=True,failures=[])
        except (ValueError,KeyError,TypeError,OSError) as e:
            gates['reproducible_handoff']=dict(passed=False,failures=[str(e)])
    passed=not errors and all(g['passed'] for g in gates.values())
    return dict(profile_sha256=sha(PROFILE),candidate_source_sha256=candidate['source_sha256'],
                candidate_physical_sha256=candidate['physical_sha256'],gates=gates,failures=errors,
                macro_handoff_qualified=passed and require_handoff,
                prerequisite_gates_passed=passed,release_qualified=passed and require_handoff)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('fresh audit output required')
    report=audit(json.loads(a.manifest.read_text()))
    report['input_sha256']={str(a.manifest.resolve()):sha(a.manifest),str(PROFILE):sha(PROFILE)}
    save(a.output,report)
    print(json.dumps(dict(release_qualified=report['release_qualified'],
                         gates={k:v['passed'] for k,v in report['gates'].items()})))
    return 0 if report['release_qualified'] else 1


if __name__=='__main__':raise SystemExit(main())
