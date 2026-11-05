#!/usr/bin/env python3
"""Independent checks of this candidate's powered GDS, with pinned tools."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from run import DEFAULT_PDK, REPO, run

MAGIC = '/nix/store/i68lxdmnc7422hvlabbmrhss4sqqkjzq-magic-vlsi-8.3.623/bin/magic'
NETGEN = '/nix/store/kw3frc6fbv3zi2m9n0wv93y1nfiyjiy6-netgen-1.5.316/bin/netgen'
KLAYOUT_PYTHON = '/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3'
STREAM = '/nix/store/15gw4cny6dmil9965l9csn881g1j6lvi-python3.13-librelane-3.0.4/lib/python3.13/site-packages/librelane/scripts/klayout/stream_out.py'


def lvs_unique_match(log):
    return ('Circuits match uniquely.' in log and
            'Property errors were found' not in log and
            'Top level cell failed pin matching' not in log)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', choices=['hd', 'hs'], default='hd')
    parser.add_argument('--pdk-root', default=DEFAULT_PDK)
    args = parser.parse_args()
    root = REPO / 'build/timing450' / args.library
    pdk = Path(args.pdk_root) / 'sky130A'
    scl = 'sky130_fd_sc_' + args.library
    library = pdk / 'libs.ref' / scl
    tech = library / 'techlef' / (scl + '__nom.tlef')
    signoff = root / 'signoff'
    signoff.mkdir(exist_ok=True)
    (signoff / 'assessment.json').unlink(missing_ok=True)
    def execute(command, log, **kwargs):
        with (signoff / log).open('w') as output:
            subprocess.run(list(map(str, command)), stdout=output, stderr=subprocess.STDOUT, check=True, **kwargs)
    spice_library = library / 'spice' / (scl + '.spice')
    view_inputs = []
    if args.library == 'hs':
        # Measure the library GDS independently of routed extraction. This
        # correction is local to this candidate; installed views are immutable.
        probe = signoff / 'diode_geometry.py'
        probe.write_text("""import json, pya, sys
l=pya.Layout(); l.read(sys.argv[1])
c=l.cell('sky130_fd_sc_hs__diode_2')
if c is None: raise RuntimeError('Missing source diode GDS cell')
r=pya.Region(c.begin_shapes_rec(l.layer(65,20))).merged()
m=pya.Region(c.begin_shapes_rec(l.layer(81,23))).merged()
if not (r ^ m).is_empty() or r.count()!=1:
    raise RuntimeError('Diode marker does not identify one diffusion junction')
p=next(r.each())
if p.holes()!=0 or p.num_points()!=4:
    raise RuntimeError('Unexpected diode junction shape')
