"""Controlled PDR proof of enabled decision update phase at divided-clock falling edges."""
import argparse,json,os,time,re
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute
from prove_handoff_v2 import YOSYS


def instrument(text,mutant=False):
    prop='''
reg [1:0] f_init=0;
reg f_previous_fine=0;
reg [1:0] f_previous_decision=0;
always @($global_clock) begin
    f_init<={f_init[0],1'b1};
    if (!f_init[1]) assume(!RESET_N);
    assume(BBPD_CAPTURE_EN && DLF_En && !DLF_Clear);
    assume(MMDCLKDIV_RATIO==8'd16);
    if (f_init[1] && fast_reset_n && dlf_reset_n && f_previous_fine && !dlf_clk)
        assert(bbpd_decision==f_previous_decision);
    if (f_init[1] && fast_reset_n && dlf_reset_n && bbpd_decision!=f_previous_decision)
        assert(dlf_clk);
    f_previous_fine<=dlf_clk;
    f_previous_decision<=bbpd_decision;
end
'''
    if text.count('endmodule')!=1:raise ValueError('single source module required')
    if mutant:
        old='if (dlf_update_edge) begin'
        if text.count(old)!=1:raise ValueError('unique actual decision update enable required')
        text=text.replace(old,"if (1'b1) begin")
    return text.replace('endmodule',prop+'\nendmodule')


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
    for name,mutant in (('baseline',False),('update_enable_negative_control',True)):
        folder=output/name;folder.mkdir();design=folder/'IntegerPLL_DigitalCore.v';design.write_text(instrument(digital.read_text(),mutant))
        recipe=folder/'export.ys'
        files=[design if p==digital else p for p in sources]
        recipe.write_text('read_verilog -formal -sv '+' '.join(map(str,files))+'''
chparam -set SYNCHRONIZE_RESETS 1 -set BBPD_EVENT_CDC 1 -set BBPD_CAPTURE_INDEPENDENT 1 -set MMD_REGISTER_CONFIG 0 -set MMD_CONFIG_PIPELINE 0 -set MMD_RATIO_WIDTH 5 -set MMD_COUNTDOWN 1 IntegerPLL_DigitalCore
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
        if header[0]!='aig' or values[5]!=2 or values[6]!=3:raise ValueError('two assertions and three explicit protocol constraints required')
        results.append(dict(case=name,proved=safe,counterexample=unsafe,expected_safe=not mutant,latches=values[2]))
        artifacts.update({str(p):sha(p) for p in folder.iterdir() if p.is_file()})
    verify(pins);save(output/'results.json',results);artifacts[str(output/'results.json')]=sha(output/'results.json')
    if not all(x['proved']==x['expected_safe'] and x['counterexample']!=x['expected_safe'] for x in results):raise ValueError('PDR proof or negative control did not match')
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
        decision_stable_at_sampled_divided_clock_falling_edge_proved=True,
        decision_changes_only_during_sampled_divided_clock_high_phase_proved=True,
        decision_update_enable_negative_control_rejected=True,
        source_scope='actual candidate DigitalCore, constant divider16, continuous enabled capture',
        assumptions=['RESET_N asserted for first two global samples','continuously enabled capture and filter, clear inactive','fixed external divider ratio16 with configuration pipeline bypassed','ideal sampled RTL clocks; no analog metastability model'],
        native_recovery_removal_qualification_complete=False,timing_exceptions_generated=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('candidate','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.candidate.resolve(),a.output.resolve())
