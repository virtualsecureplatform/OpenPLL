"""Assess every captured cycle; observed variation is not a total uncertainty bound."""
import argparse
import csv
import json
import math
from pathlib import Path
from common import save,sha,verify


def read_points(path):
    points=[]
    for line in path.read_text().splitlines():
        f=line.split()
        if len(f)!=2:raise ValueError('two-column waveform required')
        t,v=map(float,f)
        if not math.isfinite(t) or not math.isfinite(v) or (points and t<=points[-1][0]):
            raise ValueError('finite strictly increasing waveform required')
        points.append((t,v))
    if len(points)<2:raise ValueError('waveform absent')
    return points


def crossings(points,threshold):
    rises=[];falls=[]
    for (ta,va),(tb,vb) in zip(points,points[1:]):
        if va<threshold<=vb:rises.append(ta+(threshold-va)*(tb-ta)/(vb-va))
        elif va>threshold>=vb:falls.append(ta+(threshold-va)*(tb-ta)/(vb-va))
    return rises,falls


def assess(points,start_s,end_s,vdd):
    if not (0<=start_s<end_s and vdd>0):raise ValueError('invalid measurement window or supply')
    if points[0][0]>1e-18 or points[-1][0]<end_s-max(1e-18,end_s*1e-12):
        raise ValueError('waveform does not cover the requested simulation interval')
    rises,falls=crossings(points,vdd/2)
    measured=[t for t in rises if start_s<=t<=end_s]
    if len(measured)<4:raise ValueError('at least three complete measured periods required')
    periods=[b-a for a,b in zip(measured,measured[1:])]
    duties=[]
    for a,b in zip(measured,measured[1:]):
        between=[t for t in falls if a<t<b]
        if len(between)!=1:raise ValueError('one falling crossing per measured period required')
        duties.append((between[0]-a)/(b-a))
    all_periods=[b-a for a,b in zip(rises,rises[1:]) if b<=end_s]
    average=(measured[-1]-measured[0])/(len(measured)-1)
    return dict(samples=len(points),measurement_start_s=start_s,measurement_end_s=end_s,
        complete_measured_cycles=len(periods),first_measured_rise_s=measured[0],last_measured_rise_s=measured[-1],
        average_frequency_hz=1/average,
        observed_frequency_interval_hz=[1/max(periods),1/min(periods)],
        observed_period_interval_s=[min(periods),max(periods)],
        observed_duty_interval=[min(duties),max(duties)],
        fastest_observed_frequency_including_startup_hz=1/min(all_periods),
        sample_voltage_interval_v=[min(v for _,v in points),max(v for _,v in points)],
        periods_s=periods,numerical_convergence_uncertainty_included=False,
        model_holdout_uncertainty_included=False,all_reachable_startup_codes_covered=False)


def run(pilot,output):
    output.mkdir(parents=True,exist_ok=False)
    receipt=pilot/'assessment.json';r=json.loads(receipt.read_text())
    if r.get('native_worker_completed') is not True:raise ValueError('completed native worker required')
    verify(r['input_sha256'])
    manifest=pilot/'input_manifest.json';m=json.loads(manifest.read_text());command=m['command']
    def argument(name):return command[command.index(name)+1]
    if argument('--simulator')!='ngspice' or '--ngspice-waveform' not in command:
        raise ValueError('ngspice waveform pilot required')
    results=pilot/'native/dco_postlayout_results.csv';rows=list(csv.DictReader(results.open()))
    if len(rows)!=1 or rows[0]['status']!='pass' or rows[0]['timed_out']!='no':
        raise ValueError('one successful native measurement required')
    wave=Path(rows[0]['waveform']);netlist=Path(rows[0]['netlist']);log=Path(rows[0]['log'])
    if not wave.resolve().is_relative_to(pilot.resolve()):raise ValueError('waveform outside native pilot')
    paths=[receipt,manifest,results,wave,netlist,log,Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths}
    result=assess(read_points(wave),float(argument('--meas-start-ns'))*1e-9,
                  float(argument('--sim-time-ns'))*1e-9,float(argument('--vdd')))
    result.update(corner=argument('--corner'),temperature_c=float(argument('--temperature-c')),
                  supply_v=float(argument('--vdd')),coarse_code=int(rows[0]['coarse_code']),fine_code=int(rows[0]['code']))
    detail=output/'all_cycle_metrics.json';save(detail,result);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        all_captured_measurement_cycles_assessed=True,diagnostic=True,
        validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pilot',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.pilot.resolve(),a.output.resolve())
