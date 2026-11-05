"""Prove enabled decision phase in the actual parent with arbitrary enable/disable."""
import argparse
import json
import os
from pathlib import Path
import time

from common_v3 import ROOT, save, sha, verify
from resources import lease
from compiled_charge import execute
from prove_handoff_v2 import YOSYS


def core_instrument(text):
    prop = '''
reg [1:0] f_phase_init=0;
reg f_phase_previous_fine=0;
reg f_phase_previous_enable=0;
reg [1:0] f_phase_previous_decision=0;
always @($global_clock) begin
    f_phase_init<={f_phase_init[0],1'b1};
    if(f_phase_init[1] && fast_reset_n && dlf_reset_n && DLF_En && !DLF_Clear) begin
        if(f_phase_previous_fine && !dlf_clk)
            assert(bbpd_decision==f_phase_previous_decision);
        if(bbpd_decision!=f_phase_previous_decision)
            assert(dlf_clk);
        if(!f_phase_previous_enable)
            assert(dlf_clk);
    end
    if(f_phase_init[1] && fast_reset_n && dlf_reset_n) begin
        if(DLF_En && !DLF_Clear && !f_phase_previous_enable)
            assert(loop_decision==2'b00);
        if(DLF_Clear)
            assert(DLF_CODE==DLF_Ext_Data);
    end
    f_phase_previous_fine<=dlf_clk;
    f_phase_previous_enable<=DLF_En && !DLF_Clear;
    f_phase_previous_decision<=bbpd_decision;
end
'''
    if text.count('endmodule') != 1:
        raise ValueError('unique actual DigitalCore module required')
    return text.replace('endmodule', prop+'\nendmodule')


def parent_instrument(text):
    prop = '''
reg [1:0] f_phase_init=0;
reg f_phase_previous_reset=0;
reg [27:0] f_phase_previous_inputs=0;
always @($global_clock) begin
    f_phase_init<={f_phase_init[0],1'b1};
    if(!f_phase_init[1]) assume(!RESET_N);
    if(f_phase_init[1] && RESET_N && f_phase_previous_reset)
        assume({STARTUP_COARSE,STARTUP_FINE,STARTUP_INCREASING,KI,KP}==f_phase_previous_inputs);
    f_phase_previous_reset<=RESET_N;
    f_phase_previous_inputs<={STARTUP_COARSE,STARTUP_FINE,STARTUP_INCREASING,KI,KP};
end
'''
    if text.count('endmodule') != 1:
        raise ValueError('unique actual ProgrammedCore module required')
    return text.replace('endmodule', prop+'\nendmodule')


