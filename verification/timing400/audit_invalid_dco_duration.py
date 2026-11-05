#!/usr/bin/env python3
"""Retain all windows from the completed probe invalidated by reset reassertion.

Native simulation completed160ns, but reset reasserted at85.05ns because the
pulse width stayed80ns. Late missing edges are stimulus effects, not proof of
oscillator failure. This audit repeats only data analysis, never simulation.
"""
import argparse
from decimal import Decimal
import json
from pathlib import Path
from audit_dco_settling_windows import independent_edges
from benchmark_dco_linear_solver_v2 import waveform
from run_dco_duration_probe_v3 import decimal_measure
from run_dco_qualification import ROOT,sha,save,measure


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001';source=base/'dco_duration_c1_f128_160ns_001'
    plan=json.loads((source/'plan.json').read_text());wave=source/'run_001/duration.prn'
    times,values=waveform(wave);assert times[-1]>=160e-9-1e-15
    edges=independent_edges(wave);assert len(edges)==32 and Decimal('84e-9')<edges[-1]<Decimal('85.05e-9')
    assert '80.0n 160.0n)' in (source/'duration.spice').read_text()
    rows=[]
    for start,stop in plan['predeclared_windows_ns']:
        selected=[t for t in edges if Decimal(start)*Decimal('1e-9')<=t<=Decimal(stop)*Decimal('1e-9')]
        row=dict(start_ns=start,stop_ns=stop,rising_edges=len(selected),reset_reasserts_inside_window=start<85.05<stop)
        try:
            metric=measure(wave,start,stop,1.8,min_periods=3);freq,drift=decimal_measure(edges,start,stop)
            assert abs(metric['mhz']-float(freq))<1e-8
            assert abs(metric['half_window_difference_mhz']-float(drift))<1e-8
            period=(selected[-1]-selected[0])/Decimal(len(selected)-1)
            sustained=(Decimal(stop)*Decimal('1e-9')-selected[-1]<=2*period)
            row.update(**metric,independent_decimal_frequency_mhz=str(freq),independent_decimal_drift_mhz=str(drift),
                sustained_to_window_end=bool(sustained),state='early_prefix_diagnostic' if stop<=80 else 'invalid_reset_affected_window')
            if stop<=80:
                old=measure(Path(plan['reference_waveform']),start,stop,1.8,min_periods=3)
                row.update(reference_80ns_run=old,duration_run_minus_reference_mhz=metric['mhz']-old['mhz'])
        except (ValueError,AssertionError,IndexError) as error:
            row.update(state='unmeasurable_reset_affected_window',reason=repr(error),sustained_to_window_end=False)
        rows.append(row)
    files=[Path(__file__).resolve(),source/'plan.json',source/'duration.spice',source/'run_001/status.json',source/'run_001/run.log',wave,
        Path(plan['reference_waveform']),base/'dco_duration_reset_stimulus_failure_001/assessment.json']
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},artifacts={},records=rows,
        all_eight_declared_windows_retained=len(rows)==8,native_waveform_terminal=True,simulation_repeated=False,
        native_rising_edges=32,last_rising_edge_seconds=str(edges[-1]),reset_reassertion_seconds='8.505e-8',
        invalid_for_duration_convergence=True,postprocess_missing_measurements_recovered=True,
        dco_failure_established=False,measurement_window_adopted=False,calibration_model_qualified=False,release_qualified=False,scope=__doc__))
    print('Recovered all8 windows from completed invalid-stimulus waveform; no oscillator-failure or convergence claim.')

if __name__=='__main__':main()
