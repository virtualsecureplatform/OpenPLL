"""Read every diagnostic native Liberty view in the pinned timing engine."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
from common_v3 import ROOT, save, sha, verify
from compiled_charge import execute
from resources import lease


def inside(config):
    c=json.loads(config.read_text());verify(c['input_sha256'])
    remaining=c['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    if remaining<=0:raise TimeoutError('library parser deadline')
    subprocess.run([c['openroad'],'-exit',c['script']],check=True,timeout=remaining)
    verify(c['input_sha256'])
    save(Path(c['native_receipt']),dict(pinned_timing_engine_and_library_inputs_verified=True,
                                      native_library_query_completed=True))


def run(source,output):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    files=[source/f'{c}_{v}.lib' for c in ('tt','ff','ss','sf','fs') for v in ('early','late')]
    if {str(p) for p in files}!={p for p in r['artifacts'] if p.endswith('.lib')}:raise ValueError('exact five-corner early/late view set required')
    tools=[p for p in r['input_sha256'] if p.endswith('/bin/openroad')]
    if len(tools)!=1:raise ValueError('pinned timing engine identity required')
    tool=tools[0];image=ROOT/'build/apptainer/openpll-release-modern.sif'
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    table=output/'cells.tsv';script=output/'read.tcl'
    corners=[p.stem for p in files]
    text='define_corners '+' '.join(corners)+'\nset out [open {'+str(table)+'} w]\n'
    for p in files:
        lib='prototype_'+p.stem
        text+=f'read_liberty -corner {p.stem} {{{p}}}\n'
        text+=f'set cells [get_lib_cells -quiet {lib}/*]\n'
        text+=f'if {{[llength $cells]!={r["routed_cell_masters"]}}} {{error {{native view cell inventory differs}}}}\n'
        text+=f'puts $out [join [list {p.stem} [llength $cells]] "\\t"]\n'
        for master in ('dfrtp_1','dfrtp_2','dfrtp_4','dfstp_1','dfstp_2'):
            for pin in ('CLK','D','Q','RESET_B' if master.startswith('dfrtp') else 'SET_B'):
                text+=f'if {{[llength [get_lib_pins -quiet {lib}/sky130_fd_sc_hs__{master}/{pin}]]!=1}} {{error {{native FF functional pin missing}}}}\n'
    text+='close $out\nreport_lib_cell prototype_tt_late/sky130_fd_sc_hs__dfrtp_1\nreport_lib_cell prototype_tt_late/sky130_fd_sc_hs__clkinv_1\nexit\n'
    script.write_text(text);config=output/'config.json';native=output/'native_receipt.json'
    native_inputs={str(p):sha(p) for p in (*files,script,Path(__file__).resolve())}
    native_inputs[tool]=r['input_sha256'][tool]
    save(config,dict(input_sha256=native_inputs,openroad=tool,script=str(script),
                     native_receipt=str(native),deadline_uptime=deadline))
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with lease(1,4,deadline):
        execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/usr/bin/python3',
                 Path(__file__).resolve(),'--inside',config],output/'read.log',deadline,4)
    log=(output/'read.log').read_text()
    if re.search(r'\[ERROR|Error:|invalid command name',log):raise ValueError('native library parser error')
    rows=[line.split('\t') for line in table.read_text().splitlines()]
    if rows!=[[p.stem,str(r['routed_cell_masters'])] for p in files]:raise ValueError('complete native library inventories required')
    pins={str(p):sha(p) for p in (receipt,*files,image,script,config,Path(__file__).resolve())};verify(pins)
    artifacts={str(p):sha(p) for p in (table,native,output/'read.log')}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,libraries_read=10,
         every_library_cell_inventory_and_FF_functional_pin_verified=True,
         parser_warnings=[line for line in log.splitlines() if '[WARNING' in line or 'Warning:' in line],
         sequential_constraint_semantics_and_routed_timing_verified=False,
         physical_timing_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inside',type=Path);p.add_argument('--source',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.inside:inside(a.inside)
    elif a.source and a.output:run(a.source.resolve(),a.output.resolve())
    else:p.error('inside config or source and output required')
