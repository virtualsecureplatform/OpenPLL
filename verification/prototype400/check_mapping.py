#!/usr/bin/env python3
"""Compare full/compact mappings at every paired state, clock and reset pin."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
from common import ROOT, save, sha, verify
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import cut_pair, YOSYS, LIB


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gold',required=True,type=Path)
    p.add_argument('--gate',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    pins={}
    for folder in (a.gold.resolve(),a.gate.resolve()):
        report=json.loads((folder/'assessment.json').read_text())
        verify(report['input_sha256']);verify(report['artifacts'])
        for path in (folder/'assessment.json',folder/'mapped.json'):
            pins[str(path)]=sha(path)
    for path in (Path(__file__).resolve(),ROOT/'verification/timing400/check_compact_mapping.py',Path(YOSYS),LIB):
        pins[str(path)]=sha(path)
    modules=[json.loads((folder/'mapped.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
             for folder in (a.gold,a.gate)]
    gold,gate=copy.deepcopy(modules)
    count=cut_pair(gold,gate)
    for name,module in [('CUT_GOLD',gold),('CUT_GATE',gate)]:
        save(out/(name+'.json'),dict(modules={name:module}))
    task=f'''read_liberty -ignore_miss_func -ignore_miss_dir {LIB}
read_json {out}/CUT_GOLD.json
read_json {out}/CUT_GATE.json
miter -equiv -make_outputs -flatten CUT_GOLD CUT_GATE miter
hierarchy -top miter
prep -top miter -flatten
sat -verify -prove trigger 0 -show-inputs -show-outputs
'''
    def run(text,name):
        script=out/(name+'.ys');script.write_text(text)
        with (out/(name+'.log')).open('x') as log:
            code=subprocess.run([YOSYS,'-s',str(script)],stdout=log,stderr=subprocess.STDOUT,timeout=600).returncode
        return code,(out/(name+'.log')).read_text()
    code,log=run(task,'proof');assert code==0 and 'SUCCESS!' in log,log[-2000:]
    # Corrupt one flip-flop input; the exact same proof must detect it.
    bad=copy.deepcopy(gate)
    key=next(k for k in bad['ports'] if k.startswith('capture_') and k.endswith('_D'))
    original=bad['ports'][key]['bits']
    new=max(bit for cell in bad['cells'].values() for bits in cell['connections'].values()
            for bit in bits if isinstance(bit,int))+1
    bad['cells']['negative_inverter']=dict(type='sky130_fd_sc_hs__clkinv_1',parameters={},attributes={},
        port_directions={'A':'input','Y':'output'},connections={'A':original,'Y':[new]})
    bad['ports'][key]['bits']=[new]
    save(out/'CUT_BAD.json',dict(modules={'CUT_GATE':bad}))
    code,log=run(task.replace(str(out/'CUT_GATE.json'),str(out/'CUT_BAD.json')),'negative')
    assert code!=0 and 'proof did fail' in log
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,
         artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
         paired_registers=count,all_transition_clock_reset_and_output_functions_equivalent=True,
         corrupted_data_function_rejected=True,prototype_handoff_qualified=False))
    print('PASS: paired-state mapping equivalence and corruption control',count)


if __name__=='__main__':main()
