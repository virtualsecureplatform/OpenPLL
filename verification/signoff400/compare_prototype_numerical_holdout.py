"""Compare same-model native numerical controls; retain observed error, qualify no bound."""
import argparse
import json
import math
from pathlib import Path
from common import save,sha,verify

NUMERIC=('--max-step-ps','--ngspice-reltol','--ngspice-abstol')
VARIABLE=(*NUMERIC,'--step-ps','--build-dir','--timeout-s','--sim-time-ns')


def controls(command):
    result={}
    for name in NUMERIC:
        value=float(command[command.index(name)+1])
        if not math.isfinite(value) or value<=0:raise ValueError('finite positive numerical controls required')
        result[name]=value
    return result


def compare(baseline,holdout,base_command,hold_command):
    a,b=controls(base_command),controls(hold_command)
    def physical_command(command):
        result=list(command)
        for key in VARIABLE:
            if key in result:result[result.index(key)+1]='<variable>'
        return result
    if physical_command(base_command)!=physical_command(hold_command):
        raise ValueError('numerical holdout changed physical/model conditions')
    if any(b[k]>a[k] for k in NUMERIC) or not any(b[k]<a[k] for k in NUMERIC):
        raise ValueError('holdout must tighten a numerical control without weakening another')
    for key in ('corner','temperature_c','supply_v','coarse_code','fine_code','measurement_start_s'):
        if baseline[key]!=holdout[key]:raise ValueError('waveform operating-point/window mismatch')
    if holdout['measurement_end_s']<baseline['measurement_end_s']:
        raise ValueError('holdout capture shorter than baseline')
    intervals=[baseline['observed_frequency_interval_hz'],holdout['observed_frequency_interval_hz']]
    for lo,hi in intervals:
        if not (math.isfinite(lo) and math.isfinite(hi) and 0<lo<=hi):raise ValueError('invalid observed frequency interval')
    means=[baseline['average_frequency_hz'],holdout['average_frequency_hz']]
    if not all(math.isfinite(x) and x>0 for x in means):raise ValueError('invalid mean frequency')
    delta=abs(means[1]-means[0])
    return dict(baseline_controls=a,holdout_controls=b,
        mean_frequency_difference_hz=delta,mean_frequency_difference_ppm=delta/means[0]*1e6,
        observed_frequency_envelope_hz=[min(x[0] for x in intervals),max(x[1] for x in intervals)],
        observed_fastest_startup_frequency_hz=max(baseline['fastest_observed_frequency_including_startup_hz'],holdout['fastest_observed_frequency_including_startup_hz']),
        numerical_error_proven_bounded=False,model_holdout_uncertainty_included=False,
        functional_capture_margin_evaluated=False,numerical_convergence_qualified=False)


def load(directory):
    receipt=directory/'assessment.json';r=json.loads(receipt.read_text())
    if r.get('all_captured_measurement_cycles_assessed') is not True:raise ValueError('full-waveform assessment required')
    verify(r['input_sha256']);verify(r['artifacts'])
    metrics=directory/'all_cycle_metrics.json'
    if r['artifacts'].get(str(metrics))!=sha(metrics):raise ValueError('waveform metrics not pinned')
    manifests=[Path(p) for p in r['input_sha256'] if p.endswith('/input_manifest.json')]
    if len(manifests)!=1:raise ValueError('unique native command manifest required')
    native=json.loads(manifests[0].read_text());verify(native['input_sha256'])
    return json.loads(metrics.read_text()),native['command'],[receipt,metrics,*manifests]


def run(baseline,holdout,output):
    output.mkdir(parents=True,exist_ok=False)
    a,ac,ap=load(baseline);b,bc,bp=load(holdout);result=compare(a,b,ac,bc)
    pins={str(p):sha(p) for p in [*ap,*bp,Path(__file__).resolve()]};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,comparison=result,
         diagnostic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','holdout','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.baseline.resolve(),a.holdout.resolve(),a.output.resolve())
