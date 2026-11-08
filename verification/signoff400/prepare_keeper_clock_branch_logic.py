"""Export a completed candidate's functional netlist and audit annotation omissions."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import sys
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from bind_CDC_physical_instances import word
from screen_prototype_decision_hold_phase_v5 import OPENROAD


def drivers(log):
    match = re.search(r'Found (\d+) unannotated drivers\.\n(.*?)Found (\d+) partially unannotated drivers\.', log, re.S)
    if not match or int(match[3]) != 0:
        raise ValueError('complete annotation summary without partial drivers required')
    names = [x.strip() for x in match[2].splitlines() if x.strip()]
    if len(names) != int(match[1]) or len(set(names)) != len(names):
        raise ValueError('unique complete driver inventory required')
    return sorted(names)


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {28})
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())) )
    b=ROOT/'build/signoff400';candidate=b/'selected_keeper_clock_branch_candidate_1452';timing=b/'selected_keeper_clock_branch_timing_1454';receipt=candidate/'assessment.json'
    try:
        c=json.loads(receipt.read_text());verify(c['input_sha256']);verify(c['artifacts'])
        if c.get('native_candidate_route_completed') is not True:raise ValueError('completed isolated candidate required')
        expected=None;logs=[]
        for corner in ['tt','ff','ss','sf','fs']:
            before=b/f'prototype_v3_selected_402p1_timing_{corner}_019/fixed_divide16/screen.log';after=timing/corner/'native.log';old,new=drivers(before.read_text()),drivers(after.read_text());logs.extend([before,after])
            if old!=new or expected is not None and new!=expected:raise ValueError('annotation omissions changed')
            expected=new
        tcl='read_db '+str(candidate/'route.odb')+'\nset_thread_count 1\nset block [ord::get_db_block]\n'
        tcl+='set table [open '+word(str(output/'annotation.tsv'))+' w]\n'
        for full in expected:
            name,pin=full.rsplit('/',1)
            tcl+='set inst [$block findInst '+word(name)+']\nif {$inst eq {NULL}} {error "driver instance missing"}\n'
            tcl+='set term [$inst findITerm '+word(pin)+']\nif {$term eq {NULL}} {error "driver pin missing"}\n'
            tcl+='set net [$term getNet]\nset sinks 0\nset ports 0\nset netname <unconnected>\n'
            tcl+='if {$net ne {NULL}} {set netname [$net getName];set ports [llength [$net getBTerms]];foreach p [$net getITerms] {if {[$p getIoType] in {INPUT INOUT}} {incr sinks}}}\n'
            tcl+='puts $table [join [list '+word(full)+' [[$inst getMaster] getName] $netname $sinks $ports] "\\t"]\n'
        tcl+='close $table\nset table [open '+word(str(output/'masters.tsv'))+' w]\nforeach inst [$block getInsts] {puts $table [[$inst getMaster] getName]}\nclose $table\nwrite_verilog '+str(output/'route.v')+'\nexit\n'
        script=output/'export.tcl';script.write_text(tcl)
        pins={str(p):sha(p) for p in [receipt,candidate/'route.odb',*logs,script,Path(OPENROAD),Path(__file__).resolve()]}
        save(output/'status.json',dict(state='exporting_candidate_logic_and_annotation_inventory',release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
        with lease(1,4,deadline):execute([OPENROAD,'-no_init','-exit',script],output/'native.log',deadline,4)
        rows=[]
        for line in (output/'annotation.tsv').read_text().splitlines():
            pin,master,net,sinks,ports=line.split('\t');rows.append(dict(pin=pin,master=master,net=net,input_or_inout_sinks=int(sinks),top_ports=int(ports)))
        if len(rows)!=len(expected):raise ValueError('all omitted drivers require native binding')
        all_unloaded=all(r['input_or_inout_sinks']==0 and r['top_ports']==0 for r in rows)
        inventory=dict(Counter((output/'masters.tsv').read_text().splitlines()))
        old=json.loads((b/'prototype_v3_selected_route_019/assessment.json').read_text());sources=old['candidate_source_sha256'];verify(sources);pins.update(sources);verify(pins)
        annotation=output/'annotation.json';save(annotation,dict(drivers=rows,unchanged_from_all_five_baselines=True,all_unannotated_drivers_have_no_external_sinks_or_ports=all_unloaded,physical_load_models_qualified=False,release_ready=False))
        targets=[output/n for n in ['route.v','masters.tsv','annotation.tsv','annotation.json','native.log']]
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in targets},candidate_source_sha256=sources,cell_inventory=inventory,digital_routing_completed=True,source_candidate_receipt=str(receipt),functional_netlist_export_only=True,all_unannotated_drivers_have_no_external_sinks_or_ports=all_unloaded,logical_equivalence_verified=False,physical_timing_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='candidate_logic_export_complete',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
