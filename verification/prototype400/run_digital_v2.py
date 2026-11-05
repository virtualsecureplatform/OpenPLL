#!/usr/bin/env python3
"""Compile and exercise real prototype RTL; optionally map it to HS cells."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from common import ROOT, PROFILE, RTL, TOP, cases, save, sha, source_pins, spec, verify

YOSYS = '/nix/store/4bmfi4470w0i3ixcaidfki18d3fyqvva-yosys-with-plugins-0.62/bin/yosys'
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import ALLOWED

LIB = ROOT/'build/timing450/pdk/sky130A/libs.ref/sky130_fd_sc_hs/lib/sky130_fd_sc_hs__tt_025C_1v80.lib'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--synthesize', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    spec()
    bench = ROOT/'tb/tb_programmed400.v'
    pins = source_pins()
    for path in (Path(__file__).resolve(), Path(__file__).with_name('common.py'), bench,
                 Path('/usr/bin/iverilog'), Path('/usr/bin/vvp')):
        pins[str(path)] = sha(path)
    save(out/'owner.json', dict(started_utc=datetime.now(timezone.utc).isoformat(),
         wall_limit_s=43200, automatic_identical_retry=False))

    def run(command, name):
        verify(pins)
        with (out/name).open('x') as log:
            code = subprocess.run(list(map(str, command)), cwd=out, stdout=log,
                                  stderr=subprocess.STDOUT,
                                  timeout=max(.001, 43200-(time.monotonic()-started))).returncode
        if code:
            raise RuntimeError(name + ': ' + (out/name).read_text()[-2000:])

    binary = out/'controls.vvp'
    run(['/usr/bin/iverilog','-g2012','-Wall','-s','tb_programmed400','-o',binary,*RTL,bench],
        'compile.log')
    run(['/usr/bin/vvp',binary], 'controls.log')
    match = re.search(r'PASS: programmed400 digital startup controls checks=(\d+)',
                      (out/'controls.log').read_text())
    assert match
    # Check the physical top's real ports with analog blackboxes, not gate models.
    blackboxes = out/'analog_blackboxes.v'
    blackboxes.write_text('''(* blackbox *) module IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160
      (inout VPWR,VGND,VPB,VNB,input RESET_N,input [46:0] COARSETHERMAL_CODE,
       input [254:0] DCO_THERM,output PLLOUT); endmodule
      (* blackbox *) module IntegerPLL_BBPD(inout VPWR,VGND,VPB,VNB,
       input REF,CLKDIVR,RESET_N,output [1:0] BBPD); endmodule
''')
    run(['/usr/bin/iverilog','-g2012','-DUSE_POWER_PINS','-s','IntegerPLL_400MHz_PrototypeTop',
         '-o',out/'top.vvp',*RTL,TOP,blackboxes], 'top_compile.log')
    mapped = None
    if args.synthesize:
        pins[str(Path(YOSYS))] = sha(YOSYS)
        pins[str(LIB)] = sha(LIB)
        excluded = set(re.findall(r'cell\s*\(\s*"?([^\s"\)]+)',LIB.read_text())) - ALLOWED
        pins[str(ROOT/'verification/timing400/check_compact_mapping.py')] = sha(ROOT/'verification/timing400/check_compact_mapping.py')
        task = out/'synth.ys'
        task.write_text(f'''read_verilog {' '.join(map(str, RTL))}
hierarchy -check -top IntegerPLL_ProgrammedCore
synth -top IntegerPLL_ProgrammedCore -flatten
dfflibmap -liberty {LIB}
abc -liberty {LIB} -D 2222 {' '.join('-dont_use '+cell for cell in sorted(excluded))}
clean
delete t:$scopeinfo
read_liberty -lib -ignore_miss_func -ignore_miss_dir {LIB}
check -assert
stat -liberty {LIB}
write_verilog -norename {out}/mapped.v
write_json {out}/mapped.json
''')
        run([YOSYS,'-s',task], 'synth.log')
        module = json.loads((out/'mapped.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
        counts = Counter(cell['type'] for cell in module['cells'].values())
        assert set(counts) <= ALLOWED
        mapped = dict(cells=sum(counts.values()), cell_types=len(counts), counts=dict(counts))
    verify(pins)
    save(out/'functional_cases.json', dict(cases=cases(), qualification_cases_passed=0,
         gate='matching_physical_DCO_and_interface_models_required'))
    save(out/'assessment.json', dict(input_sha256=pins,
         artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
         digital_controls_passed=True, digital_control_checks=int(match[1]),
         physical_top_compile_passed=True, synthesis=mapped,
         whole_pll_qualification_pass=False, physical_timing_qualified=False,
         prototype_handoff_qualified=False, release_qualified=False))
    print(json.dumps(dict(digital_control_checks=int(match[1]), synthesis=mapped)))


if __name__ == '__main__':
    main()
