"""Prove two prior destination edges of payload stability before actual capture.

Discrete selected handoff RTL only. Physical clock range, request apertures,
reset timing and routed payload delays require separate correlation.
"""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from selected_physical_rtl import source_pins
from prove_handoff_v2 import YOSYS

PROPERTIES='''
reg f_seen=0;
reg f_previous_ref_reset=0,f_previous_dco_reset=0;
reg f_previous_clock=0;
reg [WIDTH-1:0] f_previous_payload=0;
reg [1:0] f_stable_edges=0;
wire f_capture_strobe=CAPTURE_STROBE;
always @($global_clock) begin
    f_seen<=1;
    f_previous_ref_reset<=REF_RESET_N;
    f_previous_dco_reset<=DCO_RESET_N;
    f_previous_clock<=DCOCLK;
    f_previous_payload<=payload;
    if(!f_seen) assume(!REF_RESET_N && !DCO_RESET_N);
    else begin
        if(f_previous_ref_reset && !REF_RESET_N) assume(!DCO_RESET_N);
        if(f_previous_dco_reset && !DCO_RESET_N) assume(!REF_RESET_N);
    end
    if(!REF_RESET_N || !DCO_RESET_N || payload!=f_previous_payload)
        f_stable_edges<=0;
    else if(DCOCLK && !f_previous_clock && f_stable_edges<3)
        f_stable_edges<=f_stable_edges+1'b1;
    if(f_seen && REF_RESET_N && DCO_RESET_N && DCOCLK && !f_previous_clock && f_capture_strobe)
        assert(payload==f_previous_payload && f_stable_edges>=2);
end
'''


def run(image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1200
    pins=source_pins();leaf=ROOT/'rtl/selected400/IntegerPLL_TuningHandoff.v';parent=ROOT/'rtl/selected400/IntegerPLL_ProgrammedCore.v'
    if parent.read_text().count('#(.WIDTH(34),.APPLY_CYCLES(3))')!=2:raise ValueError('both selected handoffs must use width34/apply3')
    for p in(image,Path(__file__).resolve(),*(Path(__file__).with_name(n) for n in ('common_v3.py','resources.py','compiled_charge_v2.py','selected_physical_rtl.py','prove_handoff_v2.py'))):pins[str(p)]=sha(p)
    save(output/'inputs.json',dict(input_sha256=pins,parameters={'WIDTH':34,'APPLY_CYCLES':3},assumptions=['both resets initially low','subsequent reset assertions coassert','independent clock stalls and reset release allowed'],physical_timing_qualified=False,release_ready=False));records=[];prefix=['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image]
    try:
        for name in ('baseline','capture_qualification_register_bypassed'):
            folder=output/name;folder.mkdir();text=leaf.read_text();strobe='capture_pending'
            if name!='baseline':
                if text.count('if(capture_pending) begin')!=1:raise ValueError('unique real capture predicate required')
                text=text.replace('if(capture_pending) begin','if(qualified_request) begin');strobe='qualified_request'
            properties=PROPERTIES.replace('CAPTURE_STROBE',strobe);source=folder/'handoff.v';source.write_text(text.replace('endmodule',properties+'\nendmodule'));script=folder/'export.ys';script.write_text(f'read_verilog -formal -sv {source}\nchparam -set WIDTH 34 -set APPLY_CYCLES 3 IntegerPLL_TuningHandoff\nprep -top IntegerPLL_TuningHandoff\nflatten\nclk2fflogic\nopt\ndelete -output\ntechmap\nopt\naigmap\nopt_clean\nwrite_aiger -zinit -symbols -map {folder}/model.map {folder}/model.aig\n');pins[str(source)]=sha(source);pins[str(script)]=sha(script);verify(pins);save(output/'status.json',dict(state='proving_payload_capture_age',case=name,release_ready=False))
            with lease(1,4,deadline):
                execute([*prefix,YOSYS,'-s',script],folder/'export.log',deadline,4)
                with (folder/'model.aig').open('rb') as stream:header=stream.readline().decode().split()
                fields=list(map(int,header[1:]));fields += [0]*(9-len(fields))
                if header[0]!='aig' or fields[5]!=1 or fields[6]!=3:raise ValueError('one age assertion and three reset-contract constraints required')
                solver=f'pdr -v -d -T 600' if name=='baseline' else 'bmc3 -F 160 -T 120 -v'
                execute([*prefix,str(Path(YOSYS).with_name('yosys-abc')),'-c',f'read_aiger {folder}/model.aig; fold; strash; {solver}'],folder/'proof.log',deadline,4)
            log=(folder/'proof.log').read_text();safe='Property proved' in log;unsafe='was asserted in frame' in log;expected=(safe and not unsafe) if name=='baseline' else (unsafe and not safe);records.append(dict(case=name,unbounded_proven=safe,counterexample=unsafe,expected_result=expected))
            if not expected:raise ValueError('capture-age proof/control did not produce required verdict: '+name)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file() and p.name not in ('inputs.json','status.json')},records=records,two_prior_destination_rising_edges_of_payload_stability_before_capture_proven=True,qualification_register_bypass_rejected=True,physical_request_capture_aperture_qualified=False,actual_frequency_range_qualified=False,payload_delay_budget_qualified=False,release_ready=False));save(output/'status.json',dict(state='payload_capture_age_proven',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.image.resolve(),a.output.resolve())
