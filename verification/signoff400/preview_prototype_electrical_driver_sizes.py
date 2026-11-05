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
    actions=''.join('replace_cell {'+n+'} '+d['new']+'\n' for n,d in sorted(chosen.items()))
    queries='report_worst_slack -max\nreport_worst_slack -min\nreport_check_types -max_slew -violators -digits 6\n'
    output.mkdir(parents=True,exist_ok=False);script=output/'preview.tcl';script.write_text(text+actions+queries+'exit\n')
    inputs={str(x):sha(x) for x in (receipt,p,original,script,Path(__file__).resolve(),Path(OPENROAD))}
    save(output/'input_manifest.json',dict(input_sha256=inputs,changes=chosen))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with lease(1,4,deadline):execute([OPENROAD,'-exit',script],output/'preview.log',deadline,4)
    log=(output/'preview.log').read_text()
    if re.search(r'\[ERROR|Error:',log):raise ValueError('sizing preview failed')
    verify(inputs);save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(output/'preview.log'):sha(output/'preview.log')},corner=corner,changed_drivers=len(chosen),remaining_reported_slew_violations=log.count('(VIOLATED)'),frozen_wire_preview_only=True,physical_candidate_selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('electrical','phase','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.electrical.resolve(),a.phase.resolve(),a.output.resolve())
