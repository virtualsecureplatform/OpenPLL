"""Measure clock-path phase offsets from the selected native startup trace.

Nearest-preceding-edge pairing reports observed phase residues. It does not
prove unwrapped causal latency or an all-corner timing envelope.
"""
import argparse,json,re
from pathlib import Path
import numpy as np
from common_v3 import save,sha,verify
from compare_selected_streaming import read
from capture_selected_detector_pins import crossings


def edges(t,v,rising):return crossings(t,v,.9) if rising else crossings(t,-v,-.9)


def preceding_delays(source,destination,start=200e-9,end=260e-9):
    d=destination[(destination>=start)&(destination<=end)];result=[]
    for time in d:
        i=np.searchsorted(source,time,side='right')-1
        if i<0:raise ValueError('preceding source edge required')
        result.append(float((time-source[i])*1e12))
    if not result:raise ValueError('native destination edge required')
    return dict(samples=len(result),observed_ps=result,minimum_ps=min(result),maximum_ps=max(result),
                median_ps=float(np.median(result)))


def measure(reference,pins_dir,native,output):
    if output.exists():raise FileExistsError(output)
    receipt=pins_dir/'assessment.json';p=json.loads(receipt.read_text());verify(p['artifacts'])
    if p['input_sha256'].get(str(native/'manifest.json'))!=sha(native/'manifest.json'):raise ValueError('pin capture/native identity mismatch')
    names,a=read(reference);t=a[:,0]
    channels={k:a[:,names.index('v('+k+')')] for k in ['pllout','clkdiv_retimed','refclk']}
    pin_ref=np.loadtxt(p['observations']['REF']['file']);pin_div=np.loadtxt(p['observations']['CLKDIVR']['file'])
    records={};delays={}
    for rising,label in [(True,'rise'),(False,'fall')]:
        fast=edges(t,channels['pllout'],True)
        root_div=edges(t,channels['clkdiv_retimed'],rising)
        root_ref=edges(t,channels['refclk'],rising)
        for key,source,destination in [
            ('divided_output',fast,root_div),
            ('feedback_wire',root_div,edges(pin_div[:,0],pin_div[:,1],rising)),
            ('reference_wire',root_ref,edges(pin_ref[:,0],pin_ref[:,1],rising))]:
            metric=preceding_delays(source,destination);records[key+'_'+label]=metric
            delays[key+'_'+label+'_ps']=int(round(metric['median_ps']))
    deck=(native/'profile.spice').read_text();corners=re.findall(r'^\.lib\s+.*\s+(tt|ff|ss|sf|fs)\s*$',deck,re.M|re.I)
    if len(corners)!=1 or '.options device temp=27' not in deck.lower():raise ValueError('known single-corner 27C reference required')
    if not re.search(r'^V\S+\s+VPWR\s+0\s+1\.8\s*$',deck,re.M):raise ValueError('known 1.8V reference required')
    manifest=json.loads((native/'manifest.json').read_text())
    physical={k:v for k,v in manifest['input_sha256'].items() if k.endswith('/model.spice')}
    if len(physical)!=1:raise ValueError('unique native physical model required')
    pins={str(x):sha(x) for x in [reference,receipt,native/'manifest.json',native/'profile.spice',Path(__file__).resolve(),Path(__file__).with_name('capture_selected_detector_pins.py'),Path(__file__).with_name('compare_selected_streaming.py')]}
    pins.update(p['artifacts']);verify(pins)
    save(output,dict(schema_version=1,operating_point=dict(corner=corners[0].lower(),temperature_c=27,supply_v=1.8),
        input_sha256=pins,reference_model_sha256=physical,delay_ps=delays,observations=records,
        measurement_window_ns=[200,260],pairing='nearest_preceding_source_edge',
        unwrapped_causal_latency_qualified=False,clock_timing_qualified=False,
        diagnostic=True,physical_models_qualified=False,release_ready=False))
    return delays


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['reference','pins','native','output']:p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args();print(measure(a.reference.resolve(),a.pins.resolve(),a.native.resolve(),a.output.resolve()))
