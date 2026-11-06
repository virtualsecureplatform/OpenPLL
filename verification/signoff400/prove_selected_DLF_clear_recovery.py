"""Prove one valid clear edge repairs arbitrary prior selected DLF state.

No initial reset/state assumption is made. This discrete repair/masking property
is not a metastability-resolution bound or physical reset-timing waiver.
"""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins
from resources import lease
from compiled_charge_v2 import execute
from prove_handoff_v2 import YOSYS

PROPERTIES='''
reg f_valid=0;
reg f_previous_clear;
reg [CODE_WIDTH-1:0] f_previous_seed;
always @(*) begin
    if(DLF_Clear || DLF_Ext_Override) assert(DLF_CODE==DLF_Ext_Data);
end
always @(posedge CLK or negedge RESET_N) begin
    if(!RESET_N) begin
        f_valid<=0;
        f_previous_clear<=0;
        f_previous_seed<=0;
    end else begin
        if(f_valid && f_previous_clear) begin
            assert(integ_acc==$signed({1'b0,f_previous_seed,{FRAC_WIDTH{1'b0}}}));
            assert(!acq_last_inc);
            assert(!acq_last_dec);
            assert(acq_same_dir_count==0);
        end
        f_valid<=1;
        f_previous_clear<=DLF_Clear;
        f_previous_seed<=DLF_Ext_Data;
    end
end
'''


def run(image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27});os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    pins=source_pins();rtl=ROOT/'rtl/selected400';leaf=rtl/'IntegerPLL_DLF.v';decoder=rtl/'IntegerPLL_B2TH.v';parent=rtl/'IntegerPLL_ProgrammedCore.v'
    if parent.read_text().count('IntegerPLL_DigitalCore #(.DLF_FRAC_WIDTH(2),.DLF_PROP_RAIL_GUARD(1),')!=1:raise ValueError('selected filter instantiation differs')
    paths=[Path(__file__).resolve(),image,*(Path(__file__).with_name(n)for n in('common_v3.py','selected_physical_rtl.py','resources.py','compiled_charge_v2.py','prove_handoff_v2.py'))];pins.update({str(p):sha(p)for p in paths});verify(pins)
    save(output/'inputs.json',dict(input_sha256=pins,initial_DLF_state_assumptions=0,initial_reset_assumptions=0,parameters=dict(CODE_WIDTH=10,FRAC_WIDTH=2,PROP_RAIL_GUARD=1),release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600;records=[]
    try:
        for name in('baseline','clear_load_removed','output_mask_removed'):
            folder=output/name;folder.mkdir();text=leaf.read_text()
            if name=='clear_load_removed':
                token='integ_acc <= ext_acc;'
                if text.count(token)!=1:raise ValueError('unique actual clear load required')
                text=text.replace(token,'integ_acc <= ACC_ZERO;')
            elif name=='output_mask_removed':
                token='assign DLF_CODE = (DLF_Ext_Override || DLF_Clear) ? DLF_Ext_Data : loop_code;'
                if text.count(token)!=1:raise ValueError('unique actual output mask required')
                text=text.replace(token,'assign DLF_CODE = loop_code;')
            if text.count('endmodule')!=1:raise ValueError('unique DLF module required')
            model=folder/'DLF.v';model.write_text(text.replace('endmodule',PROPERTIES+'\nendmodule'))
            recipe=folder/'export.ys';recipe.write_text(f'read_verilog -formal -sv {model} {decoder}\nchparam -set CODE_WIDTH 10 -set FRAC_WIDTH 2 -set PROP_RAIL_GUARD 1 IntegerPLL_DLF\nprep -top IntegerPLL_DLF\nflatten\nclk2fflogic\nopt\ndelete -output\ntechmap\nopt\naigmap\nopt_clean\nwrite_aiger -zinit -symbols -map {folder}/model.map {folder}/model.aig\n')
            pins.update({str(p):sha(p)for p in(model,recipe)});save(output/'status.json',dict(state='proving_clear_recovery',case=name,release_ready=False))
            prefix=['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image]
            with lease(1,2,deadline):
                execute([*prefix,YOSYS,'-s',recipe],folder/'export.log',deadline,2)
                with(folder/'model.aig').open('rb')as h:header=h.readline().decode().split()
                values=list(map(int,header[1:]));values += [0]*(9-len(values))
                if header[0]!='aig'or values[5]!=5 or values[6]!=0:raise ValueError('five assertions with no environment constraints required')
                execute([*prefix,str(Path(YOSYS).with_name('yosys-abc')),'-c',f'read_aiger {folder}/model.aig; fold; strash; pdr -v -d -I {folder}/invariant.pla -T 120'],folder/'proof.log',deadline,2)
            log=(folder/'proof.log').read_text();safe='Property proved'in log;unsafe='was asserted in frame'in log;expected=(safe and not unsafe)if name=='baseline'else(unsafe and not safe)
            records.append(dict(case=name,unbounded_property_proven=safe,rejecting_counterexample=unsafe,expected_result=expected))
            if not expected:raise ValueError('proof/control result mismatch: '+name)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in output.rglob('*')if p.is_file()and p.name not in('status.json','inputs.json')},records=records,
            arbitrary_prior_filter_state_repaired_by_one_valid_clear_clock=True,output_override_independent_of_prior_state=True,environment_constraints=0,
            physical_reset_recovery_removal_qualified=False,metastability_resolution_bound_qualified=False,integrated_clear_clock_arrival_guarantee_qualified=False,release_ready=False));save(output/'status.json',dict(state='arbitrary_state_clear_repair_proven',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.image.resolve(),a.output.resolve())
