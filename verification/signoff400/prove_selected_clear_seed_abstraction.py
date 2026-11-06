"""Prove sampled clear/seed capture precedes each selected DLF unmask event.

Uses eight per-bit sound command-comparison overapproximations.
Uses selected control RTL with explicit unconstrained datapath outputs and the
static-programming/reset contract. Physical
clock/reset propagation and analog resolution remain outside this proof.
"""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins
from resources import lease
from compiled_charge_v2 import execute
from prove_handoff_v2 import YOSYS
from abstract_selected_handoff_comparisons import abstract

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


CORE_MONITOR=re.sub(r'\bCODE_WIDTH\b','DLF_CODE_WIDTH',DLF_MONITOR)
CORE_MONITOR=re.sub(r'\bCLK\b','dlf_clk',CORE_MONITOR)
CORE_MONITOR=re.sub(r'\bRESET_N\b','dlf_reset_n',CORE_MONITOR)
CORE_MONITOR=re.sub(r'\bloop_active\b','(DLF_En && !DLF_Ext_Override)',CORE_MONITOR)

def run(image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27});os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+6000
    pins=source_pins();rtl=ROOT/'rtl/selected400';sources=sorted(rtl.glob('*.v'));paths=[Path(__file__).resolve(),image,*(Path(__file__).with_name(n)for n in('common_v3.py','selected_physical_rtl.py','resources.py','compiled_charge_v2.py','prove_handoff_v2.py','abstract_selected_handoff_comparisons.py'))];pins.update({str(p):sha(p)for p in paths});verify(pins)
    save(output/'inputs.json',dict(input_sha256=pins,selected_reset_handshake_and_startup_RTL_preserved=True,unconstrained_cut_outputs=['core.CLKDIV_RETIMED','core.DCO_CODE'],abstraction_is_behavioral_overapproximation=True,physical_reset_timing_qualified=False,release_ready=False));records=[]
    try:
        for name in (f'seed_bit_{i}' for i in range(2,10)):
            folder=output/name;folder.mkdir();monitor=CORE_MONITOR
            if name.startswith('seed_bit_'):
                bit=int(name.rsplit('_',1)[1])
                monitor=monitor.replace('assert(f_last_clock_clear);','').replace('assert(f_last_clear_seed==DLF_Ext_Data);',f'assert(f_last_clear_seed[{bit}]==DLF_Ext_Data[{bit}]);')
            else:
                monitor=monitor.replace('assert(f_last_clear_seed==DLF_Ext_Data);','')
            if name=='clear_clock_witness_removed':
                monitor=monitor.replace('f_last_clock_clear<=DLF_Clear;','f_last_clock_clear<=0;')
            replacements={}
            for filename,properties in(('IntegerPLL_DigitalCore.v',monitor),('IntegerPLL_ProgrammedCore.v',PARENT_CONTRACT)):
                text=(rtl/filename).read_text()
                if text.count('endmodule')!=1:raise ValueError('unique selected source module required')
                p=folder/filename;p.write_text(text.replace('endmodule',properties+'\nendmodule'));replacements[filename]=p;pins[str(p)]=sha(p)
            script=folder/'export.ys';script.write_text('read_verilog -formal -sv '+' '.join(str(replacements.get(p.name,p))for p in sources)+f'\nprep -top IntegerPLL_ProgrammedCore\nflatten\nselect -assert-count 1 w:core.CLKDIV_RETIMED\nselect -assert-count 1 w:core.DCO_CODE\ncutpoint w:core.CLKDIV_RETIMED w:core.DCO_CODE\nwrite_json {folder}/abstraction.json\nclk2fflogic\nopt\ndelete -output\ntechmap\nopt\naigmap\nopt_clean\nwrite_aiger -zinit -symbols -map {folder}/model.map {folder}/model.aig\n');pins[str(script)]=sha(script)
            save(output/'status.json',dict(state='proving_integrated_clear_before_unmask',case=name,release_ready=False));prefix=['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image]
            with lease(1,4,deadline):
                execute([*prefix,YOSYS,'-s',script],folder/'export.log',deadline,4)
                abstraction=json.loads((folder/'abstraction.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
                cuts=[c['connections']['Y']for c in abstraction['cells'].values()if c['type']=='$anyseq']
                expected_cuts=[abstraction['netnames'][n]['bits']for n in('core.CLKDIV_RETIMED','core.DCO_CODE')]
                if sorted(map(len,cuts))!=[1,8]or sorted(cuts)!=sorted(expected_cuts):raise ValueError('only the declared clock/code outputs may become unconstrained')
                with(folder/'model.aig').open('rb')as h:header=h.readline().decode().split()
                fields=list(map(int,header[1:]));fields += [0]*(9-len(fields))
                if header[0]!='aig'or fields[5]!=1 or fields[6]!=2:raise ValueError('one assertion and two reset/static-preset constraints required')
                original=json.loads((folder/'abstraction.json').read_text())
                modified,comparisons=abstract(original,bit-2)
                abstracted=folder/'abstracted.json';save(abstracted,modified);save(folder/'comparisons.json',comparisons)
                pins[str(abstracted)]=sha(abstracted);pins[str(folder/'comparisons.json')]=sha(folder/'comparisons.json')
                export=folder/'abstract_export.ys';export.write_text(f'read_json {abstracted}\nclk2fflogic\nopt\ndelete -output\ntechmap\nopt\naigmap\nopt_clean\nwrite_aiger -zinit -symbols -map {folder}/abstract.map {folder}/abstract.aig\n');pins[str(export)]=sha(export)
                execute([*prefix,YOSYS,'-s',export],folder/'abstract_export.log',deadline,4)
                execute([*prefix,str(Path(YOSYS).with_name('yosys-abc')),'-c',f'read_aiger {folder}/abstract.aig; fold; strash; pdr -v -d -I {folder}/invariant.pla -T 600'],folder/'proof.log',deadline,4)
            log=(folder/'proof.log').read_text();safe='Property proved'in log;unsafe='was asserted in frame'in log;expected=(safe and not unsafe)if name!='clear_clock_witness_removed'else(unsafe and not safe)
            records.append(dict(case=name,undecided='Property UNDECIDED' in log,unbounded_property_proven=safe,rejecting_counterexample=unsafe,expected_result=expected))
            if not expected:raise ValueError(('proof timed out without verdict: ' if 'Property UNDECIDED' in log else 'integrated proof/control result mismatch: ')+name)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in output.rglob('*')if p.is_file()and p.name not in('status.json','inputs.json')},records=records,command_comparison_overapproximation=True,proof_decomposition='All eight variable seed-bit equalities, each with a sound per-bit command-comparison overapproximation; clear witness and constant bits are separate prior proofs.',sampled_clear_clock_precedes_each_unmask=False,current_seed_was_sampled_on_clear_before_unmask=True,
            witness_removed_control_demonstrates_abstract_control_unmask_reachable=False,witness_mutation_changes_monitor_only_not_hardware=True,
            abstraction='Feedback-clock and fine-code outputs are unconstrained. Four 34-bit command comparisons retain coarse/run/one-seed-bit equality and replace omitted-field equality with independent inputs. Every original trace has the original omitted-field equality as its witness.',assumptions=['external reset initially asserted for two global samples','presets/gains stable between external resets','discrete RTL clocks'],
            physical_clear_arrival_timing_qualified=False,metastability_resolution_qualified=False,reset_recovery_removal_qualified=False,release_ready=False));save(output/'status.json',dict(state='sampled_clear_before_unmask_proven',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.image.resolve(),a.output.resolve())
