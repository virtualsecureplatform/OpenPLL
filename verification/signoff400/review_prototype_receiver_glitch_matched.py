"""Review peak-targeted replays with source and receiving-cell process corners matched."""
import argparse
import json
import math
from pathlib import Path
import re
import time
from common_v3 import ROOT,save,sha,verify
from resources import identity
from compare_mapped_routed_CDC import clock_roots
from run_prototype_receiver_glitch_peak import assess,targeted_phases
from run_prototype_BBPD_receiver_RC_point import read_table


def table(text):
    declared=re.findall(r'No\. of Data Rows\s*:\s*(\d+)',text);rows=[]
    if len(declared)!=1:raise ValueError('one replay table required')
    for line in text.splitlines():
        f=line.split()
        if not f or not f[0].isdigit():continue
        if len(f)!=5 or int(f[0])!=len(rows):raise ValueError('malformed replay table')
        row=tuple(map(float,f[1:]))
        if not all(math.isfinite(v) for v in row) or rows and row[0]<=rows[-1][0]:raise ValueError('invalid replay samples')
        rows.append(row)
    if len(rows)!=int(declared[0]) or not rows or rows[0][0]!=0 or abs(rows[-1][0]-12e-9)>1e-15:raise ValueError('incomplete replay table')
    return rows


def run(sources,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    pins={};records=[];corners=set()
    routed=ROOT/'build/signoff400/startup_timing_routed_CDC_inventory_001/routed.json'
    inv=routed.parent/'assessment.json';a=json.loads(inv.read_text())
    if a['artifacts'].get(str(routed))!=sha(routed):raise ValueError('routed receiver identity changed')
    module=json.loads(routed.read_text())['modules']['IntegerPLL_ProgrammedCore'];clock=clock_roots(module)
    receivers=[]
    for name,cell in module['cells'].items():
        if cell['connections'].get('D')!=[3071]:continue
        if cell['type']!='sky130_fd_sc_hs__dfrtp_1' or clock(cell['connections']['CLK'][0])!=('primary','PLLOUT',0,0):raise ValueError('unexpected receiving cell or clock')
        receivers.append(name)
    if len(receivers)!=1:raise ValueError('unique first DN synchronizer receiver required')
    for source in sources:
        while not (source/'assessment.json').exists():
            owner=json.loads((source/'owner.json').read_text())
            if identity(owner['pid'])!=owner['birth']:raise ValueError('replay stopped without receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('replay review deadline')
            time.sleep(1)
        receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if r['corner'] in corners:raise ValueError('duplicate replay corner')
        if r['waveform_source_corner']!=r['corner']:raise ValueError('source and receiver process corners must match')
        corners.add(r['corner']);pins[str(receipt)]=sha(receipt)
        originals=[Path(p) for p in r['input_sha256'] if p.endswith('/phase_0ps/native.log')]
        if len(originals)!=1:raise ValueError('unique original glitch waveform required')
        phases,peak=targeted_phases(read_table(originals[0].read_text()))
        if not r.get('targeted_peak_sampling') or r['clock_phase_offsets_ps']!=phases or r['source_peak']!=peak:raise ValueError('measured-peak targeting differs')
        pins[str(originals[0])]=sha(originals[0])
        declared=json.loads((source/'observations.json').read_text());seen=set()
        for row in declared:
            high=row['high'];phase=round((row['clock_center_ns']-5)*1000)
            if type(high) is not bool or phase not in phases or (high,phase) in seen:raise ValueError('invalid replay case grid')
            seen.add((high,phase));log=source/f'{int(high)}_{phase}ps/native.log'
            if r['artifacts'].get(str(log))!=sha(log):raise ValueError('unbound replay log')
            observed=assess(table(log.read_text()),high)
            if any(row[k]!=v for k,v in observed.items()):raise ValueError('native replay observation differs')
            records.append(dict(corner=r['corner'],high=high,phase_ps=phase,**observed));pins[str(log)]=sha(log)
        if seen!={(h,p) for h in (False,True) for p in phases}:raise ValueError('incomplete replay case grid')
    if corners!={'tt','ff','ss','sf','fs'}:raise ValueError('five receiving-cell corners required')
    pins.update({str(p):sha(p) for p in (routed,inv,Path(__file__).resolve(),Path(__file__).with_name('run_prototype_receiver_glitch_peak.py'))})
    detail=output/'observations.json';save(detail,records);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},receiving_cell=receivers[0],
        complete_native_cases=len(records),observed_peak_targeting_verified=True,all_conditional_states_retained=all(r['state_retained'] for r in records),
        source_and_receiving_cell_corners_match=True,source_waveform_PVT_envelope_bounded=False,phase_continuum_covered=False,
        actual_pin_loading_in_original_waveform=False,diagnostic=True,native_interface_qualified=False,release_ready=False))
    print('Reviewed native replay cases:',len(records))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sources',type=Path,nargs='+',required=True);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();run([p.resolve() for p in a.sources],a.output.resolve())
