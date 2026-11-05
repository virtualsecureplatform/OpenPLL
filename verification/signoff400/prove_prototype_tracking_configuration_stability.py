"""Prove tracked configuration stability with a conservative free-clock/core-output cut.

The complete startup and both handoffs are retained. Divider clock and loaded
code are independent arbitrary inputs, so this proof cannot establish initial
seed loading, clock phase, analog timing, or full-core behavior.
"""
import argparse,json,os,time,re
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute
from prove_handoff_v2 import YOSYS


def instrument(text,mutant=False):
    comparison='!=' if mutant else '=='
    core=re.compile(r'    IntegerPLL_DigitalCore #\(.*?\.Fine_CAPS_CTRL\(\)\);',re.S)
    if len(core.findall(text))!=1:raise ValueError('unique actual core instance required for conservative cut')
    text=core.sub('''    (* anyseq *) reg f_free_feedback_clock;
    (* anyseq *) reg [7:0] f_free_loaded_code;
    assign CLKDIV_RETIMED=f_free_feedback_clock;
    assign core_dco_code=f_free_loaded_code;
    // Other core outputs have no fan-in to the retained safety assertion.
    assign core_dco_therm=255\'b0;
    assign core_coarse_therm=47\'b0;
    assign DLF_CODE=10\'b0;''',text)
    prop='''
reg [1:0] f_init=0;
reg f_previous_reset=0;
reg f_previous_tracking=0;
reg [27:0] f_previous_inputs=0;
reg [21:0] f_previous_configuration=0;
always @($global_clock) begin
    f_init<={f_init[0],1'b1};
    if (!f_init[1]) assume(!RESET_N);
    if (f_init[1] && RESET_N && f_previous_reset)
        assume({STARTUP_COARSE,STARTUP_FINE,STARTUP_INCREASING,KI,KP}==f_previous_inputs);
    if (f_init[1] && RESET_N && oscillator_reset_n && fine_reset_n) begin
        if (TRACKING && f_previous_tracking)
            assert({fine_seed,fine_increasing,fine_ki,fine_kp} COMPARISON f_previous_configuration);
    end
    f_previous_reset<=RESET_N;
    f_previous_tracking<=TRACKING;
    f_previous_inputs<={STARTUP_COARSE,STARTUP_FINE,STARTUP_INCREASING,KI,KP};
    f_previous_configuration<={fine_seed,fine_increasing,fine_ki,fine_kp};
end
'''.replace('COMPARISON',comparison)
    if text.count('endmodule')!=1:raise ValueError('single source module required')
    return text.replace('endmodule',prop+'\nendmodule')


def run(candidate,output):
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    receipt=candidate/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    sources=sorted((candidate/'rtl').glob('*.v'))
    digital=candidate/'rtl/IntegerPLL_ProgrammedCore.v'
    if len(sources)!=9 or digital not in sources:raise ValueError('complete isolated candidate RTL required')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';abc=str(Path(YOSYS).with_name('yosys-abc'))
    paths=[receipt,*sources,image,Path(__file__).resolve(),Path(__file__).with_name('prove_handoff_v2.py')]
    pins={str(p):sha(p) for p in paths}
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    prefix=['apptainer','exec','--bind','/home:/home',image];results=[];artifacts={}
    for name,mutant in (('baseline',False),('tracking_reachability_control',True)):
        folder=output/name;folder.mkdir();design=folder/'IntegerPLL_ProgrammedCore.v';design.write_text(instrument(digital.read_text(),mutant))
        recipe=folder/'export.ys'
        files=[design if p==digital else p for p in sources]
        recipe.write_text('read_verilog -formal -sv '+' '.join(map(str,files))+'''
prep -top IntegerPLL_ProgrammedCore
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
        if header[0]!='aig' or values[5]!=1 or values[6]!=2:raise ValueError('one stability assertion and two explicit reset/static-input constraints required')
        results.append(dict(case=name,proved=safe,counterexample=unsafe,expected_safe=not mutant,latches=values[2]))
        artifacts.update({str(p):sha(p) for p in folder.iterdir() if p.is_file()})
    verify(pins);save(output/'results.json',results);artifacts[str(output/'results.json')]=sha(output/'results.json')
    if not all(x['proved']==x['expected_safe'] and x['counterexample']!=x['expected_safe'] for x in results):raise ValueError('PDR proof or negative control did not match')
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
        configuration_stable_during_sampled_tracking_proved=True,
        initial_sampled_tracking_code_matches_seed_proved=False,tracked_configuration_state_reachable=True,
        conservative_free_core_outputs_and_feedback_clock_cut=True,
        source_scope='actual ProgrammedCore startup and both 34-bit handoffs; DigitalCore replaced by independent arbitrary feedback clock and loaded-code inputs',
        assumptions=['RESET_N asserted for first two global samples','presets and gains stable between external resets','ideal sampled RTL clocks; no analog metastability model'],
        native_recovery_removal_qualification_complete=False,timing_exceptions_generated=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('candidate','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.candidate.resolve(),a.output.resolve())
