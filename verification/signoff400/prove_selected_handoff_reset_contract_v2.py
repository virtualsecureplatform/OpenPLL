"""Prove the selected top supplies the standalone handoff reset assumptions.

Discrete RTL only: asynchronous physical recovery/removal remains a timing gate.
"""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins
from resources import lease
from compiled_charge_v2 import execute
from prove_handoff_v2 import YOSYS

PROPERTIES='''
reg f_seen=0;
reg f_previous_ref_reset, f_previous_fast_reset, f_previous_fine_reset;
always @($global_clock) begin
    f_seen<=1;
    f_previous_ref_reset<=ref_reset_n;
    f_previous_fast_reset<=dco_reset_n;
    f_previous_fine_reset<=fine_reset_n;
    if(!f_seen) assume(!RESET_N);
    else begin
        if(f_previous_ref_reset && !ref_reset_n) begin
            assert(!dco_reset_n);
            assert(!fine_reset_n);
        end
        if(f_previous_fast_reset && !dco_reset_n) assert(!ref_reset_n);
        if(f_previous_fine_reset && !fine_reset_n) assert(!ref_reset_n);
        if(!$past(RESET_N)) begin
            assert(!ref_reset_n);
            assert(!dco_reset_n);
            assert(!fine_reset_n);
        end
    end
end
'''


def run(image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{25})
    pins=source_pins();rtl=ROOT/'rtl/selected400';top=rtl/'IntegerPLL_ProgrammedCore.v'
    source=top.read_text()
    checks={'.REF_RESET_N(ref_reset_n)':3,'.DCO_RESET_N(dco_reset_n)':1,'.DCO_RESET_N(reset_pipe[1])':1,'assign fine_reset_n=reset_pipe[1];':1}
    if any(source.count(s)!=n for s,n in checks.items()):raise ValueError('selected handoff reset port connections changed')
    leaf=rtl/'IntegerPLL_TuningHandoff.v';proof=ROOT/'build/signoff400/handoff_pdr_002/assessment.json';a=json.loads(proof.read_text())
    old=ROOT/'rtl/prototype400/IntegerPLL_TuningHandoff.v'
    if a['input_sha256'][str(old)]!=sha(leaf)or a['sampled_handoff_safety_proven']is not True:raise ValueError('standalone reset contract proof differs from selected leaf')
    for p in(image,proof,Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('selected_physical_rtl.py'),Path(__file__).with_name('resources.py'),Path(__file__).with_name('compiled_charge_v2.py'),Path(__file__).with_name('prove_handoff_v2.py')):pins[str(p)]=sha(p)
    save(output/'inputs.json',dict(input_sha256=pins,scope='selected top reset assumption discharge, arbitrary independently stalled clocks',release_ready=False))
    results=[];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    try:
        for name in('baseline','fast_reset_polarity_mutant'):
            folder=output/name;folder.mkdir();text=source
            if name!='baseline':
                before='if(!RESET_N) dco_reset_pipe<=0;'
                if text.count(before)!=1:raise ValueError('negative control reset source differs')
                text=text.replace(before,"if(!RESET_N) dco_reset_pipe<=2'b11;")
            generated=folder/'top.v';generated.write_text(text.replace('endmodule',PROPERTIES+'\nendmodule'))
            sources=sorted(p for p in rtl.glob('*.v')if p!=top)
            script=folder/'proof.ys';script.write_text('read_verilog -formal -sv '+ ' '.join(map(str,[*sources,generated]))+'\nchparam -set DLF_UPDATE_ON_PLLOUT 0 IntegerPLL_ProgrammedCore\nprep -top IntegerPLL_ProgrammedCore\nflatten\nclk2fflogic\nopt_clean\nopt\ndelete -output\ntechmap\nopt\naigmap\nopt_clean\nwrite_aiger -zinit -symbols -map ' + str(folder/'model.map') + ' ' + str(folder/'model.aig') + '\n')
            for p in(generated,script):pins[str(p)]=sha(p)
            verify(pins);save(output/'status.json',dict(state='reset_contract_proof_running',case=name,release_ready=False))
            command=['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,YOSYS,'-s',script]
            with lease(1,4,deadline):execute(command,folder/'export.log',deadline,4)
            model=folder/'model.aig'
            with model.open('rb')as stream:header=stream.readline().decode().split()
            fields=list(map(int,header[1:]));fields += [0]*(9-len(fields))
            if header[0]!='aig'or fields[3]!=0 or fields[5]!=7 or fields[6]!=1:raise ValueError('seven assertions and one initial reset assumption required')
            pins[str(model)]=sha(model);pins[str(folder/'model.map')]=sha(folder/'model.map')
            command=['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,str(Path(YOSYS).with_name('yosys-abc')),'-c',f'read_aiger {model}; fold; strash; pdr -v -d -I {folder}/invariant.pla -T 900']
            with lease(1,4,deadline):execute(command,folder/'proof.log',deadline,4)
            log=(folder/'proof.log').read_text();safe='Property proved'in log;counterexample='was asserted in frame'in log
            valid=(safe and not counterexample)if name=='baseline'else(counterexample and not safe)
            results.append(dict(case=name,unbounded_safety_proven=safe,rejecting_counterexample=counterexample,expected_result=valid))
            if not valid:raise RuntimeError('formal result does not match control expectation: '+name)
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in output.rglob('*')if p.is_file()and p.name=='proof.log'},results=results,
            selected_top_supplies_sampled_handoff_coassertion_contract=True,
            assumptions=['external RESET_N initially asserted','arbitrary subsequent external reset and clock changes','discrete RTL sampling'],
            physical_recovery_removal_qualified=False,payload_timing_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='selected_reset_contract_proven',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.image.resolve(),a.output.resolve())
