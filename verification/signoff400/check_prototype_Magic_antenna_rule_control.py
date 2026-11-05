"""Control Magic antenna sensitivity with identical cell geometry and a mutated poly ratio."""
import argparse
import json
import os
from pathlib import Path
import re
import time

from common_v3 import ROOT, save, sha, verify
from compiled_charge import execute
from resources import lease
from extract_prototype_analog_capacitance_v2 import PDK, MAGIC


def run(output):
    tech = PDK/'libs.tech/magic/sky130A.tech'
    gds = PDK/'libs.ref/sky130_fd_sc_hs/gds/sky130_fd_sc_hs.gds'
    source = tech.read_text()
    changed, count = re.subn(r'(?m)^(\s*antenna\s+poly\s+sidewall\s+)50(\s+none\s*)$',
                            r'\g<1>1\2', source)
    if count != 1:
        raise ValueError('unique pinned poly antenna ratio required')
    output.mkdir(parents=True, exist_ok=False)
    mutant = output/'low_poly_ratio.tech'; mutant.write_text(changed)
    inputs = [tech, gds, Path(MAGIC), mutant, Path(__file__).resolve(),
              ROOT/'build/apptainer/openpll-release-modern.sif']
    pins = {str(p): sha(p) for p in inputs}
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    results = []; devices = []
    for name, technology in [('baseline', tech), ('low_poly_ratio', mutant)]:
        folder = output/name; folder.mkdir()
        rc = folder/'minimal.magicrc'; rc.write_text('tech load {'+str(technology)+'}\n')
        script = folder/'control.tcl'
        script.write_text(f'''drc off
crashbackups disable
locking disable
if {{[catch {{
gds read {{{gds}}}
load sky130_fd_sc_hs__dfrtp_1 -dereference
select top cell
flatten AntennaRuleControl
load AntennaRuleControl
cd {{{folder}}}
extract style ngspice()
extract do capacitance
extract do coupling
extract no resistance
extract
feedback clear
antennacheck
puts "ANTENNA_CONTROL_FEEDBACK=[feedback count]"
feedback save {{{folder}/antenna.feedback}}
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
        with lease(1, 4, deadline):
            execute([MAGIC, '-dnull', '-noconsole', '-rcfile', rc, script], folder/'magic.log', deadline, 4)
        log = (folder/'magic.log').read_text()
        matches = re.findall(r'^ANTENNA_CONTROL_FEEDBACK=(\d+)\s*$', log, re.M)
        ext = folder/'AntennaRuleControl.ext'
        if len(matches) != 1 or not ext.exists():
            raise ValueError('native rule control incomplete')
        rows = sorted(line for line in ext.read_text().splitlines() if line.startswith('device '))
        if not rows:
            raise ValueError('control transistor extraction absent')
        devices.append(rows)
        results.append(dict(case=name, feedback_entries=int(matches[0]), extracted_devices=len(rows)))
    detail = output/'results.json'; save(detail, results)
    verify(pins)
    if devices[0] != devices[1] or results[0]['feedback_entries'] != 0 or results[1]['feedback_entries'] <= 0:
        raise ValueError('baseline or antenna sensitivity control did not match')
    save(output/'assessment.json', dict(input_sha256=pins,
         artifacts={str(p): sha(p) for p in output.rglob('*') if p.is_file()},
         stock_isolated_cell_has_no_antenna_feedback=True,
         lowered_poly_ratio_produces_antenna_feedback=True,
         transistor_geometry_and_connectivity_unchanged_between_controls=True,
         mutation_scope='only poly sidewall ratio 50 to 1 in a private technology copy',
         parent_or_final_candidate_antenna_qualified=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve())