print(json.dumps({'area_um2':r.area()*l.dbu**2,'perimeter_um':r.perimeter()*l.dbu}))
""")
        execute([KLAYOUT_PYTHON, probe, library / 'gds' / (scl + '.gds')], 'diode_geometry.json')
        from hs_views import normalize_diode_spice
        original_spice = spice_library
        spice_library = signoff / (scl + '.canonical.spice')
        spice_library.write_text(normalize_diode_spice(original_spice.read_text(),
                                 json.loads((signoff / 'diode_geometry.json').read_text())))
        view_inputs = [spice_library, probe, signoff / 'diode_geometry.json',
                       Path(__file__).with_name('hs_views.py')]
    recipe = signoff / 'audit.tcl'
    recipe.write_text(f'''read_lef {tech}
read_lef {library}/lef/{scl}.lef
read_liberty {library}/lib/{scl}__tt_025C_1v80.lib
read_db {root}/route.odb
check_placement -verbose
check_antennas -report_file {signoff}/antenna.rpt
set total 0
set connected 0
foreach inst [[ord::get_db_block] getInsts] {{
    foreach term [$inst getITerms] {{
        if {{[$term getSigType] in {{POWER GROUND}}}} {{
            incr total
            if {{[$term getNet] ne {{NULL}}}} {{incr connected}}
        }}
    }}
}}
puts "POWER_PIN_AUDIT total=$total connected=$connected"
if {{$total != $connected}} {{error "unconnected supply pins"}}
check_power_grid -net VDD -error_file {signoff}/vdd_errors.rpt
check_power_grid -net VSS -error_file {signoff}/vss_errors.rpt
write_verilog -include_pwr_gnd {signoff}/powered.v
exit
''')
    run('openroad', ['-exit', recipe], signoff / 'audit.log')
    command = [KLAYOUT_PYTHON, STREAM, '-o', signoff / 'route.gds', '-t', 'IntegerPLL_AcquiringCore',
               '-T', pdk / 'libs.tech/klayout/tech/sky130A.lyt', '-P', pdk / 'libs.tech/klayout/tech/sky130A.lyp',
               '-M', pdk / 'libs.tech/klayout/tech/sky130A.map', '-l', tech,
               '-l', library / 'lef' / (scl + '.lef')]
    extra = library / 'lef' / ('sky130_ef_sc_' + args.library + '.lef')
    if extra.exists():
        command += ['-l', extra]
    command += ['-w', library / 'gds' / (scl + '.gds'), root / 'route.def']
    execute(command, 'stream.log', cwd=REPO)
    env = dict(os.environ, PDK_ROOT=str(pdk.parent))
    startup = pdk / 'libs.tech/magic/sky130A.magicrc'
    drc = signoff / 'drc.tcl'
    drc.write_text(f'''crashbackups stop
drc euclidean on
drc style drc(full)
drc on
snap internal
gds flatten true
gds read {signoff}/route.gds
load IntegerPLL_AcquiringCore
select top cell
expand
drc catchup
set errors [drc listall why]
set out [open {signoff}/drc_errors.rpt w]
set count 0
foreach {{why rectangles}} $errors {{
    puts $out $why
    foreach rect $rectangles {{incr count; puts $out $rect}}
}}
puts $out "MAGIC_DRC_RECTANGLES=$count"
close $out
puts "MAGIC_DRC_RECTANGLES=$count"
quit -noprompt
''')
    with drc.open() as source:
        execute([MAGIC, '-dnull', '-noconsole', '-rcfile', startup], 'drc.log', stdin=source, env=env, cwd=signoff)
    extraction = signoff / 'extraction'
    extraction.mkdir(exist_ok=True)
    extract = signoff / 'extract.tcl'
    extract.write_text(f'''drc off
crashbackups disable
locking disable
gds read {signoff}/route.gds
readspice {spice_library}
load IntegerPLL_AcquiringCore -dereference
cd {extraction}
extract do local
extract no capacitance
extract no coupling
extract no resistance
extract no adjust
extract
ext2spice lvs
ext2spice short resistor
ext2spice -o ../IntegerPLL_AcquiringCore.spice IntegerPLL_AcquiringCore.ext
feedback save ../feedback.txt
quit -noprompt
''')
    with extract.open() as source:
        execute([MAGIC, '-dnull', '-noconsole', '-rcfile', startup], 'extract.log', stdin=source, env=env, cwd=signoff)
    compare = signoff / 'compare.tcl'
    compare.write_text(f'''readnet spice {signoff}/IntegerPLL_AcquiringCore.spice 1
readnet spice {spice_library} 2
readnet verilog {signoff}/powered.v 2
lvs {{IntegerPLL_AcquiringCore 1}} {{IntegerPLL_AcquiringCore 2}} {pdk}/libs.tech/netgen/sky130A_setup.tcl {signoff}/compare.log -json
quit
''')
    execute([NETGEN, '-batch', 'source', compare], 'compare.runner.log', cwd=REPO, env=env)
    drc_text = (signoff / 'drc_errors.rpt').read_text()
    match = re.search(r'MAGIC_DRC_RECTANGLES=(\d+)', drc_text)
    audit = (signoff / 'audit.log').read_text()
    pg = re.search(r'POWER_PIN_AUDIT total=(\d+) connected=(\d+)', audit)
    nets = re.search(r'Found (\d+) net violations', audit)
    pins = re.search(r'Found (\d+) pin violations', audit)
    result = {'release_qualified': False, 'selected': False,
              'power_pins_total': int(pg[1]) if pg else None,
              'power_pins_connected': int(pg[2]) if pg else None,
              'antenna_net_violations': int(nets[1]) if nets else None,
              'antenna_pin_violations': int(pins[1]) if pins else None, 'magic_drc_rectangles': int(match[1]) if match else None,
              'lvs_unique_match': lvs_unique_match((signoff / 'compare.log').read_text()),
              'limitations': ['Antenna closure, full KLayout DRC and density/EM/IR qualification remain separate gates'],
              'sha256': {str(f): hashlib.sha256(f.read_bytes()).hexdigest()
                         for f in [*view_inputs, root / 'route.odb', signoff / 'route.gds', signoff / 'powered.v', signoff / 'compare.log', signoff / 'drc_errors.rpt',
                                   library / 'spice' / (scl + '.spice'), library / 'gds' / (scl + '.gds'),
                                   Path(__file__), recipe, drc, extract, compare, signoff / 'audit.log',
                                   signoff / 'antenna.rpt', library / 'lef' / (scl + '.lef')]}}
    result['diagnostic_physical_pass'] = (result['magic_drc_rectangles'] == 0 and result['lvs_unique_match']
                                          and result['antenna_net_violations'] == 0
                                          and result['antenna_pin_violations'] == 0
                                          and result['power_pins_total'] is not None
                                          and result['power_pins_total'] == result['power_pins_connected'])
    (signoff / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
