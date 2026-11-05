"""Prove sampled bundled-transfer safety with independent, arbitrarily stalled clocks.

This is not a metastability, payload-delay, reset-recovery or integration proof.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from common import ROOT, PROFILE, save, sha, source_pins, verify
sys.path.append(str(ROOT/'verification/prototype400'))
from parallel_geometry_jobs import run_jobs

YOSYS='/nix/store/4bmfi4470w0i3ixcaidfki18d3fyqvva-yosys-with-plugins-0.62/bin/yosys'
MUTANTS={
    'overwrite_unacknowledged_payload':('if(acknowledge_sync==request && (!sent_valid || payload!=COMMAND)) begin',
                                      'if(!sent_valid || payload!=COMMAND) begin'),
    'acknowledge_before_consumer_cycles':('if(remaining==1) acknowledge<=pending_request;',
                                         'if(remaining==APPLY_CYCLES[COUNT_WIDTH-1:0]) acknowledge<=pending_request;'),
    'capture_unheld_command':('APPLIED_COMMAND<=payload;', 'APPLIED_COMMAND<=COMMAND;'),
}


def instrument(source, properties, mutant=None):
    if mutant:
        before,after=MUTANTS[mutant]
        if source.count(before)!=1:raise ValueError('handoff mutant source differs')
        source=source.replace(before,after,1)
    if source.count('endmodule')!=1:raise ValueError('expected one handoff module')
    return source.replace('endmodule',properties+'\nendmodule',1)


def run(output,container):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    started=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=started+43200
    rtl=ROOT/'rtl/prototype400/IntegerPLL_TuningHandoff.v'
    properties=Path(__file__).with_name('handoff_properties.vh')
    image=Path(container).resolve()
    paths=[Path(__file__).resolve(),Path(sys.executable),properties,rtl,image,
           Path(__file__).with_name('common.py'),ROOT/'verification/prototype400/parallel_geometry_jobs.py',
           ROOT/'verification/signoff400/resources.py',Path('/usr/bin/prlimit')]
    pins=dict(source_pins(),**{str(p):sha(p) for p in paths})
    save(out/'owner.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),
         wall_limit_s=43200,automatic_identical_retry=False,independent_case_workers=4,
         per_case_memory_limit_GiB=4,global_step_clock_edges_arbitrary=True))
    def status(state,**kw):save(out/'status.json',dict(state=state,
         observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False,**kw))
    jobs=[]
    for label in ('baseline',*MUTANTS):
        generated=out/(label+'.v')
        generated.write_text(instrument(rtl.read_text(),properties.read_text(),None if label=='baseline' else label))
        task=out/(label+'.ys')
        task.write_text(f'''read_verilog -formal -sv {generated}
chparam -set WIDTH 34 -set APPLY_CYCLES 3 IntegerPLL_TuningHandoff
prep -top IntegerPLL_TuningHandoff
clk2fflogic
opt
check -assert
sat -seq 2 -tempinduct -maxsteps 60 -set-def-inputs -prove-asserts -verify -show-inputs -show-outputs
''')
        jobs.append(dict(label=label,command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,YOSYS,'-s',task],
                         cpus=1,memory_gib=4,allow_nonzero=True))
    try:
        results=run_jobs(jobs,out,pins,deadline,workers=4,
                         update=lambda **kw:status('parallel_sampled_handoff_proofs_running',**kw))
        records=[]
        for label in ('baseline',*MUTANTS):
            text=(out/(label+'.log')).read_text()
            proven=results[label]==0 and 'Induction step proven: SUCCESS!' in text
            rejected=results[label]!=0 and ('proof did fail' in text or 'model found: FAIL' in text)
            records.append(dict(label=label,native_exit=results[label],unbounded_induction_pass=proven,rejecting_counterexample=rejected))
        save(out/'case_results.json',records)
        if not records[0]['unbounded_induction_pass']:raise RuntimeError('handoff baseline lacks unbounded safety proof')
        if not all(r['rejecting_counterexample'] for r in records[1:]):raise RuntimeError('handoff mutant lacks rejecting counterexample')
        verify(pins)
        save(out/'assessment.json',dict(profile_sha256=sha(PROFILE),candidate_source_sha256=source_pins(),
            input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
            records=records,sampled_handoff_safety_proven=True,all_three_negative_controls_rejected=True,
            assumptions=['both domain resets initially asserted',
                         'a subsequent assertion of either reset asserts both together',
                         'reset releases may differ; each input clock may stall or change independently',
                         'discrete RTL sampling; no metastability or analog timing abstraction'],
            physical_timing_qualified=False,interface_model_qualified=False,digital_startup_qualified=False,
            release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started))
        status('sampled_handoff_safety_proven_pending_physical_and_integration_bounds')
    except BaseException as error:
        status('failed',reason=repr(error));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--container',required=True,type=Path)
    a=parser.parse_args();run(a.output,a.container)
