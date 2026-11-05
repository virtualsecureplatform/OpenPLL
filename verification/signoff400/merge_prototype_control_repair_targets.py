"""Retain historical successful repairs and add newly measured unbuffered targets."""
import argparse
import json
from pathlib import Path
import sys
from common_v3 import ROOT,save,sha,verify
sys.path.insert(0,str(ROOT/'verification/prototype400'))
from build_assembly_frame import expected

def run(frame,observations,output):
    fr=frame/'assessment.json';f=json.loads(fr.read_text());verify(f['input_sha256']);verify(f['artifacts'])
    if not f['assembly_frame_pass']:raise ValueError('checked source frame required')
    pins={str(p):sha(p) for p in (fr,Path(__file__).resolve())};targets={};logical=expected()
    for directory in observations:
        receipt=directory/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        if a['input_sha256'].get(str(fr))!=sha(fr) or a['violations_with_macro_port']!=a['violations']:
            raise ValueError('matching fully localized source-frame observations required')
        records=directory/'records.json';pins.update({str(p):sha(p) for p in (receipt,records)})
        for row in json.loads(records.read_text()):
            ports=[p for p in row['macro_ports'] if p['instance']=='oscillator']
            if len(ports)!=1:raise ValueError('one measured DCO control receiver required')
            port=ports[0];net=logical.get(('oscillator',port['pin']))
            if net is None or port['net']!=net:
                raise ValueError('remaining buffered-output failure needs a different repair; do not relabel it')
            target=targets.setdefault(net,dict(net=net,macro_ports=[port],observations=[]))
            if target['macro_ports']!=[port]:raise ValueError('source macro port geometry differs')
            target['observations'].append(dict(authority=str(receipt),stage=row['stage'],cluster=row['cluster'],observed_physical_net=port['net']))
    if not targets:raise ValueError('measured repair targets required')
    verify(pins);output.mkdir(parents=True,exist_ok=False);records=output/'records.json';save(records,[targets[n] for n in sorted(targets)])
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(records):sha(records)},
         record_semantics='cumulative_repair_targets_not_current_failure_count',historical_observations_retained=True,
         repair_targets=len(targets),violations=len(targets),violations_with_macro_port=len(targets),
         all_targets_are_original_unbuffered_control_signals=True,antenna_qualified=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('frame','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--observation',type=Path,required=True,action='append')
    args=parser.parse_args();run(args.frame.resolve(),[p.resolve() for p in args.observation],args.output.resolve())
