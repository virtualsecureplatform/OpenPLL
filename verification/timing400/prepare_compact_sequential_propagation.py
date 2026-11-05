#!/usr/bin/env python3
"""Prepare extracted clock-to-Q and asynchronous-assertion fixtures only.

No native job is launched. Setup/hold, recovery/removal, pulse width, output
slew, numerical error and full nominal15PVT qualification remain separate.
"""
import argparse
import itertools
import json
from pathlib import Path

from characterize_compact_propagation import ROOT,PDK,SOURCE,SUPPLIES,XYCE
from run_dco_qualification import REQUIREMENTS,sha,save


def pwl(points):
    return 'PWL('+ ' '.join(f'{time:.12g}n {volts:.12g}' for time,volts in points)+')'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corner',required=True,choices=['tt','ff','ss','sf','fs'])
    parser.add_argument('--temperature-c',required=True,type=int,choices=[-40,27,125])
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    index_path=ROOT/'build/timing400/release_001/hs_cell_model_index_001/assessment.json'
    index=json.loads(index_path.read_text())['models']
    inputs=[Path(__file__).resolve(),Path(__file__).with_name('characterize_compact_propagation.py').resolve(),
            REQUIREMENTS,index_path,XYCE]
    pins={str(p):sha(p) for p in inputs}
    spec=json.loads(REQUIREMENTS.read_text());assert spec['voltages']==[1.8]
    provenance_path=ROOT/'build/modern_25mhz/nominal_release_dco_path_001/screen/provenance.json'
    pins[str(provenance_path)]=sha(provenance_path)
    provenance=json.loads(provenance_path.read_text())
    for path,digest in provenance['files'].items():
        if str(PDK) in path and Path(path).suffix in ('.spice','.pm3','.mod','.lib'):
            assert sha(path)==digest,path;pins[path]=digest
    cases=[];models=[]
    for family,strength in itertools.product(('dfrtp','dfstp'),(1,2,4)):
        master=f'sky130_fd_sc_hs__{family}_{strength}'
        model=Path(index[master]['model']);assert sha(model)==index[master]['model_sha256']
        pins[str(model)]=sha(model);models.append(model)
        source=SOURCE/family/(master+'__tt_025C_1v80_ccsnoise.lib.json')
        if not source.exists():source=SOURCE/family/(master+'__tt_025C_1v80.lib.json')
        pins[str(source)]=sha(source);cell=json.loads(source.read_text())
        ff=[v for n,v in cell.items() if n.startswith('ff,')]
        control='RESET_B' if family=='dfrtp' else 'SET_B'
        reset_value=0 if family=='dfrtp' else 1
        expected={'clocked_on':'CLK','next_state':'D',
                  'clear' if family=='dfrtp' else 'preset':'!'+control}
        assert ff==[expected],(master,ff)
        ports=index[master]['ports']
        assert set(ports)==set(SUPPLIES)|{'CLK','D','Q',control}
        cap=float(cell['pin,Q']['max_capacitance']);assert cap>0
        for kind,ramp_ps,load_pf in itertools.product(('clock_toggle','async_assert'),
                                                    (20,200,1000/0.6),(0,cap/4,cap)):
            captures=[1-reset_value,reset_value,1-reset_value,reset_value]
            if kind=='async_assert':captures=[1-reset_value]*4
            cases.append(dict(master=master,kind=kind,ports=ports,control_pin=control,
                reset_value=reset_value,full_ramp_ps=ramp_ps,external_load_pf=load_pf,
                clock_rising_cycles_ns=[8,24,40,56],expected_captured_values=captures,
                assertion_start_times_ns=[16,32,48] if kind=='async_assert' else []))
    assert len(cases)==108
    lines=[f'* Raw sequential propagation preparation: {len(cases)} fixtures.',
        f'.lib "{PDK}/libs.tech/ngspice/sky130.lib.spice" {args.corner}',
        *[f'.include "{p}"' for p in models],f'.options device temp={args.temperature_c}',
        '.options timeint reltol=1e-5 abstol=1e-10','VSUP VDD 0 1.8']
    columns=[]
    for i,c in enumerate(cases):
        ramp_ns=c['full_ramp_ps']/1000
        reset=[(0,0),(2,0),(2.02,1.8)]
        if c['kind']=='async_assert':
            for start in (16,32,48):reset.extend([(start,1.8),(start+ramp_ns,0),(start+4,0),(start+4.02,1.8)])
        data=[(0,c['reset_value']*1.8)]
        if c['kind']=='clock_toggle':
            old=c['reset_value']
            for t,new in zip((4,20,36,52),c['expected_captured_values']):
                data.extend([(t,old*1.8),(t+.02,new*1.8)]);old=new
        else:data=[(0,(1-c['reset_value'])*1.8)]
        for points in (reset,data):assert all(a[0]<b[0] for a,b in zip(points,points[1:]))
        aliases={**SUPPLIES,'CLK':f'CLK_{i}','D':f'D_{i}','Q':f'Q_{i}',c['control_pin']:f'R_{i}'}
        lines.extend([f'VCLK_{i} CLK_{i} 0 PULSE(0 1.8 8n {c["full_ramp_ps"]:.12g}p {c["full_ramp_ps"]:.12g}p 3n 16n)',
            f'VDATA_{i} D_{i} 0 '+pwl(data),f'VRESET_{i} R_{i} 0 '+pwl(reset),
            f'XDUT_{i} '+' '.join(aliases[p] for p in c['ports'])+' '+c['master']])
        if c['external_load_pf']>0:lines.append(f'CLOAD_{i} Q_{i} 0 {c["external_load_pf"]:.12g}p')
        columns.extend(f'V({name}_{i})' for name in ('CLK','D','R','Q'))
    lines.extend(['.tran 2p 64n 0 2p','.print tran '+' '.join(columns),'.end'])
    deck=out/'batch.cir';deck.write_text('\n'.join(lines)+'\n');pins[str(deck)]=sha(deck)
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'plan.json',dict(input_sha256=pins,fixtures=cases,waveform_columns=columns,
        pvt=dict(corner=args.corner,supply_v=1.8,temperature_c=args.temperature_c),
        stop_ns=64,max_step_ps=2,native_processes=1,per_check_timeout_s=43200,
        native_execution_started=False,automatic_identical_retry=False,
        setup_hold_recovery_removal_qualified=False,physical_timing_qualified=False,
        release_qualified=False,scope=__doc__))
    print(f'Prepared {len(cases)} sequential propagation fixtures; no native job launched',flush=True)


if __name__=='__main__':main()
