"""Prove sampled clear/seed capture precedes each selected DLF unmask event.

Uses the complete selected RTL and static-programming/reset contract. Physical
clock/reset propagation and analog resolution remain outside this proof.
"""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins
from resources import lease
from compiled_charge_v2 import execute
from prove_handoff_v2 import YOSYS

DLF_MONITOR='''
reg f_last_clock_clear=0;
reg [CODE_WIDTH-1:0] f_last_clear_seed;
always @(posedge CLK or negedge RESET_N) begin
    if(!RESET_N) begin f_last_clock_clear<=0;f_last_clear_seed<=0;end
    else begin
        f_last_clock_clear<=DLF_Clear;
        if(DLF_Clear) f_last_clear_seed<=DLF_Ext_Data;
    end
end
reg [1:0] f_monitor_init=0;
reg f_previous_active=0;
always @($global_clock) begin
    f_monitor_init<={f_monitor_init[0],1'b1};
    if(f_monitor_init[1] && RESET_N && loop_active && !DLF_Clear && !f_previous_active) begin
        assert(f_last_clock_clear);
        assert(f_last_clear_seed==DLF_Ext_Data);
    end
    f_previous_active<=RESET_N && loop_active && !DLF_Clear;
end
'''
PARENT_CONTRACT='''
reg [1:0] f_contract_init=0;
reg f_previous_reset=0;
reg [27:0] f_previous_inputs;
always @($global_clock) begin
    f_contract_init<={f_contract_init[0],1'b1};
    if(!f_contract_init[1]) assume(!RESET_N);
    if(f_contract_init[1] && RESET_N && f_previous_reset)
        assume({STARTUP_COARSE,STARTUP_FINE,STARTUP_INCREASING,KI,KP}==f_previous_inputs);
    f_previous_reset<=RESET_N;
    f_previous_inputs<={STARTUP_COARSE,STARTUP_FINE,STARTUP_INCREASING,KI,KP};
end
'''


def run(image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27});os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    pins=source_pins();rtl=ROOT/'rtl/selected400';sources=sorted(rtl.glob('*.v'));paths=[Path(__file__).resolve(),image,*(Path(__file__).with_name(n)for n in('common_v3.py','selected_physical_rtl.py','resources.py','compiled_charge_v2.py','prove_handoff_v2.py'))];pins.update({str(p):sha(p)for p in paths});verify(pins)
    save(output/'inputs.json',dict(input_sha256=pins,complete_selected_RTL_executed=True,physical_reset_timing_qualified=False,release_ready=False));records=[]
    try:
        for name in('baseline','clear_clock_witness_removed'):
            folder=output/name;folder.mkdir();monitor=DLF_MONITOR if name=='baseline'else DLF_MONITOR.replace('f_last_clock_clear<=DLF_Clear;','f_last_clock_clear<=0;')
            replacements={}
            for filename,properties in(('IntegerPLL_DLF.v',monitor),('IntegerPLL_ProgrammedCore.v',PARENT_CONTRACT)):
                text=(rtl/filename).read_text()
                if text.count('endmodule')!=1:raise ValueError('unique selected source module required')
                p=folder/filename;p.write_text(text.replace('endmodule',properties+'\nendmodule'));replacements[filename]=p;pins[str(p)]=sha(p)
            script=folder/'export.ys';script.write_text('read_verilog -formal -sv '+' '.join(str(replacements.get(p.name,p))for p in sources)+f'\nprep -top IntegerPLL_ProgrammedCore\nclk2fflogic\nopt\nflatten\ndelete -output\ntechmap\nopt\naigmap\nopt_clean\nwrite_aiger -zinit -symbols -map {folder}/model.map {folder}/model.aig\n');pins[str(script)]=sha(script)
            save(output/'status.json',dict(state='proving_integrated_clear_before_unmask',case=name,release_ready=False));prefix=['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image]
            with lease(1,4,deadline):
                execute([*prefix,YOSYS,'-s',script],folder/'export.log',deadline,4)
                with(folder/'model.aig').open('rb')as h:header=h.readline().decode().split()
                fields=list(map(int,header[1:]));fields += [0]*(9-len(fields))
                if header[0]!='aig'or fields[5]!=2 or fields[6]!=2:raise ValueError('two assertions and two reset/static-preset constraints required')
                execute([*prefix,str(Path(YOSYS).with_name('yosys-abc')),'-c',f'read_aiger {folder}/model.aig; fold; strash; pdr -v -d -I {folder}/invariant.pla -T 600'],folder/'proof.log',deadline,4)
            log=(folder/'proof.log').read_text();safe='Property proved'in log;unsafe='was asserted in frame'in log;expected=(safe and not unsafe)if name=='baseline'else(unsafe and not safe)
            records.append(dict(case=name,unbounded_property_proven=safe,rejecting_counterexample=unsafe,expected_result=expected))
            if not expected:raise ValueError('integrated proof/control result mismatch: '+name)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in output.rglob('*')if p.is_file()and p.name not in('status.json','inputs.json')},records=records,sampled_clear_clock_precedes_each_unmask=True,current_seed_was_sampled_on_clear_before_unmask=True,
            witness_removed_control_demonstrates_reachable_unmask=True,witness_mutation_changes_monitor_only_not_hardware=True,
            assumptions=['external reset initially asserted for two global samples','presets/gains stable between external resets','discrete RTL clocks'],
            physical_clear_arrival_timing_qualified=False,metastability_resolution_qualified=False,reset_recovery_removal_qualified=False,release_ready=False));save(output/'status.json',dict(state='sampled_clear_before_unmask_proven',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.image.resolve(),a.output.resolve())
