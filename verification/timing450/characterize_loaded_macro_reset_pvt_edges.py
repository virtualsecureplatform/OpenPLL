#!/usr/bin/env python3
"""Prepare or run a loaded-event physical reset test with discrete PVT, phase and REF/DIV edge settings."""
import argparse
import json
import re
import subprocess
from pathlib import Path
from characterize_bbpd import sha,verify


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corner',choices=('tt','ff','ss','sf','fs'),required=True)
    parser.add_argument('--temperature-c',type=int,choices=(-40,27,125),required=True)
    parser.add_argument('--vdd',type=float,choices=(1.62,1.8,1.95),required=True)
    parser.add_argument('--phase-ps',type=int,choices=(-250,250),required=True)
    parser.add_argument('--edge-ps',type=int,choices=(20,200),required=True)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--prototype',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();fixture=args.fixture.resolve();prototype=args.prototype.resolve();out=args.output.resolve()
    recipe=json.loads((prototype/'assessment.json').read_text());assert recipe['simulation_completed'] and recipe['exit_code']==0
    verify(recipe['sha256']);prior=prototype/'input_manifest.json';assert sha(prior)==recipe['input_manifest_sha256'];pins=json.loads(prior.read_text())['sha256'];verify(pins)
    assembled=json.loads((fixture/'extraction.json').read_text());verify(assembled['sha256']);assert sha(fixture/'receiver.spice')==assembled['receiver_sha256']
    assert assembled['fixed_model_corner']==args.corner and assembled['fixed_model_temperature_c']==args.temperature_c
    pins.update(assembled['sha256'])
    original=Path('build/timing450/interface_characterization/receiver_committed_macro_reset_fixture_v2/extraction.json').resolve();graph=json.loads(original.read_text());verify(graph['sha256'])
    deck=(prototype/'loaded.cir').read_text();assert '.param VDD=1.62' in deck and '.options device temp=125' in deck
    old=next(line for line in deck.splitlines() if line.startswith('.include ') and 'receiver_reset_fixture_rc/receiver.spice' in line)
    deck=deck.replace(old,f'.include "{fixture / "receiver.spice"}"')
    header=re.search(r'^\.subckt bbpd_receiver_cdc (.+)$',(fixture/'receiver.spice').read_text(),re.M)[1].split()
    oldcall=next(line for line in deck.splitlines() if line.startswith('Xreceiver '));tokens=oldcall.split()[1:-1]
    oldports='BBPD0 BBPD1 PLLOUT RESET_N ACQ_INACTIVE COMMAND_RUN VGND VNB VPB VPWR UPQ DNQ UP1 UP2 DN1 DN2 CLKUP1 DATAUP1 CLKDN1 DATADN1 TIE_HIGH TIE_HIGH1 TIE_HIGH2 READY1 READY2 EVENT_RESET_N PIPE_RESET_N TRACK_ACTIVE'.split();assert len(tokens)==len(oldports)
    aliases=dict(zip(oldports,tokens));aliases.update(REFCLK='REF',BBPD_RESET_N='BBPD_RESET_PHY')
    for net,alias in graph['committed_boundaries'].items():
        if alias=='COMMITTED_FINE_CLOCK':aliases[alias]='CLKDIVR'
        elif alias=='COMMITTED_FINE_RUN':aliases[alias]='COMMAND_RUN'
        else:
            assert alias.startswith(('COMMITTED_COARSE_', 'COMMITTED_FINE_COARSE_'))
            aliases[alias]=alias
            deck=deck.replace('.options timeint',f'Vcommitted_{alias} {alias} 0 0\n.options timeint')
    assert deck.count('.tran 5p 90n 0 5p')==1
    deck=deck.replace('.tran 5p 90n 0 5p','.tran 5p 350n 0 5p')
    assert deck.count('17.05n {VDD} 17.07n 0 18.55n 0 18.57n {VDD}')==1
    deck=deck.replace('17.05n {VDD} 17.07n 0 18.55n 0 18.57n {VDD}',
                      '187.05n {VDD} 187.07n 0 188.55n 0 188.57n {VDD}')
    for name,alias in graph['external_configuration_ports'].items():
        if name=='PLL_ENABLE':value=1
        else:
            m=re.fullmatch(r'(FEEDBACK_DIVIDER|KI|KP)\[(\d+)\]',name);assert m
            value=({'FEEDBACK_DIVIDER':18,'KI':4,'KP':0}[m[1]]>>int(m[2]))&1
        aliases[alias]=alias;deck=deck.replace('.options timeint',f'Vcfg_{alias} {alias} 0 '+('{VDD}' if value else '0')+'\n.options timeint')
    for alias,value in graph['additional_tie_ports'].items():
        aliases[alias]=alias;deck=deck.replace('.options timeint',f'Vcfg_{alias} {alias} 0 '+('{VDD}' if value else '0')+'\n.options timeint')
    assert set(header)==set(aliases)
    deck=deck.replace(oldcall,'Xreceiver '+' '.join(aliases[p] for p in header)+' bbpd_receiver_cdc')
    assert deck.count('XBBPD BBPD[0] BBPD[1] CLKDIVR REF RESET_N ')==1
    deck=deck.replace('XBBPD BBPD[0] BBPD[1] CLKDIVR REF RESET_N ','XBBPD BBPD[0] BBPD[1] CLKDIVR REF BBPD_RESET_PHY ')
    deck=deck.replace('v(COMMAND_RUN)','v(COMMAND_RUN) v(BBPD_RESET_PHY)')
    assert deck.count('VDIV CLKDIVR 0 PULSE(0 {VDD} 10.25n ')==1
    deck=deck.replace('VDIV CLKDIVR 0 PULSE(0 {VDD} 10.25n ',f'VDIV CLKDIVR 0 PULSE(0 {{VDD}} {10+args.phase_ps/1000:g}n ')
    for source in ('VREF REF', 'VDIV CLKDIVR'):
        line=next(line for line in deck.splitlines() if line.startswith(source+' '))
        assert line.count('20p 20p')==1
        deck=deck.replace(line,line.replace('20p 20p',f'{args.edge_ps}p {args.edge_ps}p'))
    lib_line=next(line for line in deck.splitlines() if line.startswith('.lib '))
    assert lib_line.endswith(' ss')
    deck=deck.replace(lib_line,lib_line[:-3]+' '+args.corner)
    assert deck.count('.param VDD=1.62')==1 and deck.count('.options device temp=125')==1
    deck=deck.replace('.param VDD=1.62',f'.param VDD={args.vdd:g}').replace('.options device temp=125',f'.options device temp={args.temperature_c}')
    pvt={'corner':args.corner,'supply_v':args.vdd,'temperature_c':args.temperature_c}
    out.mkdir(parents=True,exist_ok=False);circuit=out/'loaded.cir';circuit.write_text(deck)
    for p in [prior,prototype/'assessment.json',fixture/'extraction.json',fixture/'receiver.spice',original,circuit,Path(__file__).resolve(),Path(__file__).with_name('characterize_loaded_macro_reset.py'),Path(__file__).with_name('characterize_loaded_macro_reset_pvt.py'),Path(__file__).with_name('characterize_bbpd.py'),Path('/opt/xyce/bin/Xyce')]:pins[str(p.resolve())]=sha(p)
    verify(pins);manifest=out/'input_manifest.json';manifest.write_text(json.dumps({'sha256':pins,'pvt':pvt,'phase_ps':args.phase_ps,'edge_ps':args.edge_ps,'scope':'Matching recorded primitive PVT and fixed diode translation,450MHz; actual mapped BBPD reset export; ideal REF/DIV/PLL/ties and acquisition-inactive/committed fast/fine RUN/coarse/divided-clock cuts; no fullPLL proof'},indent=2)+'\n')
    if args.prepare_only:
        report={'prepared':True,'simulation_completed':False,'native_result_pending':True,
                'pvt':pvt,'phase_ps':args.phase_ps,'edge_ps':args.edge_ps,
                'input_manifest_sha256':sha(manifest),'deck_sha256':sha(circuit),
                'release_qualified':False,'selected':False,
                'scope':'Prepared 450MHz loaded-event test; nominal cell RC/fixed route RC and ideal committed control boundaries. No native behavioral evidence.'}
        (out/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report));return
    with (out/'run.log').open('w') as log:
        result=subprocess.run(['/opt/xyce/bin/Xyce','-linsolv','KLU','-quiet','-o',str(out/'loaded'),str(circuit)],stdout=log,stderr=subprocess.STDOUT)
    verify(pins);log=(out/'run.log').read_text();wave=out/'loaded.prn'
    completed=result.returncode==0 and wave.exists() and 'End of Xyce(TM) Simulation' in wave.read_text() and not any(s in log for s in ['Unrecognized dot line','Simulation aborted','Netlist error'])
    report={'pvt':pvt,'exit_code':result.returncode,'simulation_completed':completed,'input_manifest_sha256':sha(manifest),'sha256':{str(p):sha(p) for p in [circuit,out/'run.log',wave] if p.exists()},'release_qualified':False,'selected':False,'functional_audit_pending':True,'limitations':['One alignment/PVT, nominal cellRC/fixed maxrouteRC; diode translation matches recorded corner/temperature','Ideal REF/DIV/PLL/ties; committed fast/fine RUN, coarse and divided-clock boundaries; no acquisition/handoff-generation proof','Native full-wave/consumption audit, MTBF and wholePLL qualification remain required']}
    (out/'assessment.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    if not completed:raise RuntimeError('Expanded reset-export native pilot incomplete')


if __name__=='__main__':main()
