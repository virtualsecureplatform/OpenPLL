#!/usr/bin/env python3
"""Assess completed native STD output without repeating the DCO simulation.

The retained runner anticipated CSV; this upstream build writes STD .prn when
given its explicit -o output path. Frequency remains a diagnostic until the
independent calibration, model and physical integration checks pass.
"""
import argparse
import json
import math
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--point',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    base = Path(__file__).resolve().parents[2]/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    original = args.point/'assessment.json'
    receipt = json.loads(original.read_text())
    assert receipt['native_exit'] == 0
    manifest = args.point/'input_manifest.json'
    parameters = json.loads(manifest.read_text())['parameters']
    assert 'End of Xyce(TM) Simulation' in (args.point/'native.log').read_text()
    wave = args.point/'point.cir.prn'
    assert digest(wave) == receipt['artifacts'][str(wave.resolve())]
    time_values, voltage, current = [],[],[]
    with wave.open() as stream:
        assert next(stream).split() == ['Index','TIME','V(PLLOUT)','I(VVPWR)']
        for line in stream:
            values = line.split()
            if line.strip() == 'End of Xyce(TM) Simulation':
                continue
            assert len(values) == 4 and int(values[0]) == len(time_values), line
            t,v,i = map(float,values[1:])
            assert all(math.isfinite(value) for value in [t,v,i])
            assert not time_values or t > time_values[-1]
            time_values.append(t)
            voltage.append(v)
            current.append(i)
    assert len(time_values) > 2
    assert time_values[-1] >= parameters['duration_ns']*1e-9*(1-1e-7)
    edges = []
    for i in range(1,len(time_values)):
        if voltage[i-1] < .9 <= voltage[i]:
            t = time_values[i-1]+(.9-voltage[i-1])*(time_values[i]-time_values[i-1])/(voltage[i]-voltage[i-1])
            if t >= parameters['measure_start_ns']*1e-9:
                edges.append(t)
    intervals = [b-a for a,b in zip(edges,edges[1:])]
    metrics = None
    if len(intervals) >= 3:
        metrics = dict(mhz=len(intervals)/(edges[-1]-edges[0])*1e-6,periods=len(intervals),
            minimum_period_ns=min(intervals)*1e9,maximum_period_ns=max(intervals)*1e9,
            output_min_V=min(voltage),output_max_V=max(voltage))
    args.output.mkdir(exist_ok=False)
    save(args.output/'measured_edges_s.json',edges)
    inputs = [Path(__file__).resolve(),owner,original,manifest,wave,args.point/'native.log']
    save(args.output/'assessment.json',dict(native_exit=0,completed_diagnostic_oscillation=metrics is not None,
        metrics=metrics,native_cases_repeated=0,retained_STD_output_assessed=True,
        settled_frequency_calibration_qualified=False,physical_full_parent_loading_qualified=False,
        runtime_model_eligible=False,release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256={str(p.resolve()):digest(p) for p in inputs},
        artifacts={str((args.output/'measured_edges_s.json').resolve()):digest(args.output/'measured_edges_s.json')}))
    print(json.dumps(dict(metrics=metrics,native_cases_repeated=0),indent=2))


if __name__ == '__main__':
    main()
