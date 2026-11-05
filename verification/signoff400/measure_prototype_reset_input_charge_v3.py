"""Measure reset-pin charge with preloaded output states; no routed-path qualification."""
import argparse
import itertools
import json
import math
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease
from compiled_charge import execute
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v2 import header

PDK='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A'


def clipped_integral(t0,t1,i0,i1,start,stop):
    if t1<=t0:raise ValueError('strictly increasing sample times required')
    a,b=max(t0,start),min(t1,stop)
    if b<=a:return 0.
    ia=i0+(i1-i0)*(a-t0)/(t1-t0)
    ib=i0+(i1-i0)*(b-t0)/(t1-t0)
    return (ia+ib)*(b-a)/2


def run(source,corner,output):
    if corner not in ('tt','ff','ss','sf','fs'):raise ValueError('prototype corner required')
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    receipt=source/'assessment.json';a=json.loads(receipt.read_text())
    verify(a['input_sha256']);verify(a['artifacts'])
    model=source/'models.spice';blocks=subcircuits(model.read_text())
    if len(blocks)!=5 or not a['all_native_fixtures_passed']:
        raise ValueError('five reviewed final sequential cell models required')
    cases=[]
    for master,block in sorted(blocks.items()):
        ports=header(block);control='RESET_B' if '__dfrtp_' in master else 'SET_B'
        if control not in ports:raise ValueError('explicit asynchronous control required')
        for data,clock,ramp in itertools.product((0,1),(0,1),(20,200,2000)):
            cases.append(dict(master=master,control=control,data=data,clock=clock,ramp_ps=ramp,ports=ports))
    output.mkdir(parents=True,exist_ok=False)
    definition=output/'models.spice';definition.write_bytes(model.read_bytes())
    lines=['* Native reset input charge; preload clock then held CLK, Q load 40 fF.',
           f'.lib "{PDK}/libs.tech/ngspice/sky130.lib.spice" {corner}',
           f'.include "{definition}"','.options device temp=27',
           '.options timeint reltol=1e-6 abstol=1e-12','VSUP VDD 0 1.8']
    columns=[]
    for i,c in enumerate(cases):
        ramp=c['ramp_ps']/1000
        aliases=dict(VPWR='VDD',VPB='VDD',VGND='0',VNB='0',
                     D='VDD' if c['data'] else '0',CLK=f'CLK_{i}',Q=f'Q_{i}')
        aliases[c['control']]=f'R_{i}'
        nodes=[aliases.get(p,f'PRIVATE_{i}_{j}') for j,p in enumerate(c['ports'])]
        clock_wave='0 0 4n 0 4.2n 1.8 '+('14n 1.8' if c['clock'] else '6n 1.8 6.2n 0 14n 0')
        lines.append(f'VCLK_{i} CLK_{i} 0 PWL({clock_wave})')
        lines.extend((f'VR_{i} R_{i} 0 PWL(0 0 2n 0 {2+ramp:.12g}n 1.8 8n 1.8 {8+ramp:.12g}n 0 14n 0)',
                      f'XDUT_{i} '+' '.join(nodes)+' '+c['master'],f'CQ_{i} Q_{i} 0 40f'))
        columns.extend((f'V(R_{i})',f'I(VR_{i})',f'V(Q_{i})'))
    lines.extend(('VCONTROL CREF 0 PWL(0 0 2n 0 2.2n 1.8 8n 1.8 8.2n 0 14n 0)',
                  'CCONTROL CREF 0 20f','.tran 2p 14n 0 2p',
                  '.print tran '+' '.join(columns+['V(CREF)','I(VCONTROL)']),'.end'))
    deck=output/'batch.cir';deck.write_text('\n'.join(lines)+'\n')
    pins={str(p):sha(p) for p in (receipt,model,definition,deck,Path(__file__).resolve(),
          Path(__file__).with_name('prepare_prototype_analog_reference.py'),
          Path(__file__).with_name('prepare_prototype_BBPD_receiver_v2.py'))}
    tool='/opt/xyce/bin/Xyce';pins[tool]=sha(tool)
    pins.update({p:d for p,d in a['input_sha256'].items() if p.startswith(PDK+'/')})
    save(output/'plan.json',dict(input_sha256=pins,corner=corner,cases=cases,
         static_D_CLK_only=False,preloaded_output_states_exercised=True,preload_clock_ramp_ps=200,output_load_f=40e-15,routed_path_qualification=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(1,8,deadline):
        save(output/'status.json',dict(state='native_reset_charge_running',release_ready=False))
        execute([tool,'-linsolv','KLU','-quiet','-o',output/'batch',deck],output/'native.log',deadline,8)
        wave=output/'batch.prn';previous=None;count=0;terminal=False
        charge=[[0.,0.] for _ in range(len(cases)+1)]
        with wave.open() as stream:
            expected=['Index','TIME']+columns+['V(CREF)','I(VCONTROL)']
            if stream.readline().split()!=expected:raise ValueError('native current columns differ')
            for line in stream:
                if 'End of Xyce(TM) Simulation' in line:terminal=True;continue
                f=line.split()
                if not f:continue
                if terminal or len(f)!=len(expected) or int(f[0])!=count:raise ValueError('waveform row mismatch')
                row=list(map(float,f[1:]));t=row[0]
                if not all(map(math.isfinite,row)):raise ValueError('nonfinite native current')
                if previous is not None:
                    pt,old=previous
                    for i in range(len(cases)+1):
                        ramp=(cases[i]['ramp_ps'] if i<len(cases) else 200)*1e-12
                        column=2+3*i
                        if i==len(cases):column=len(row)-1
                        for j,edge in enumerate((2e-9,8e-9)):
                            charge[i][j]+=clipped_integral(pt,t,old[column],row[column],edge+.2*ramp,edge+.8*ramp)
                previous=(t,row);count+=1
        if not terminal or previous is None or previous[0]<14e-9-1e-15:
            raise ValueError('incomplete native current observation')
        control=[-charge[-1][0]/1.08,charge[-1][1]/1.08]
        if any(abs(v/20e-15-1)>1e-4 for v in control):
            raise ValueError('known 20 fF charge/sign/unit control failed')
        detail=output/'charge.json'
        results=[dict(fixture=c,rising_20_80_effective_f=-q[0]/1.08,
                      falling_80_20_effective_f=q[1]/1.08) for c,q in zip(cases,charge)]
        save(detail,dict(points=results,control_capacitances_f=control))
        verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,
         artifacts={str(p):sha(p) for p in (definition,deck,wave,detail,output/'plan.json')},
         corner=corner,temperature_c=27,supply_v=1.8,measured_reset_fixtures=len(cases),
         known_capacitor_charge_sign_and_units_pass=True,static_D_CLK_only=False,preloaded_output_states_exercised=True,preload_clock_ramp_ps=200,
         leakage_not_subtracted=True,intracell_wire_R_included=False,
         native_reset_input_impedance_fully_qualified=False,routed_path_correlation_complete=False,
         physical_timing_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='reset_charge_diagnostic_complete',release_ready=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--corner',required=True)
    args=parser.parse_args()
    try:run(args.source.resolve(),args.corner,args.output.resolve())
    except BaseException as error:
        if args.output.is_dir():save(args.output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise
