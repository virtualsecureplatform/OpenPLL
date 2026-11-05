"""Controlled PDR proof of sampled BBPD synchronizer data at reset release."""
import argparse,json,os,time,re
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute
from prove_handoff_v2 import YOSYS


def instrument(text,mutant=False):
    anchor='(* ASYNC_REG="TRUE" *) reg [1:0] up_pipe, dn_pipe;'
    if text.count(anchor)!=1:raise ValueError('unique actual event synchronizer source required')
    prop='''
    reg [1:0] f_init=0;
    reg f_previous_reset=0;
    always @($global_clock) begin
        f_init<={f_init[0],1'b1};
        if (!f_init[1]) assume(!RESET_N);
        if (f_init[1] && fast_reset_n && !f_previous_reset)
            assert(f_pipe_zero);
        f_previous_reset<=fast_reset_n;
    end
'''
    text=text.replace(anchor,anchor+'\nassign f_pipe_zero=(up_pipe==0 && dn_pipe==0);')
    if text.count('endmodule')!=1:raise ValueError('single source module required')
    text=text.replace('endmodule','wire f_pipe_zero;\n'+prop+'\nendmodule')
    if mutant:
        old='if(!fast_reset_n) begin up_pipe<=0;dn_pipe<=0;end'
        if text.count(old)!=1:raise ValueError('unique reset branch required for negative control')
        text=text.replace(old,"if(!fast_reset_n) begin up_pipe<=2'b11;dn_pipe<=0;end")
    return text


def run(candidate,output):
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    receipt=candidate/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    sources=sorted((candidate/'rtl').glob('*.v'))
    digital=candidate/'rtl/IntegerPLL_DigitalCore.v'
    if len(sources)!=9 or digital not in sources:raise ValueError('complete isolated candidate RTL required')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';abc=str(Path(YOSYS).with_name('yosys-abc'))
    paths=[receipt,*sources,image,Path(__file__).resolve(),Path(__file__).with_name('prove_handoff_v2.py')]
    pins={str(p):sha(p) for p in paths}
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    prefix=['apptainer','exec','--bind','/home:/home',image];results=[];artifacts={}
    for name,mutant in (('baseline',False),('reset_data_negative_control',True)):
        folder=output/name;folder.mkdir();design=folder/'IntegerPLL_DigitalCore.v';design.write_text(instrument(digital.read_text(),mutant))
        recipe=folder/'export.ys'
        files=[design if p==digital else p for p in sources]
        recipe.write_text('read_verilog -formal -sv '+' '.join(map(str,files))+'''
chparam -set SYNCHRONIZE_RESETS 1 -set BBPD_EVENT_CDC 1 -set BBPD_CAPTURE_INDEPENDENT 1 IntegerPLL_DigitalCore
prep -top IntegerPLL_DigitalCore
clk2fflogic
opt
flatten
delete -output
techmap
opt
aigmap
opt_clean
'''+f'write_aiger -zinit -symbols -map {folder}/model.map {folder}/model.aig\n')
        with lease(1,4,deadline):
            execute([*prefix,YOSYS,'-s',recipe],folder/'export.log',deadline,4)
            execute([*prefix,abc,'-c',f'read_aiger {folder}/model.aig; fold; strash; pdr -v -d -I {folder}/invariant.pla -T 3600'],folder/'proof.log',deadline,4)
        log=(folder/'proof.log').read_text();safe='Property proved' in log;unsafe='was asserted in frame' in log
        header=(folder/'model.aig').open('rb').readline().decode().split()
        values=list(map(int,header[1:]));values += [0]*(9-len(values))
        if header[0]!='aig' or values[5]!=1 or values[6]!=1:raise ValueError('one assertion and one initialization constraint required')
        results.append(dict(case=name,proved=safe,counterexample=unsafe,expected_safe=not mutant,latches=values[2]))
        artifacts.update({str(p):sha(p) for p in folder.iterdir() if p.is_file()})
    verify(pins);save(output/'results.json',results);artifacts[str(output/'results.json')]=sha(output/'results.json')
    if not all(x['proved']==x['expected_safe'] and x['counterexample']!=x['expected_safe'] for x in results):raise ValueError('PDR proof or negative control did not match')
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
        first_synchronizer_stage_zero_at_sampled_fast_reset_release_proved=True,
        second_stage_D_equals_reset_value_at_sampled_release=True,reset_data_negative_control_rejected=True,
        source_scope='actual candidate DigitalCore with synchronized resets, event CDC and independent capture enabled',
        assumptions=['RESET_N asserted for first two global samples','ideal sampled RTL clocks; no analog metastability model'],
        native_recovery_removal_qualification_complete=False,timing_exceptions_generated=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('candidate','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.candidate.resolve(),a.output.resolve())
