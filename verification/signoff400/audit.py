#!/usr/bin/env python3
"""Fail-closed audit of matching 400 MHz hard-macro evidence."""
import argparse
import json
from pathlib import Path

from common import PROFILE, cases, save, sha, source_pins, spec, verify

FLAGS = dict(digital_startup='digital_startup_qualified', dco_model='dco_model_qualified',
             interfaces_reset_cdc='interface_model_qualified', whole_pll_lock='whole_pll_qualification_pass',
             digital_timing='digital_timing_qualified', physical_signoff='physical_signoff_qualified')
PVT_GATES = {'dco_model', 'interfaces_reset_cdc', 'whole_pll_lock', 'digital_timing'}


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
                    if len(observed)!=12 or set(observed)!=expected or not all(c['passed'] and c['native_exit']==0 for c in r['records']):
                        raise ValueError('incomplete closed-loop scenario coverage')
                    gains.add((r['ki'],r['kp']))
                checked.append(entry['path'])
            except (ValueError,KeyError,TypeError,OSError) as e:
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
