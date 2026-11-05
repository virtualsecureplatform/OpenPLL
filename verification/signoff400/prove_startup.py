#!/usr/bin/env python3
"""Unbounded sampled startup-control invariants with rejecting RTL mutants.

This is partial digital evidence, not analog/CDC/timing or macro qualification.
All inputs after the initial reset are arbitrary; no stable-program or prompt
acknowledgement assumption is made. Reset is modeled by Yosys async2sync.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

from common import ROOT, PROFILE, save, sha, source_pins, verify

YOSYS = '/nix/store/4bmfi4470w0i3ixcaidfki18d3fyqvva-yosys-with-plugins-0.62/bin/yosys'
MUTANTS = {
    'single_seed_observation': ('if(settle_count==2)', "if(1'b1)"),
    'accept_fine_below_eight': ('STARTUP_FINE<8', 'STARTUP_FINE<0'),
    'ignore_program_change': ('state!=CAPTURE && changed', "state!=CAPTURE && 1'b0"),
}


def instrument(source, properties, mutant=None):
    if source.count('endmodule') != 1:
        raise ValueError('expected one startup module')
    if mutant:
        before, after = MUTANTS[mutant]
        if source.count(before) != 1:
            raise ValueError('mutant target must occur exactly once')
        source = source.replace(before, after)
    return source.replace('endmodule', properties + '\nendmodule')


def run(output, container=None):
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    deadline = started + 43200
    rtl = ROOT / 'rtl/IntegerPLL_ProgrammedStartup.v'
    properties = Path(__file__).with_name('startup_properties.vh').resolve()
    pins = source_pins()
    for p in (rtl, properties, Path(__file__).resolve(), Path(__file__).with_name('common.py')):
        pins[str(p)] = sha(p)
    prefix = []
    if container:
        container = Path(container).resolve()
        pins[str(container)] = sha(container)
        prefix = ['apptainer', 'exec', '--bind', '/home:/home,/tmp:/tmp', str(container)]
    else:
        pins[YOSYS] = sha(YOSYS)
    save(out / 'owner.json', dict(started_utc=datetime.now(timezone.utc).isoformat(),
         wall_limit_s=43200, automatic_identical_retry=False))
    source = rtl.read_text()
    assertions = properties.read_text()
    records = []
    try:
        for label in ('baseline', *MUTANTS):
            design = out / (label + '.v')
            design.write_text(instrument(source, assertions, None if label == 'baseline' else label))
            recipe = out / (label + '.ys')
            recipe.write_text(f'''read_verilog -formal -sv {design}
prep -top IntegerPLL_ProgrammedStartup
async2sync
opt
sat -seq 2 -tempinduct -maxsteps 30 -set-at 1 RESET_N 0 -set-def-inputs -prove-asserts -verify -show-ports
''')
            command = prefix + [YOSYS, '-s', str(recipe)]
            with (out / (label + '.log')).open('x') as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=max(.001, deadline-time.monotonic()))
            text = (out / (label + '.log')).read_text()
            success = result.returncode == 0 and 'Induction step proven: SUCCESS!' in text
            counterexample = result.returncode != 0 and ('proof did fail' in text or 'model found: FAIL' in text)
            records.append(dict(label=label, command=command, returncode=result.returncode,
                                unbounded_induction_pass=success, rejecting_counterexample=counterexample))
            if label == 'baseline' and not success:
                raise RuntimeError('startup baseline lacks unbounded induction success')
            if label != 'baseline' and not counterexample:
                raise RuntimeError('startup mutant lacks a rejecting counterexample: ' + label)
        verify(pins)
        report = dict(profile_sha256=sha(PROFILE), candidate_source_sha256=source_pins(),
             input_sha256=pins, artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
             records=records, sampled_startup_control_invariants_proven=True,
             all_three_negative_controls_rejected=True,
             assumptions=['one sampled REFCLK edge per proof step',
                          'RESET_N low at first step; all later inputs arbitrary',
                          'async2sync reset abstraction; no recovery/removal or analog claim'],
             physical_timing_qualified=False, interface_model_qualified=False,
             digital_startup_qualified=False, release_qualified=False,
             elapsed_s=time.monotonic()-started)
        save(out / 'assessment.json', report)
        save(out / 'status.json', dict(state='sampled_invariants_proven_pending_integration',
                                      elapsed_s=time.monotonic()-started, release_qualified=False))
        return report
    except BaseException as error:
        save(out / 'status.json', dict(state='failed', reason=repr(error), records=records,
                                      elapsed_s=time.monotonic()-started, release_qualified=False))
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--container', type=Path)
    a = p.parse_args()
    report = run(a.output, a.container)
    print(json.dumps({k: report[k] for k in ('sampled_startup_control_invariants_proven',
                                           'all_three_negative_controls_rejected', 'elapsed_s')}))


if __name__ == '__main__':
    main()
