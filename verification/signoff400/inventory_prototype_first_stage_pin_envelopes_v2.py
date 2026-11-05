"""Observe actual first-stage pin slew and routed Q load under native timing views."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import re
import time
from common_v3 import save,sha,verify
from compiled_charge import execute
from resources import lease
from review_prototype_first_stage_ranges import capacitance
from screen_prototype_decision_hold_phase_v3 import OPENROAD

def run(phase,obligations,output):
    pr=phase/'assessment.json';orr=obligations/'assessment.json';p,o=[json.loads(f.read_text()) for f in (pr,orr)]
    for a in (p,o):verify(a['artifacts'])
    original=phase/'screen.tcl';ob=obligations/'obligations.json';chains=json.loads(ob.read_text())['synchronizers']
    if len(chains)!=13 or any(c['stages'][0]['routed_master']!='sky130_fd_sc_hs__dfrtp_1' for c in chains):raise ValueError('exact thirteen DFRTP1 first stages required')
    output.mkdir(parents=True,exist_ok=False);table=output/'slews.tsv'
    query='set f [open {'+str(table)+'} w]\nputs $f [join {id pin rise_min_s rise_max_s fall_min_s fall_max_s} [format %c 9]]\n'
    for i,c in enumerate(chains):
        name=c['stages'][0]['routed_cell'].lstrip('\\')
        if any(ch in name for ch in '{}\n\r'):raise ValueError('invalid first-stage name')
        for pin in ('D','CLK','Q','RESET_B'):
            query+='set p [sta::get_port_pin_error pin {'+name+'/'+pin+'}]\nset vertices [$p vertices]\nif {[llength $vertices]!=1} {error "one first-stage timing vertex required"}\nset v [lindex $vertices 0]\nputs $f [join [list {'+c['id']+'} '+pin+' [$v slew rise min] [$v slew rise max] [$v slew fall min] [$v slew fall max]] [format %c 9]]\n'
        query+=f'puts "FIRST_STAGE_NET_{i}_BEGIN"\nset net [get_full_name [get_nets -of_objects [get_pins {{'+name+'/Q}]]]\nreport_net -digits 9 $net\n'+f'puts "FIRST_STAGE_NET_{i}_END"\n'
    query+='close $f\nexit\n';script=output/'query.tcl';script.write_text(original.read_text().split('report_parasitic_annotation',1)[0]+query)
    inputs={str(f):sha(f) for f in (pr,orr,original,ob,script,Path(OPENROAD),Path(__file__).resolve(),Path(__file__).with_name('review_prototype_first_stage_ranges.py'))}
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200;os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with lease(1,4,deadline):execute([OPENROAD,'-exit',script],output/'query.log',deadline,4)
    log=(output/'query.log').read_text();rows=list(csv.DictReader(table.open(),delimiter='\t'))
    if len(rows)!=52:raise ValueError('all four functional pins of all first stages required')
    for row in rows:
        for key in ('rise_min_s','rise_max_s','fall_min_s','fall_max_s'):
            row[key]=float(row[key])
            if not math.isfinite(row[key]) or row[key]<0:raise ValueError('nonfinite or negative first-stage slew')
    nets=[]
    for i,c in enumerate(chains):
        section=log.split(f'FIRST_STAGE_NET_{i}_BEGIN',1)[1].split(f'FIRST_STAGE_NET_{i}_END',1)[0]
        low,high=capacitance(section)
        nets.append(dict(id=c['id'],total_Q_capacitance_min_fF=low,total_Q_capacitance_fF=high))
    verify(inputs);detail=output/'envelopes.json';save(detail,dict(pins=rows,Q_nets=nets))
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(f):sha(f) for f in (table,detail,output/'query.log')},corner=p['native_model_corner'],first_stage_cells=13,functional_pins=52,early_late_capacitance_range_retained=True,maximum_Q_load_fF=max(n['total_Q_capacitance_fF'] for n in nets),maximum_slew_ps_by_pin={pin:max(max(r['rise_max_s'],r['fall_max_s'])*1e12 for r in rows if r['pin']==pin) for pin in ('D','CLK','Q','RESET_B')},capacitance_scope='supplied native-view pin capacitances and normalized routed nominal SPEF; pF UI converted to fF',physical_CDC_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('phase','obligations','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.phase.resolve(),a.obligations.resolve(),a.output.resolve())
