"""Preview larger equivalent drivers on frozen wires; never physical signoff."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from common_v3 import save,sha,verify
from compiled_charge import execute
from resources import lease
from screen_prototype_decision_hold_phase_v3 import OPENROAD

def run(electrical,phase,output):
    receipt=electrical/'assessment.json'; a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    p=phase/'assessment.json'; ph=json.loads(p.read_text());verify(ph['artifacts'])
    corner=ph['native_model_corner']; findings=json.loads((electrical/'violations.json').read_text())
    baseline=next(Path(n).parent for n in ph['input_sha256'] if n.endswith('/assessment.json') and 'timing_' in n)
    if a['input_sha256'].get(str(baseline/'assessment.json'))!=sha(baseline/'assessment.json'):raise ValueError('different route')
    original=phase/'screen.tcl'; text=original.read_text().split('report_parasitic_annotation',1)[0]
    libs=re.findall(r'^read_liberty.*? (\S+\.lib)$',text,re.M)
    masters=set()
    for name in libs:masters.update(re.findall(r'cell \(([^)]+)\)',Path(name).read_text()))
    chosen={}
    for f in findings:
        if f['corner']!=corner:continue
        for d in f['drivers']:
            base,size=d['master'].rsplit('_',1)
            choices=sorted((int(n.rsplit('_',1)[1]),n) for n in masters if n.startswith(base+'_') and n.rsplit('_',1)[1].isdigit() and int(n.rsplit('_',1)[1])>int(size))
            if choices:chosen[d['cell']]=dict(old=d['master'],new=choices[0][1])
    if not chosen:raise ValueError('no characterized larger drivers')
    inv=next(Path(n).parent for n in a['input_sha256'] if n.endswith('/assessment.json') and 'routed_CDC' in n)
    module=json.loads((inv/'routed.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
    cells={n.lstrip('\\'):c for n,c in module['cells'].items()}
    drivers={}
    for name,c in cells.items():
        for pin,bits in c['connections'].items():
            if c['port_directions'].get(pin)=='output':
                for bit in bits:drivers.setdefault(bit,[]).append(name)
    output.mkdir(parents=True,exist_ok=False)
    inputs={str(x):sha(x) for x in (receipt,p,original,inv/'routed.json',Path(__file__).resolve(),Path(OPENROAD))}
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    history=[];artifacts={}
    for iteration in range(8):
        actions=''.join('replace_cell {'+n+'} '+d['new']+'\n' for n,d in sorted(chosen.items()))
        queries='report_worst_slack -max\nreport_worst_slack -min\nreport_check_types -max_slew -violators -digits 6\n'
        script=output/f'preview_{iteration}.tcl';script.write_text(text+actions+queries+'exit\n')
        logpath=output/f'preview_{iteration}.log'
        with lease(1,4,deadline):execute([OPENROAD,'-exit',script],logpath,deadline,4)
        log=logpath.read_text()
        if re.search(r'\[ERROR|Error:',log):raise ValueError('sizing preview failed')
        history.append(dict(iteration=iteration,changed_drivers=len(chosen),violating_pins=log.count('(VIOLATED)')))
        artifacts.update({str(x):sha(x) for x in (script,logpath)})
        names=set()
        for pin in re.findall(r'^([^\s]+)\s+[\d.]+\s+[\d.]+\s+[-\d.]+ \(VIOLATED\)',log,re.M):
            name,port=pin.rsplit('/',1)
            if name not in cells:raise ValueError('unbound failing pin')
            for bit in cells[name]['connections'][port]:names.update(drivers.get(bit,[]))
        bumped=False
        for name in sorted(names):
            master=chosen[name]['new'] if name in chosen else cells[name]['type']
            base,size=master.rsplit('_',1)
            choices=sorted((int(n.rsplit('_',1)[1]),n) for n in masters if n.startswith(base+'_') and n.rsplit('_',1)[1].isdigit() and int(n.rsplit('_',1)[1])>int(size))
            if choices:
                chosen[name]=dict(old=cells[name]['type'],new=choices[0][1]);bumped=True
        if not bumped:break
    verify(inputs)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts=artifacts,corner=corner,history=history,frozen_wire_preview_only=True,physical_candidate_selected=False,release_ready=False))
    save(output/'changes.json',chosen)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('electrical','phase','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.electrical.resolve(),a.phase.resolve(),a.output.resolve())
