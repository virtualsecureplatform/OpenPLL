"""Parallel compiled full-deck capacitance token inventory with source pins."""
import argparse
import json
from pathlib import Path
import subprocess
import time
from common import save,sha
from compiled_charge import execute
from resources import lease


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    source=Path('tools/sheet_charge/scan_SPICE_cap_tokens.cpp').resolve()
    include=Path('tools/charge_compiler/json.hpp').resolve()
    deck=Path('/tmp/openpll-interface-domain-_9_bmlz2/domain/trace/retained_rc.spice')
    proof=Path('build/signoff400/startup_timing_SPICE_cap_serialization_001/assessment.json').resolve()
    paths=[source,include,deck,proof,Path(__file__).resolve()];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(8,8,deadline):
        pins={str(p):sha(p) for p in paths};binary=output/'scan_SPICE_cap_tokens'
        command=['g++','-std=c++20','-O3','-pthread','-fno-fast-math',str(source),'-o',str(binary)]
        with (output/'build.log').open('x') as log:
            subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        fixture=output/'control.spice';fixture.write_text('* C comment\n.subckt x a b\nC0 a b 0\nC1 a b 0.001f\nC2 a b 1p $ comment\nR1 a b 1\nC3 a b 2f **FLOATING\nC4 a b 3e-15\nC5 a b -1f\n.ends')
        for threads in (1,4,8):
            report=output/f'control_{threads}.json'
            execute([binary,fixture,threads,report],output/f'control_{threads}.log',deadline,8)
            r=json.loads(report.read_text())
            if (r['capacitor_records'],r['printed_zero_capacitor_records'],r['positive_capacitor_records'])!=(6,1,4):raise ValueError('compiled scanner coverage control')
            if r['negative_capacitor_records']!=1:raise ValueError('signed capacitor control')
            if r['minimum_positive_capacitance_F']!=1e-18 or abs(r['serialized_capacitance_sum_F_diagnostic']-1.004001e-12)>1e-27:raise ValueError('SI scanner controls')
        for name,text in [('suffix','C0 a b 1z\n'),('nonfinite','C0 a b nan\n'),('missing','C0 a b\n')]:
            f=output/f'bad_{name}.spice';f.write_text(text)
            r=subprocess.run([str(binary),str(f),'4',str(output/f'bad_{name}.json')],capture_output=True,text=True)
            save(output/f'bad_{name}.result.json',dict(returncode=r.returncode,stderr=r.stderr))
            if r.returncode==0:raise ValueError('malformed capacitor accepted')
        report=output/'native_deck_report.json';execute([binary,deck,8,report],output/'native_scan.log',deadline,8)
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('scan input changed')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (binary,report)},
             compiled_parallel_full_SPICE_capacitance_token_scan_complete=True,threads=8,
             controls_1_4_8_threads_and_malformed_rejection_pass=True,results=json.loads(report.read_text()),
             serialization_loss_spatial_assignment_complete=False,full_SPICE_matrix_equivalence_verified=False,
             physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
