"""Export a native branch-ECO checkpoint for a separately scoped Boolean proof."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import time
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge_v2 import execute
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import OPENROAD


def run(checkpoint,source,output):
    manifest=checkpoint/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    rr=source/'assessment.json';r=json.loads(rr.read_text());verify(r['artifacts'])
    if m['input_sha256'].get(str(rr))!=sha(rr):raise ValueError('checkpoint source differs')
    db=checkpoint/'antenna_repaired.odb';owner=checkpoint/'owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise ValueError('original deadline expired')
    output.mkdir(parents=True,exist_ok=False);script=output/'export.tcl'
    script.write_text(f'read_db {{{db}}}\nset_thread_count 1\nwrite_verilog {{{output/"route.v"}}}\nwrite_verilog -include_pwr_gnd {{{output/"powered.v"}}}\nset f [open {{{output/"masters.txt"}}} w]\nforeach inst [[ord::get_db_block] getInsts] {{puts $f [[$inst getMaster] getName]}}\nclose $f\nexit\n')
    inputs={str(p):sha(p) for p in (manifest,rr,db,owner,script,Path(OPENROAD),Path(__file__).resolve(),
        Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('resources.py'),Path(__file__).with_name('compiled_charge_v2.py'))}
    os.environ.update(OMP_NUM_THREADS='1',GOMAXPROCS='1',OPENBLAS_NUM_THREADS='1')
    with lease(1,4,deadline):execute([OPENROAD,'-no_init','-exit',script],output/'export.log',deadline,4)
    verify(inputs)
    save(output/'assessment.json',dict(input_sha256=inputs,
        artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file()},
        candidate_source_sha256=r['candidate_source_sha256'],
        cell_inventory=dict(Counter((output/'masters.txt').read_text().splitlines())),
        logic_checkpoint_export_completed=True,digital_routing_completed=False,
        physical_signoff_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('checkpoint','source','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ('checkpoint','source','output')))
