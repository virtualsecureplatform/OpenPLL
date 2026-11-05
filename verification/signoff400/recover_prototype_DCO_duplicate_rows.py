"""Recover completed native output only when duplicate print rows are exactly redundant."""
import argparse
from decimal import Decimal
import json
import math
from pathlib import Path
import re
from common_v3 import save, sha, verify
from resources import identity
from assess_prototype_native_waveform import assess, crossings

NUMBER=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'


def parse(text):
    pattern=re.compile(r'^\s*(\d+)\s+('+NUMBER+r')\s+('+NUMBER+r')\s*$')
    points=[];duplicates=[];previous=None;count=0
    for line in text.splitlines():
        m=pattern.fullmatch(line)
        if m is None:continue
        index=int(m[1]);t=Decimal(m[2]);v=Decimal(m[3])
        if index!=count or not t.is_finite() or not v.is_finite():raise ValueError('native row indices or values invalid')
        count+=1
        if previous is not None and t<=previous[0]:
            if t!=previous[0] or v!=previous[1]:raise ValueError('nonredundant time collision or decreasing native time')
            duplicates.append(dict(original_index=index,previous_original_index=index-1,time=m[2],voltage=m[3]))
            continue
        tf,vf=float(t),float(v)
        if not all(map(math.isfinite,(tf,vf))) or points and tf<=points[-1][0]:raise ValueError('float conversion loses waveform time resolution')
        points.append((tf,vf));previous=(t,v)
    declared=re.findall(r'^No\. of Data Rows\s*:\s*(\d+)\s*$',text,re.M)
    if len(declared)!=1 or int(declared[0])!=count or len(points)<2:raise ValueError('complete native printed row count required')
    if 'Total analysis time (seconds)' not in text:raise ValueError('native completion footer missing')
    return points,duplicates,count


def measured(text,name):
    found=re.findall(r'^\s*'+re.escape(name)+r'\s*=\s*('+NUMBER+r')',text,re.M)
    if len(found)!=1 or not math.isfinite(float(found[0])):raise ValueError('unique finite native measure required: '+name)
    return float(found[0])


def run(source,output):
    manifest=source/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    owner=json.loads((source/'owner.json').read_text())
    if identity(owner['pid'])==owner['birth']:raise ValueError('original point controller is still live')
    status=source/'status.json';state=json.loads(status.read_text())
    wrapper=source/'native.log'
    if state['state']!='stopped_without_promotion' or 'ValueError: nonmonotonic ngspice waveform' not in wrapper.read_text():
        raise ValueError('only the known completed-output parser failure may be recovered')
    command=m['command']
    def arg(name):return command[command.index(name)+1]
    if arg('--simulator')!='ngspice' or '--ngspice-klu' not in command:raise ValueError('explicit ngspice KLU point required')
    logs=list((source/'native').glob('dco_postlayout_*.log'))
    if len(logs)!=1:raise ValueError('unique native simulation log required')
    log=logs[0];deck=log.with_suffix('.spice');provenance=log.with_suffix('.provenance.json')
    p=json.loads(provenance.read_text())
    if p['netlist_sha256']!=sha(deck):raise ValueError('original native deck changed')
    text=log.read_text()
    if 'Using KLU as Direct Linear Solver' not in text:raise ValueError('native KLU banner missing')
    points,duplicates,rows=parse(text)
    if not duplicates:raise ValueError('no exact redundant native rows to recover')
    start=float(arg('--meas-start-ns'))*1e-9;stop=float(arg('--sim-time-ns'))*1e-9;vdd=float(arg('--vdd'))
    metrics=assess(points,start,stop,vdd)
    rises=[t for t in crossings(points,vdd/2)[0] if start<=t<=stop]
    native_frequency=measured(text,'freq_hz');first_two=2/(rises[2]-rises[0])
    if not math.isclose(first_two,native_frequency,rel_tol=5e-5):raise ValueError('recovered crossings disagree with native frequency measure')
    rails={}
    for rail in ('vpwr','vpb'):
        values={kind:measured(text,rail+'_current_'+kind) for kind in ('avg','min','max')}
        if not values['min']<=values['avg']<=values['max']:raise ValueError('native current measure interval inconsistent')
        rails[rail]=values
    power=-vdd*(rails['vpwr']['avg']+rails['vpb']['avg'])
    if power<=0:raise ValueError('native delivered power must be positive')
    metrics.update(corner=arg('--corner'),temperature_c=float(arg('--temperature-c')),supply_v=vdd,
                   coarse_code=int(arg('--coarse-codes')),fine_code=int(arg('--codes')))
    paths=[manifest,status,wrapper,log,deck,provenance,source/'owner.json',Path(__file__).resolve(),
           Path(__file__).with_name('assess_prototype_native_waveform.py')]
    pins={str(f):sha(f) for f in paths};pins.update(m['input_sha256']);verify(pins)
    output.mkdir(parents=True,exist_ok=False);wave=output/'waveform.tsv'
    wave.write_text(''.join(f'{t:.17g} {v:.17g}\n' for t,v in points))
    detail=output/'all_cycle_metrics.json';save(detail,metrics)
    proof=output/'recovery.json';save(proof,dict(original_native_rows=rows,retained_unique_points=len(points),
         exact_redundant_rows=duplicates,first_two_cycle_frequency_hz=first_two,native_frequency_measure_hz=native_frequency,
         power_measures=rails,average_fixed_rail_power_W=power))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(f):sha(f) for f in (wave,detail,proof)},
         original_worker_failed_during_waveform_parsing=True,offline_native_waveform_recovery_completed=True,
         only_exact_equal_time_and_voltage_rows_coalesced=True,piecewise_linear_printed_waveform_unchanged=True,
         original_native_outputs_modified=False,native_simulations_started=0,
         native_measure_and_recovered_crossings_agree=True,all_captured_complete_cycles_assessed=True,
         numerical_uncertainty_bounded=False,parent_loading_complete=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve())
