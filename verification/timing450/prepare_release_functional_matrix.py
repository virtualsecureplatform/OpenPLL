#!/usr/bin/env python3
"""Prepare 75 model-gated cases using the frozen physical candidate RTL."""
import argparse
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT/'build/timing450/hs/closure/handoff_candidate/build/timing450/hs/rtl_snapshot'
FILES = ['IntegerPLL_AcquiringCore.v','IntegerPLL_DigitalCore.v','IntegerPLL_FrequencyAcquisition.v',
         'IntegerPLL_TuningHandoff.v','IntegerPLL_DLF.v','IntegerPLL_B2TH.v',
         'IntegerPLL_MMD_Retimer.v','IntegerPLL_Divider.v']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists()
    here = Path(__file__).resolve().parent
    reqpath = ROOT/'verification/release_requirements.json'
    spec = json.loads(reqpath.read_text())
    assert spec['voltages']==[1.8]
    inputs = [reqpath,Path(__file__).resolve(),here/'IntegerPLL_ReleaseHarness.v',
              here/'tb_release_harness_smoke.v',*[FROZEN/name for name in FILES]]
    pins = {str(p):sha(p) for p in inputs}
    # The unselected root RTL differs from the routed candidate. Do not compile
    # the old mixed-signal wrapper against it and call it candidate qualification.
    mismatches = [name for name in FILES if sha(ROOT/'rtl'/name)!=sha(FROZEN/name)]
    assert 'IntegerPLL_DigitalCore.v' in mismatches
    out.mkdir(parents=True)
    binary = out/'harness_smoke.vvp'
    argv = ['/usr/bin/iverilog','-g2012','-s','tb_release_harness_smoke','-o',str(binary),
            *[str(FROZEN/name) for name in FILES],str(here/'IntegerPLL_ReleaseHarness.v'),
            str(here/'tb_release_harness_smoke.v')]
    with (out/'compile.log').open('w') as log:
        compiled = subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,timeout=43200)
    assert compiled.returncode==0
    with (out/'smoke.log').open('w') as log:
        tested = subprocess.run(['/usr/bin/vvp',str(binary)],stdout=log,stderr=subprocess.STDOUT,timeout=43200)
    assert tested.returncode==0 and 'PASS:' in (out/'smoke.log').read_text()
    for path in [Path('/usr/bin/iverilog'),Path('/usr/bin/vvp'),binary,out/'compile.log',out/'smoke.log']:
        pins[str(path)]=sha(path)
    cases = []
    for mode,corner,temp in product(spec['modes_mhz'],spec['corners'],spec['temperatures_c']):
        cases.append({'id':f'{mode}MHz_{corner}_1.8V_{temp}C','mode_mhz':mode,
             'corner':corner,'supply_v':1.8,'temperature_c':temp,
             'divider':mode//spec['reference_mhz'],
             'acquisition_limit_ns':spec['acquisition_limit_ns'],
             'sustained_windows':spec['sustained_windows'],'window_ns':spec['window_ns'],
             'frequency_error_ppm':spec['frequency_error_ppm'],
             'phase_limits_output_periods':{k:spec[k] for k in
                 ['phase_span_output_periods','phase_mean_output_periods','phase_drift_output_periods']},
             'status':'BLOCKED_VALIDATED_DCO_AND_INTERFACE_MODELS',
             'execution_eligible':False,'passed':False})
    assert len(cases)==75 and len({c['id'] for c in cases})==75
    report = {'observed_utc':datetime.now(timezone.utc).isoformat(),
              'case_count':75,'cases':cases,'candidate_rtl':str(FROZEN),
              'root_rtl_mismatch_negative_control':mismatches,
              'candidate_harness_compile_and_reset_smoke_pass':True,
              'required_before_qualification_execution':[
                  'Converged exact-candidate DCO model with calibrated range/interpolation and PVT coverage',
                  'Analog-correlated BBPD/receiver/reset model and candidate-boundary timing assumptions',
                  'Event/phase-continuous closed-loop driver with independently checked edge traces and mode-change coverage'],
              'native_analog_simulation_launched':False,
              'whole_pll_qualification_pass':False,'release_qualified':False,
              'sha256':pins,'scope':'Exact candidate harness smoke and75-case requirements manifest only. No fabricated calibration, acquisition, phase, power or jitter results.'}
    (out/'assessment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['cases','sha256']},indent=2))


if __name__=='__main__':
    main()
