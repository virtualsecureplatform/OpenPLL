#!/usr/bin/env python3
"""Prepare60 model-gated cases and test the actual frozen candidate boundary."""
import argparse
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import subprocess

from run_dco_qualification import ROOT, REQUIREMENTS, sha, validate_spec

FROZEN = ROOT/'build/timing450/hs/closure/handoff_candidate/build/timing450/hs/rtl_snapshot'
FILES = ['IntegerPLL_AcquiringCore.v','IntegerPLL_DigitalCore.v','IntegerPLL_FrequencyAcquisition.v',
         'IntegerPLL_TuningHandoff.v','IntegerPLL_DLF.v','IntegerPLL_B2TH.v',
         'IntegerPLL_MMD_Retimer.v','IntegerPLL_Divider.v']


def cases_for(spec, targets):
    validate_spec(spec)
    if set(targets['targets']) != {str(m) for m in spec['modes_mhz']}:
        raise ValueError('presets contain stale/missing modes')
    cases = []
    for mode,corner,temp in itertools.product(spec['modes_mhz'],spec['corners'],spec['temperatures_c']):
        divider = targets['targets'][str(mode)]['ndiv']
        if divider != mode//spec['reference_mhz']:
            raise ValueError('incorrect divider preset')
        cases.append(dict(id=f'{mode}MHz_{corner}_1.8V_{temp}C',mode_mhz=mode,
            corner=corner,supply_v=1.8,temperature_c=temp,divider=divider,
            incoming_mode_changes_mhz=[m for m in spec['modes_mhz'] if m!=mode],
            acquisition_limit_ns=spec['acquisition_limit_ns'],sustained_windows=spec['sustained_windows'],
            window_ns=spec['window_ns'],frequency_error_ppm=spec['frequency_error_ppm'],
            phase_limits_output_periods={k:spec[k] for k in
                ['phase_span_output_periods','phase_mean_output_periods','phase_drift_output_periods']},
            status='BLOCKED_VALIDATED_DCO_AND_INTERFACE_MODELS',execution_eligible=False,passed=False))
    assert len(cases)==60 and len({c['id'] for c in cases})==60
    return cases


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    spec = json.loads(REQUIREMENTS.read_text())
    targets_path = ROOT/'sky130/release_400mhz_targets.json'
    cases = cases_for(spec,json.loads(targets_path.read_text()))
    out = a.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    harness = ROOT/'verification/timing450/IntegerPLL_ReleaseHarness.v'
    smoke = Path(__file__).with_name('tb_release400_smoke.v')
    inputs = [REQUIREMENTS,targets_path,Path(__file__),harness,smoke,*[FROZEN/f for f in FILES]]
    pins = {str(path):sha(path) for path in inputs}
    binary = out/'smoke.vvp'
    commands = [(['/usr/bin/iverilog','-g2012','-s','tb_release400_smoke','-o',str(binary),
                  *[str(FROZEN/f) for f in FILES],str(harness),str(smoke)],'compile.log'),
                (['/usr/bin/vvp',str(binary)],'smoke.log')]
    for argv,logname in commands:
        with (out/logname).open('x') as log:
            result = subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,timeout=43200)
        if result.returncode:
            raise RuntimeError(logname+' failed')
    assert 'PASS: all four supported modes' in (out/'smoke.log').read_text()
    for path,digest in pins.items():
        assert sha(path)==digest
    for path in (Path('/usr/bin/iverilog'),Path('/usr/bin/vvp'),binary,out/'compile.log',out/'smoke.log'):
        pins[str(path)]=sha(path)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),case_count=60,cases=cases,
        candidate_rtl=str(FROZEN),candidate_boundary_and_four_divider_smoke_pass=True,
        directed_mode_changes_per_pvt=12,sha256=pins,qualification_cases_passed=0,
        release_qualified=False,whole_pll_qualification_pass=False,
        required_before_execution=['Qualified DCO model for every lookup reached during acquisition/tracking; unknown lookups must stop execution',
                                   'Analog-correlated interface/reset/BBPD model with valid timing assumptions',
                                   'Phase-continuous driver validated against independently checked edge traces'],
        scope='Exact frozen candidate boundary and divider tests plus60 blocked cases. No acquisition/lock, interpolation, analog or release qualification.')
    (out/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','sha256')}))


if __name__=='__main__':
    main()