def run(candidate, local_control, reachability, output):
    receipts = [p/'assessment.json' for p in (candidate, local_control, reachability)]
    records = [json.loads(p.read_text()) for p in receipts]
    for record in records:
        verify(record['artifacts'])
    if not records[1]['decision_update_enable_negative_control_rejected'] or not records[2]['tracked_seed_state_reachable']:
        raise ValueError('existing update-enable mutation and actual integrated tracking witness required')
    sources = sorted((candidate/'rtl').glob('*.v'))
    if len(sources) != 9:
        raise ValueError('complete actual candidate RTL required')
    for p in sources:
        if (records[1]['input_sha256'].get(str(p)) != sha(p)
                or records[2]['candidate_source_sha256'].get(str(p)) != sha(p)):
            raise ValueError('control/witness candidate source differs')
    image = ROOT/'build/apptainer/openpll-release-modern.sif'
    inputs = [*receipts, *sources, image, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in inputs}
    output.mkdir(parents=True, exist_ok=False)
    replacements = {}
    for name, instrument in [('IntegerPLL_DigitalCore.v', core_instrument),
                             ('IntegerPLL_ProgrammedCore.v', parent_instrument)]:
        target = output/name; target.write_text(instrument((candidate/'rtl'/name).read_text()))
        replacements[name] = target
    script = output/'export.ys'
    script.write_text('read_verilog -formal -sv '+' '.join(str(replacements.get(p.name, p)) for p in sources)+'''
prep -top IntegerPLL_ProgrammedCore
clk2fflogic
opt
flatten
delete -output
techmap
opt
aigmap
opt_clean
'''+f'write_aiger -zinit -symbols -map {output}/model.map {output}/model.aig\n')
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', GOMAXPROCS='1')
    prefix = ['apptainer', 'exec', '--bind', '/home:/home', image]
    save(output/'status.json', dict(state='integrated_mask_rearm_and_phase_proof_running', release_ready=False))
    with lease(1, 4, deadline):
        execute([*prefix, YOSYS, '-s', script], output/'export.log', deadline, 4)
        header = (output/'model.aig').open('rb').readline().decode().split()
        values = list(map(int, header[1:])); values += [0]*(9-len(values))
        if header[0] != 'aig' or values[5] != 5 or values[6] != 2:
            raise ValueError('three phase and two mask/rearm assertions and two reset/static-input constraints required')
        abc = str(Path(YOSYS).with_name('yosys-abc'))
        execute([*prefix, abc, '-c', f'read_aiger {output}/model.aig; fold; strash; pdr -v -d -I {output}/invariant.pla -T 3600'], output/'proof.log', deadline, 4)
    verify(pins)
    if 'Property proved' not in (output/'proof.log').read_text():
        save(output/'status.json', dict(state='not_proved', release_ready=False))
        raise ValueError('integrated phase property not proved')
    # Mutate only the actual filter's disabled output override. Require a
    # counterexample on the new mask property, not merely another failed proof.
    original=candidate/'rtl/IntegerPLL_DLF.v'
    token='assign DLF_CODE = (DLF_Ext_Override || DLF_Clear) ? DLF_Ext_Data : loop_code;'
    if original.read_text().count(token)!=1:raise ValueError('unique actual mask gate required')
    mutated=output/'mask_removed.v';mutated.write_text(original.read_text().replace(token,'assign DLF_CODE = loop_code;'))
    bad=output/'mask_removed';bad.mkdir()
    bad_script=bad/'export.ys'
    text=script.read_text().replace(str(original),str(mutated)).replace(str(output)+'/model.',str(bad)+'/model.')
    bad_script.write_text(text)
    with lease(1,4,deadline):
        execute([*prefix,YOSYS,'-s',bad_script],bad/'export.log',deadline,4)
        execute([*prefix,abc,'-c',f'read_aiger {bad}/model.aig; fold; strash; pdr -v -d -T 3600; write_cex -a {bad}/counterexample.cex'],bad/'proof.log',deadline,4)
    bad_log=(bad/'proof.log').read_text()
    if 'Output 4' not in bad_log or 'asserted' not in bad_log or not (bad/'counterexample.cex').exists():raise ValueError('disabled output mask mutation not rejected by the intended assertion')
    save(output/'assessment.json', dict(input_sha256=pins,
         artifacts={str(p): sha(p) for p in output.rglob('*') if p.is_file() and p.name!='status.json'},
         enabled_decision_stable_at_sampled_falling_edge_in_actual_parent_proved=True,
         enabled_decision_changes_only_in_divided_clock_high_phase_proved=True,
         loop_enable_asserts_only_in_divided_clock_high_phase_proved=True,
         continuous_capture_or_filter_enable_assumed=False,
         both_actual_handoffs_and_loop_filter_retained=True,
         local_update_enable_mutation_control_reused=True,
         actual_integrated_tracking_reachability_witness_reused=True,
         assumptions=['external reset asserted for first two global samples',
                      'presets and gains stable between external resets', 'ideal sampled RTL clocks'],
         disabled_output_seed_override_proved=True,decision_is_zero_at_each_sampled_loop_enable_assertion_proved=True,actual_filter_output_mask_removed_mutation_rejected=True,analog_resolution_qualified=False,disabled_state_masking_or_analog_resolution_qualified=False,
         timing_exceptions_generated=False, digital_timing_qualified=False, release_ready=False))
    save(output/'status.json', dict(state='sampled_integrated_mask_rearm_and_phase_proved', release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'local-control', 'reachability', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.candidate.resolve(), args.local_control.resolve(), args.reachability.resolve(), args.output.resolve())
