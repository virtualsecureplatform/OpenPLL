#!/usr/bin/env python3
"""Prove checkpoint logic; detailed routing and all physical signoff remain separate."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from common import ROOT
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_clock_tree import verify
from check_compact_mapping import LIB, LEF, YOSYS
TOP="IntegerPLL_ProgrammedCore"
from route_compact_candidate import PHYSICAL
from run_dco_qualification import sha, save


def main():
    started=time.monotonic()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',required=True,type=Path)
    parser.add_argument('--gold-json',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();root=args.checkpoint.resolve();gold=args.gold_json.resolve();out=args.output.resolve()
    receipt=verify(root/'assessment.json')
    assert receipt['logic_checkpoint_export_completed'] and receipt['digital_routing_completed'] is False
    diode='sky130_fd_sc_hs__diode_2'
    out.mkdir(parents=True,exist_ok=False)
    proof_script=Path(__file__).with_name('check_physical_equivalence.py').resolve()
    files=[Path(__file__).resolve(),(ROOT/'verification/timing400/check_compact_routed_equivalence_v2.py'),(ROOT/'verification/timing400/check_compact_routed_equivalence.py'),proof_script,Path(YOSYS),LIB,LEF,gold,root/'assessment.json',root/'route.v',
           (ROOT/'verification/timing400/route_compact_candidate.py')]
    pins={str(p):sha(p) for p in files}
    def execute(command,log):
        with log.open('x') as stream:
            child=subprocess.Popen(list(map(str,command)),stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:code=child.wait(timeout=max(.001,43200-(time.monotonic()-started)))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=30)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                save(out/'timeout.json',dict(inconclusive=True,release_qualified=False));raise
        assert code==0,log.read_text()[-2000:]
    # No functional pin may disappear: the explicit physical masters have
    # only PG pins in the source LEF and no signal connections in route.v.
    lef=LEF.read_text()
    for master in sorted(PHYSICAL):
        block=re.search(r'^MACRO '+re.escape(master)+r'\s*\n(.*?)^END '+re.escape(master)+r'\s*$',lef,re.M|re.S)
        assert block,master
        pg_pins=re.findall(r'\bPIN\s+(\S+)\s*\n(.*?)\n\s*END\s+\1',block[1],re.S)
        assert pg_pins,master
        for name,body in pg_pins:
            assert re.search(r'\bUSE\s+(POWER|GROUND)\s*;',body),(master,name)
    diode_lef=re.search(r'^MACRO '+re.escape(diode)+r'\s*\n(.*?)^END '+re.escape(diode)+r'\s*$',lef,re.M|re.S)
    assert diode_lef and 'CLASS CORE ANTENNACELL' in diode_lef[1]
    diode_pins=re.findall(r'\bPIN\s+(\S+)\s*\n(.*?)\n\s*END\s+\1',diode_lef[1],re.S)
    signal_pins={name:body for name,body in diode_pins if 'USE SIGNAL' in body}
    assert set(signal_pins)=={'DIODE'} and 'DIRECTION INPUT' in signal_pins['DIODE']
    assert all('USE POWER' in body or 'USE GROUND' in body for name,body in diode_pins if name!='DIODE')
    stubs=out/'physical_stubs.v'
    stubs.write_text('\n'.join(f'module {m}(); endmodule' for m in sorted(PHYSICAL))+'\nmodule '+diode+'(input DIODE); endmodule\n')
    task=out/'projection.ys'
    task.write_text(f'''read_liberty -lib -ignore_miss_func -ignore_miss_dir {LIB}
read_verilog -lib {stubs}
read_verilog {root}/route.v
hierarchy -check -top {TOP}
check -assert
write_json {out}/before_projection.json
''')
    execute([YOSYS,'-s',task],out/'projection.log')
    module=json.loads((out/'before_projection.json').read_text())['modules'][TOP]
    removed=Counter()
    diode_connections={}
    for instance,cell in module['cells'].items():
        if cell['type'] in PHYSICAL:
            assert not cell['connections'],cell
            removed[cell['type']]+=1
        elif cell['type']==diode:
            assert set(cell['connections'])=={'DIODE'} and len(cell['connections']['DIODE'])==1
            assert cell['port_directions']=={'DIODE':'input'}
            diode_connections[instance]=cell['connections']['DIODE']
            removed[diode]+=1
    assert dict(removed)=={m:c for m,c in receipt['cell_inventory'].items() if m in PHYSICAL|{diode}}
    gold_module=json.loads(gold.read_text())['modules'][TOP]
    pg_ports=set(module['ports'])-set(gold_module['ports'])
    assert pg_ports<={'VDD','VSS'}
    assert set(gold_module['ports'])<=set(module['ports'])
    for name in sorted(pg_ports):
        port=module['ports'][name]
        assert port['direction']=='inout' and len(port['bits'])==1
        bits=set(port['bits'])
        assert not any(bits.intersection(p['bits']) for n,p in module['ports'].items() if n!=name)
        assert not any(bits.intersection(v) for c in module['cells'].values() for v in c['connections'].values())
    projection=out/'remove_physical.ys'
    projection.write_text(f'read_json {out}/before_projection.json\nhierarchy -check -top {TOP}\n'
        +''.join('delete t:'+m+'\n' for m in sorted(PHYSICAL|{diode}))
        +('delete '+' '.join('w:'+name for name in sorted(pg_ports))+'\n' if pg_ports else '')
        +f'write_verilog -noattr {out}/logic.v\n')
    execute([YOSYS,'-s',projection],out/'remove_physical.log')
    execute([sys.executable,proof_script,'--gold-json',gold,'--physical-verilog',out/'logic.v','--output',out/'proof'],out/'proof_driver.log')
    proof=verify(out/'proof/assessment.json')
    assert proof['all_transition_and_output_functions_equivalent'] and proof['corrupted_reset_function_rejected']
    for path,digest in pins.items():assert sha(Path(path))==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file()},
        projected_auxiliary_master_counts=dict(removed),all_projected_pg_only_cells_have_no_signal_connections=True,
        unused_logical_pg_ports_projected=sorted(pg_ports),
        projected_input_only_antenna_diode_connections=diode_connections,
        passive_load_effects_excluded_from_boolean_proof=True,
        matched_state_primitives=proof['matched_state_primitives'],all_transition_and_output_functions_equivalent=True,
        corrupted_reset_function_rejected=True,proof_stage='pre_detailed_routing_checkpoint',digital_routing_completed=False,physical_timing_qualified=False,release_qualified=False,
        scope='Binary transition/output equivalence after audited PG-only and input-only antenna-cell projection. Diode loading, physical connectivity/LVS and timing remain separate checks.'))
    print('Checkpoint transition/output relation proved',flush=True)


if __name__=='__main__':main()
