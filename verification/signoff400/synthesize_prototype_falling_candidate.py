"""Freeze and map a falling-edge decision-register candidate without changing the baseline."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from common_v3 import ROOT,PROFILE,RTL,TOP,save,sha,verify,source_pins
from resources import identity,lease
from compiled_charge import execute
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import ALLOWED,LIB,YOSYS


def revised_digital(original):
    before='reg [1:0] decision_q;\n            always @(posedge dlf_clk or negedge dlf_reset_n)'
    after='reg [1:0] decision_q;\n            always @(negedge dlf_clk or negedge dlf_reset_n)'
    if original.count(before)!=1:raise ValueError('unique baseline decision-register clock required')
    return original.replace(before,after)


def run(experiment,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    er=experiment/'assessment.json';r=json.loads(er.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if r.get('decision_register_clock_edge')!='falling' or not r['experimental_trace_limits_passed'] or r['physical_models_qualified']:raise ValueError('matching complete short-pipeline diagnostic required')
    baseline=ROOT/'rtl/prototype400/IntegerPLL_DigitalCore.v';change=experiment/'IntegerPLL_DigitalCore.v'
    if change.read_text()!=revised_digital(baseline.read_text()):raise ValueError('experiment differs beyond the single decision-register clock edge')
    source_dir=output/'rtl';source_dir.mkdir();actual=[]
    for path in [*RTL,TOP]:
        target=source_dir/path.name
        if target.exists():raise ValueError('candidate source basename collision')
        shutil.copyfile(change if path==baseline else path,target)
        if path!=TOP:actual.append(target)
    sources=output/'sources.json';save(sources,dict(files=[str(p.relative_to(output)) for p in actual],physical_top=str((source_dir/TOP.name).relative_to(output))))
    candidate_sources={str(p):sha(p) for p in [*actual,source_dir/TOP.name,sources]}
    pins={str(p):sha(p) for p in (PROFILE,er,change,LIB,Path(YOSYS),Path(__file__).resolve(),ROOT/'verification/timing400/check_compact_mapping.py')};pins.update(source_pins());pins.update(candidate_sources)
    bench=ROOT/'tb/tb_programmed400.v';pins[str(bench)]=sha(bench);binary=output/'controls.vvp'
    def invoke(command,log,cpus=1):
        verify(pins)
        with lease(cpus,4,deadline):execute(command,log,deadline,4)
    invoke(['/usr/bin/iverilog','-g2012','-s','tb_programmed400','-o',binary,*actual,bench],output/'compile.log')
    invoke(['/usr/bin/vvp',binary],output/'controls.log')
    match=re.search(r'PASS: programmed400 digital startup controls checks=(\d+)',(output/'controls.log').read_text())
    if not match:raise ValueError('candidate digital startup controls did not pass')
    cells=set(re.findall(r'cell\s*\(\s*"?([^\s"\)]+)',LIB.read_text()));models=[]
    supported_ff={'sky130_fd_sc_hs__'+name for name in ('dfrtp_1','dfrtp_2','dfrtp_4','dfstp_1','dfstp_4')}
    ff_exclusions=' '.join('-dont_use '+c for c in sorted(cells) if c.startswith('sky130_fd_sc_hs__df') and c not in supported_ff)
    for label in ('full','compact'):
        folder=output/label;folder.mkdir();excluded={c for c in cells if 'probe' in c or 'lpflow' in c} if label=='full' else cells-ALLOWED
        task=folder/'synth.ys';task.write_text(f'''read_verilog {' '.join(map(str,actual))}
hierarchy -check -top IntegerPLL_ProgrammedCore
synth -top IntegerPLL_ProgrammedCore -flatten
dfflibmap -liberty {LIB} {ff_exclusions}
abc -liberty {LIB} -D 2222 {' '.join('-dont_use '+c for c in sorted(excluded))}
hilomap -hicell sky130_fd_sc_hs__conb_1 HI -locell sky130_fd_sc_hs__conb_1 LO
clean
delete t:$scopeinfo
read_liberty -lib -ignore_miss_func -ignore_miss_dir {LIB}
check -assert
stat -liberty {LIB}
write_verilog -norename {folder}/mapped.v
write_json {folder}/mapped.json
''')
        save(output/'status.json',dict(state='mapping_falling_decision_candidate',mapping=label,release_ready=False))
        invoke([YOSYS,'-s',task],folder/'synth.log')
        module=json.loads((folder/'mapped.json').read_text())['modules']['IntegerPLL_ProgrammedCore'];counts=Counter(c['type'] for c in module['cells'].values())
        if label=='compact' and not set(counts)<=ALLOWED:raise ValueError('unsupported compact candidate master')
        artifacts={str(p):sha(p) for p in (task,folder/'synth.log',folder/'mapped.v',folder/'mapped.json')}
        save(folder/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,candidate_source_sha256=candidate_sources,source_change='move_decision_register_to_falling_divided_clock_edge',synthesis=dict(cells=sum(counts.values()),counts=dict(counts)),physical_timing_qualified=False,release_ready=False))
        models.append(dict(label=label,cells=sum(counts.values()),masters=len(counts)))
    proof=output/'mapping_proof';checker=ROOT/'verification/prototype400/check_mapping.py';pins[str(checker)]=sha(checker)
    invoke(['/usr/bin/python3',checker,'--gold',output/'full','--gate',output/'compact','--output',proof],output/'mapping_proof.log')
    checked=json.loads((proof/'assessment.json').read_text());verify(checked['input_sha256']);verify(checked['artifacts'])
    if not checked['all_transition_clock_reset_and_output_functions_equivalent'] or not checked['corrupted_data_function_rejected']:raise ValueError('candidate mapping proof incomplete')
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [sources,*actual,source_dir/TOP.name,er,output/'controls.log',output/'compile.log',output/'mapping_proof.log',proof/'assessment.json',output/'full/assessment.json',output/'compact/assessment.json']},
        candidate_source_sha256=candidate_sources,controls_checks=int(match[1]),mappings=models,
        full_and_compact_state_transition_mappings_equivalent=True,mapping_negative_control_rejected=True,
        physical_candidate_rebuilt=False,related_clock_transfer_timing_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='falling_decision_candidate_mapped_and_proved',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--experiment',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.experiment.resolve(),a.output.resolve())
