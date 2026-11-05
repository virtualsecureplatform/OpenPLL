"""Deterministic legal-clock reachability witness for the proved full-core seed properties."""
import argparse
import json
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease
from compiled_charge import execute
from prove_handoff_v2 import YOSYS
from prove_prototype_tracking_configuration_v2 import instrument


def run(proof, candidate, output):
    baseline = proof/'baseline'
    source=baseline/'IntegerPLL_ProgrammedCore.v'
    candidate_receipt=candidate/'assessment.json'
    selected=json.loads(candidate_receipt.read_text());verify(selected['candidate_source_sha256'])
    actual=candidate/'rtl/IntegerPLL_ProgrammedCore.v'
    if instrument(actual.read_text(),False)!=source.read_text():
        raise ValueError('actual full-core baseline instrumentation differs')
    log=baseline/'proof.log'
    if 'Property proved' not in log.read_text():raise ValueError('proved full-core baseline required')
    output.mkdir(parents=True,exist_ok=False)
    mutant=output/'IntegerPLL_ProgrammedCore.v'
    witness="""
reg [11:0] f_witness_sample=0;
always @($global_clock) begin
    f_witness_sample<=f_witness_sample+1'b1;
    assume({RESET_N,PLL_ENABLE,REFCLK,PLLOUT,BBPD,
            STARTUP_COARSE,STARTUP_FINE,STARTUP_INCREASING,KI,KP}
           =={(f_witness_sample>=12'd4),1'b1,f_witness_sample[4],f_witness_sample[0],2'b00,
              6'd1,8'd128,1'b1,8'd1,5'd3});
end
"""
    text=instrument(actual.read_text(),True)
    if text.count('endmodule')!=1:raise ValueError('unique formal top required')
    mutant.write_text(text.replace('endmodule',witness+'\nendmodule'))
    recipe=output/'export.ys';files=sorted((candidate/'rtl').glob('*.v'))
    if len(files)!=9:raise ValueError('complete actual source bank required')
    model=output/'model.aig'
    recipe.write_text('read_verilog -formal -sv '+' '.join(str(mutant if p==actual else p) for p in files)+"""
prep -top IntegerPLL_ProgrammedCore
clk2fflogic
opt
flatten
delete -output
techmap
opt
aigmap
opt_clean
"""+f'write_aiger -zinit -symbols -map {output}/model.map {model}\n')
    image = ROOT/'build/apptainer/openpll-release-modern.sif'
    abc = str(Path(YOSYS).with_name('yosys-abc'))
    paths=[source,log,baseline/'model.aig',baseline/'export.ys',baseline/'export.log',
           candidate_receipt,*map(Path,selected['candidate_source_sha256']),mutant,recipe,
           Path(__file__).with_name('prove_prototype_tracking_configuration_v2.py'),image,Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths}
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    prefix=['apptainer','exec','--bind','/home:/home',image]
    with lease(1,4,deadline):
        execute([*prefix,YOSYS,'-s',recipe],output/'export.log',deadline,4)
        values=list(map(int,model.open('rb').readline().decode().split()[1:]))
        if values[5:7]!=[4,3]:raise ValueError('four assertions and three explicit constraints required')
        execute([*prefix,abc,'-c',f'read_aiger {model}; fold; strash; bmc3 -F 512 -T 120 -v'],output/'bmc.log',deadline,4)
    result = (output/'bmc.log').read_text()
    verify(pins)
    if 'was asserted in frame' not in result:
        raise ValueError('bounded control did not demonstrate tracked-state reachability')
    save(output/'assessment.json', dict(input_sha256=pins,
         artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file()},
         baseline_joint_assertions_proved=True, tracked_seed_state_reachable=True,
         candidate_source_sha256=selected['candidate_source_sha256'],
         only_initial_seed_assertion_inverted=True, actual_full_core_and_both_handoffs_retained=True,
         deterministic_witness_constraints_apply_only_to_negative_control=True,
         witness_REFCLK_global_sample_bit=4,witness_PLLOUT_global_sample_bit=0,
         baseline_assumptions_unchanged=True,
         initial_sampled_tracking_code_matches_seed_proved=True,
         configuration_stable_during_sampled_tracking_proved=True, full_core_behavior_proved=False,
         physical_timing_qualified=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('proof', 'candidate', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    run(a.proof.resolve(), a.candidate.resolve(), a.output.resolve())
