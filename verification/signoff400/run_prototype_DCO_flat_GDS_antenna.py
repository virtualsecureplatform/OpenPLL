"""Run stock Magic antenna rules on full flattened GDS; validation controls remain separate."""
import argparse
from fractions import Fraction as F
import json
import os
from pathlib import Path
import re
import shlex
import time

from common_v3 import ROOT, save, sha, verify
from compiled_charge import execute
from resources import lease
from extract_prototype_analog_capacitance_v2 import PDK, MAGIC

TOP = 'IntegerPLL_400MHz_PrototypeTop'
FLAT = 'OpenPLL_Prototype_Antenna_Flat'


def run(candidate, control, output):
    receipt=candidate/'assessment.json'; c=json.loads(receipt.read_text());verify(c['input_sha256']);verify(c['artifacts'])
    reviewed=control/'assessment.json'; r=json.loads(reviewed.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not (c['isolated_route_completed'] and r['wrapped_stock_cell_baseline_has_no_antenna_feedback'] and r['large_connected_metal_pad_detected_under_unchanged_PDK_rules'] and r['transistor_geometry_and_connectivity_unchanged_between_controls']):raise ValueError('isolated route and geometric controls required')
    gdslist=[Path(n) for n in c['artifacts'] if n.endswith('.gds')]
    if len(gdslist)!=1:raise ValueError('unique candidate GDS required')
    gds=gdslist[0]; top=gds.stem; receipts=[receipt,reviewed]
    output.mkdir(parents=True, exist_ok=False)
    tech = PDK/'libs.tech/magic/sky130A.tech'
    image = ROOT/'build/apptainer/openpll-release-modern.sif'
    rc = output/'minimal.magicrc'; rc.write_text('tech load {'+str(tech)+'}\n')
    script = output/'antenna.tcl'
    script.write_text(f'''drc off
crashbackups disable
locking disable
if {{[catch {{
gds read {{{gds}}}
load {top} -dereference
select top cell
flatten {FLAT}
load {FLAT}
cd {{{output}}}
extract style ngspice()
extract do capacitance
extract do coupling
extract no resistance
extract
feedback clear
antennacheck
puts "ANTENNA_FEEDBACK_COUNT=[feedback count]"
feedback save {{{output}/antenna.feedback}}
gds write {{{output}/flat.gds}}
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
    inputs = [*receipts, gds, tech, Path(MAGIC), image, rc, script, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in inputs}
    save(output/'input_manifest.json', dict(input_sha256=pins,
         scope='stock full-GDS flattened antenna experiment, independent of LEF antenna metadata',
         release_ready=False))
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'status.json', dict(state='flat_GDS_extraction_and_antenna_running', release_ready=False))
    with lease(1, 16, deadline):
        execute([MAGIC, '-dnull', '-noconsole', '-rcfile', rc, script], output/'magic.log', deadline, 16)
    log = (output/'magic.log').read_text()
    counts = re.findall(r'^ANTENNA_FEEDBACK_COUNT=(\d+)\s*$', log, re.M)
    ext = output/(FLAT+'.ext')
    if len(counts) != 1 or not ext.exists() or not (output/'flat.gds').exists():
        raise ValueError('flat antenna run incomplete')
    if re.search(r'invalid command name|couldn.t open|Cannot open|syntax error|unknown command', log, re.I):
        raise ValueError('native antenna command or input error')
    uses = 0; mos = 0; gate_area = F(0)
    for line in ext.read_text().splitlines():
        fields = shlex.split(line)
        if fields[:1] == ['use']:
            uses += 1
        if fields[:2] == ['device', 'msubckt'] and any(t in fields[2] for t in ('nfet', 'pfet')):
            values = dict(t.split('=', 1) for t in fields if '=' in t)
            gate_area += F(values['l'])*F(values['w'])*F(1, 200)**2
            mos += 1
    if uses or mos < 100:
        raise ValueError('full parent transistor geometry not flattened/extracted')
    verify(pins)
    save(output/'assessment.json', dict(input_sha256=pins,
         artifacts={str(p): sha(p) for p in output.iterdir() if p.is_file() and p.name!='status.json'},
         native_flat_layout_antenna_run_completed=True, source_macros_all_expanded=True,
         residual_hierarchy_uses=uses, extracted_flat_MOS_primitives=mos,
         raw_gate_area_um2_at_1_over_200_grid=str(gate_area),
         native_antenna_feedback_entries=int(counts[0]),
         independent_GDS_gate_area_and_conductor_geometry_checked=False,
         antenna_engine_negative_controls_complete=True,
         final_candidate_integrated=False, parent_antenna_qualified=False, release_ready=False))
    save(output/'status.json', dict(state='native_flat_antenna_experiment_complete', release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'control', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.candidate.resolve(), args.control.resolve(), args.output.resolve())
