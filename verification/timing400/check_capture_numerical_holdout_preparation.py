#!/usr/bin/env python3
"""Audit copied stimuli and isolated parameter changes; use synthetic bookkeeping."""
import json
from pathlib import Path
import re
from compile_local_C_operators_v2 import digest,save
from characterize_compact_propagation import SUPPLIES
from check_capture_boundary_observer import oracle
from run_compact_capture_boundaries_v2 import observe
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001';folder=base/'capture_numerical_holdouts_fs125_001'
master=json.loads((folder/'plan.json').read_text());assert len(master['cases'])==4
reference=None;checked_sources=0
identity_fields=('master','kind','offset_ps','ports','control_pin','reset_value','clock_center_ns','changing_input_center_ns','clock','data','control','pretest_value','changed_value','sentinel','sentinel_expected_final_value','full_clock_ramp_ps','full_changing_input_ramp_ps','external_load_pf')
for item in master['cases']:
    p=Path(item['plan']);assert digest(p)==item['plan_sha256'];plan=json.loads(p.read_text())
    assert len(plan['fixtures'])==72 and sum(c['sentinel'] for c in plan['fixtures'])==36 and plan['output_precision']==16
    lines=(p.parent/'batch.cir').read_text().splitlines()
    if reference is None:reference=lines
    else:
        changes=[(a,b) for a,b in zip(reference,lines,strict=True) if a!=b]
        assert len(changes)==1 and changes[0][0].startswith('.tran ' if item['label']=='timestep_only' else '.options timeint ')
    assert sum(line.startswith('.print tran FORMAT=STD PRECISION=16 ') for line in lines)==1
    for index,c in enumerate(plan['fixtures']):
        original=json.loads(Path(c['source_plan']).read_text())['fixtures'][c['source_case_index']]
        assert all(c[field]==original[field] for field in identity_fields)
        for channel,name in [('CLK','clock'),('D','data'),('R','control')]:
            selected=[line for line in lines if line.startswith(f'V{channel}_{index} ')]
            assert len(selected)==1
            match=re.fullmatch(r'V\w+ \w+ 0 PWL\((.*)\)',selected[0]);assert match
            tokens=match[1].split();assert len(tokens)%2==0
            actual=[]
            for t,v in zip(tokens[::2],tokens[1::2]):
                assert t.endswith('n');actual.append((float(t[:-1]),float(v)))
            assert len(actual)==len(c[name])
            assert all(abs(a[0]-b[0])<1e-10 and a[1]==b[1] for a,b in zip(actual,c[name]))
            checked_sources+=1
        aliases={**SUPPLIES,'CLK':f'CLK_{index}','D':f'D_{index}','Q':f'Q_{index}',c['control_pin']:f'R_{index}'}
        assert f'XDUT_{index} '+' '.join(aliases[pin] for pin in c['ports'])+' '+c['master'] in lines
        assert f'CLOAD_{index} Q_{index} 0 5f' in lines
baseline=json.loads(Path(master['cases'][0]['plan']).read_text());controls=0
for case in baseline['fixtures']:
    times,values=oracle(case);r=observe(times,values,case)
    if case['sentinel']:assert r['sentinel_passed'];controls+=1
assert controls==36 and checked_sources==864
out=base/'capture_numerical_holdout_preparation_checks_001';out.mkdir(exist_ok=False)
save(out/'assessment.json',dict(input_sha256={str(p):digest(p) for p in (Path(__file__).resolve(),folder/'plan.json',Path(__file__).with_name('check_capture_boundary_observer.py'),Path(__file__).with_name('run_compact_capture_boundaries_v2.py'))},
    native_PWL_sources_verified=checked_sources,source_fixture_identities_verified=288,single_parameter_deck_changes_verified=3,
    synthetic_observations=72,synthetic_separated_controls_passing=36,native_circuit_started=False,
    physical_timing_qualified=False,release_qualified=False))
print('Verified864 native PWL sources, isolated parameter changes and72 synthetic observations')
