#!/usr/bin/env python3
"""Isolated, reproducible timing candidate; run inside the pinned container."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[2]
FLOW = Path(__file__).resolve().parent
DEFAULT_PDK = '/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae'
TOOLS = {
    'yosys': '/nix/store/4bmfi4470w0i3ixcaidfki18d3fyqvva-yosys-with-plugins-0.62/bin/yosys',
    'openroad': '/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad',
}


def run(tool, args, log):
    with log.open('w') as out:
        subprocess.run([TOOLS.get(tool, tool), *map(str, args)], cwd=REPO,
                       stdout=out, stderr=subprocess.STDOUT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'synth', 'place', 'cts', 'pdn', 'route', 'extract', 'report', 'all'], required=True)
    parser.add_argument('--library', choices=['hd', 'hs'], default='hd')
    parser.add_argument('--pdk-root', default=DEFAULT_PDK)
    parser.add_argument('--mode-mhz', type=int, choices=[100, 250, 300, 400, 450], default=450,
                        help='Timing report mode; physical implementation uses 450 MHz')
    parser.add_argument('--repair-extracted', action='store_true',
                        help='Archive the initial route and repair using its maximum-RC SPEF')
    parser.add_argument('--repair-ports', action='store_true',
                        help='Archive an existing route and give aliased output ports separate drivers')
    parser.add_argument('--repair-critical', action='store_true',
                        help='Archive an existing route and strengthen its measured critical cells')
    parser.add_argument('--repair-recovery', action='store_true',
                        help='Archive an existing route and strengthen reset release paths')
    parser.add_argument('--repair-closure', action='store_true',
                        help='Targeted HS closure using all nine extracted cell/RC screens')
    parser.add_argument('--repair-clock-roles', action='store_true',
                        help='Correct HS local-clock routing roles while retaining other signal wires')
    args = parser.parse_args()
    if args.repair_closure and (args.library != 'hs' or args.stage != 'route' or any([
            args.repair_extracted, args.repair_ports, args.repair_critical, args.repair_recovery, args.repair_clock_roles])):
        parser.error('--repair-closure requires HS, --stage route, and no other repair flag')
    if args.repair_clock_roles and (args.library != 'hs' or args.stage != 'route' or any([
            args.repair_extracted, args.repair_ports, args.repair_critical, args.repair_recovery, args.repair_closure])):
        parser.error('--repair-clock-roles requires HS, --stage route, and no other repair flag')
    if args.mode_mhz != 450 and args.stage != 'report':
        parser.error('Non-450 modes are only supported for timing reports')
    if args.repair_extracted and args.stage != 'route':
        parser.error('--repair-extracted requires --stage route')
    if args.repair_ports and (args.stage != 'route' or args.repair_extracted):
        parser.error('--repair-ports requires --stage route and cannot combine with --repair-extracted')
    if args.repair_recovery and (args.stage != 'route' or args.repair_extracted or args.repair_ports or args.repair_critical):
        parser.error('--repair-recovery requires --stage route and no other repair flag')
    if args.repair_critical and (args.stage != 'route' or args.repair_extracted or args.repair_ports):
        parser.error('--repair-critical requires --stage route and no other repair flag')
    root = REPO / 'build/timing450' / args.library
    root.mkdir(parents=True, exist_ok=True)
    pdk = Path(args.pdk_root) / 'sky130A'
    scl = 'sky130_fd_sc_' + args.library
    libroot = pdk / 'libs.ref' / scl
    lib = libroot / 'lib' / (scl + '__tt_025C_1v80.lib')
    slow = libroot / 'lib' / (scl + '__ss_100C_1v60.lib')
    if args.repair_closure:
        from closure import close
        close(root, pdk, run)
        return
    if args.repair_clock_roles:
        from closure import repair_clock_roles
        repair_clock_roles(root, pdk, run)
        return
    if args.stage in ['prepare', 'all']:
        snapshot = root / 'rtl_snapshot'
        snapshot.mkdir(exist_ok=True)
        for directory in [REPO / 'rtl', FLOW / 'rtl']:
            for source in directory.glob('*.v'):
                shutil.copyfile(source, snapshot / source.name)
        makefile = (REPO / 'Makefile').read_text().replace('rtl/', str(snapshot.relative_to(REPO)) + '/')
        makefile = makefile.replace('build/frequency-acquisition', str(root.relative_to(REPO)) + '/regression')
        (root / 'Makefile').write_text(makefile)
        manifest = {str(f.relative_to(REPO)): hashlib.sha256(f.read_bytes()).hexdigest()
                    for f in sorted(snapshot.glob('*.v'))}
        (root / 'source_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        if args.stage == 'prepare':
            return
    stages = ['synth', 'place', 'cts', 'pdn', 'route', 'extract', 'report'] if args.stage == 'all' else [args.stage]
    for stage in stages:
        if stage == 'synth':
            cells = re.findall(r'cell\s*\(\s*"?([^"\s)]+)', lib.read_text())
            excluded = [c for c in cells if 'probe' in c or 'lpflow' in c]
            names = ['B2TH', 'MMD_Retimer', 'Divider', 'DLF', 'DigitalCore', 'FrequencyAcquisition', 'TuningHandoff', 'AcquiringCore']
            sources = ' '.join(str(root / 'rtl_snapshot' / ('IntegerPLL_' + n + '.v')) for n in names)
            ys = f'''read_verilog {sources}
hierarchy -check -top IntegerPLL_AcquiringCore
flatten
proc
# Keeping the wire alone does not stop opt_merge from sharing its FF.
setattr -set keep 1 w:*advance_* %ci
synth -top IntegerPLL_AcquiringCore -flatten
write_verilog -noattr -norename {root}/pre_map.v
dfflibmap -liberty {lib}
abc -liberty {lib} -D 2222 {' '.join('-dont_use ' + c for c in excluded)}
clean
stat -liberty {lib}
write_verilog -norename {root}/mapped.v
write_json {root}/mapped.json
'''
            recipe = root / 'synth.ys'
            recipe.write_text(ys)
            run('yosys', ['-s', recipe], root / 'synth.log')
            module = json.loads((root / 'mapped.json').read_text())['modules']['IntegerPLL_AcquiringCore']
            def driver(bit):
                found = [n for n, c in module['cells'].items() if c['connections'].get('Q') == [bit]]
                if len(found) != 1:
                    raise RuntimeError(f'Expected one Q driver for bit {bit}: {found}')
                return found[0]
            clock = driver(module['ports']['CLKDIV_RETIMED']['bits'][0])
            resets = {}
            for n, net in module['netnames'].items():
                if n in ['core.gen_local_resets.fast_pipe', 'core.gen_local_resets.fine_pipe', 'ref_reset_pipe', 'dco_reset_pipe']:
                    resets[n] = driver(net['bits'][1])
            control = [driver(module['netnames']['core.feedback_divider.gen_countdown.' + n]['bits'][0])
                       for n in ['advance_active', 'advance_counter', 'advance_shift']]
            if len(set(control)) != 3:
                raise RuntimeError('Reload control replicas were merged')
            if any(c['type'] in excluded for c in module['cells'].values()):
                raise RuntimeError('Excluded cell family present')
            (root / 'mapping.json').write_text(json.dumps({'clock': clock, 'resets': resets, 'reload_controls': control}, indent=2) + '\n')
            def pins(name, index=None, pin='D'):
                bits = module['netnames'][name]['bits']
                if index is not None:
                    bits = [bits[index]]
                result = []
                for bit in bits:
                    if not isinstance(bit, int):
                        continue
                    outputs = [n for n, c in module['cells'].items() if c['connections'].get('Q') == [bit]]
                    if not outputs and not any(bit in b for c in module['cells'].values() for b in c['connections'].values()):
                        # Unconsumed destination bundle bits are optimized away.
                        continue
                    result.append(driver(bit) + '/' + pin)
                if not result:
                    raise RuntimeError(f'No active endpoints for {name}')
                return result
            exceptions = []
            receivers = [
                ('acquisition.gray_meta', None, 'PLLOUT'),
                ('acquisition.rail_meta', None, 'FINECLK'),
                ('handoff.request_meta', None, 'REFCLK'),
                ('handoff.acknowledge_meta', None, 'PLLOUT'),
                ('gen_feedback_handoff.fine_handoff.request_meta', None, 'REFCLK'),
                ('gen_feedback_handoff.fine_handoff.acknowledge_meta', None, 'FINECLK'),
                ('core.gen_event_cdc.up_pipe', 0, 'EVENT_BBPD[1]'),
                ('core.gen_event_cdc.dn_pipe', 0, 'EVENT_BBPD[0]'),
            ]
            for name, index, source_clock in receivers:
                targets = ' '.join(pins(name, index))
                exceptions.append(f'set_false_path -from [get_clocks {{{source_clock}}}] -to [get_pins {{{targets}}}]')
            for name, period in [('handoff', 2.222222), ('gen_feedback_handoff.fine_handoff', 40.0)]:
                sources = ' '.join(sorted({p.rsplit('/', 1)[0] for p in pins(name + '.payload', pin='Q')}))
                targets = ' '.join(pins(name + '.APPLIED_COMMAND'))
                exceptions += [
                    f'set_max_delay {2 * period - .15:.6f} -ignore_clock_latency -from [get_cells {{{sources}}}] -to [get_pins {{{targets}}}]',
                    f'set_min_delay 0 -ignore_clock_latency -from [get_cells {{{sources}}}] -to [get_pins {{{targets}}}]',
                ]
            (root / 'cdc.tcl').write_text('# Endpoint-specific receiver exceptions and bundled-data bounds.\n' + '\n'.join(exceptions) + '\n')
            continue
        mapping = json.loads((root / 'mapping.json').read_text())
        mapped = json.loads((root / 'mapped.json').read_text())['modules']['IntegerPLL_AcquiringCore']
        track_bits = mapped['netnames']['track_pipe']['bits']
        track_receivers = []
        for bit in track_bits:
            drivers = [(name, cell) for name, cell in mapped['cells'].items()
                       if cell['connections'].get('Q') == [bit]]
            if len(drivers) != 1 or 'RESET_B' not in drivers[0][1]['connections']:
                raise RuntimeError('Tracking reset receiver is not the expected two-stage synchronizer')
            track_receivers.append(drivers[0])
        if len(track_receivers) != 2 or track_receivers[1][1]['connections']['D'] != [track_bits[0]]:
            raise RuntimeError('Tracking reset receiver stages are not directly connected')
        if track_receivers[0][1]['connections']['CLK'] != track_receivers[1][1]['connections']['CLK'] or track_receivers[0][1]['connections']['RESET_B'] != track_receivers[1][1]['connections']['RESET_B']:
            raise RuntimeError('Tracking reset receivers must share clock and asynchronous assertion')
        if 'ASYNC_REG' not in mapped['netnames']['track_pipe']['attributes']:
            raise RuntimeError('Tracking reset receiver lacks ASYNC_REG declaration')
        receiver_pins = ' '.join(name + '/RESET_B' for name, _ in track_receivers)
        (root / 'receiver_resets.tcl').write_text(
            '# REF-domain withdrawal asserts this receiver asynchronously.\n'
            '# Its two registers release tracking on PLLOUT. This exception\n'
            '# ends at their reset pins; final-Q functional paths remain timed.\n'
            f'set_false_path -from [get_clocks REFCLK] -to [get_pins {{{receiver_pins}}}]\n')
        techs = [libroot / 'techlef' / (scl + '__nom.tlef')]
        if not techs[0].exists():
            raise RuntimeError(f'Expected one nominal technology LEF: {techs}')
        header = f'read_lef {techs[0]}\nread_lef {libroot}/lef/{scl}.lef\n'
        extra = libroot / 'lef' / ('sky130_ef_sc_' + args.library + '.lef')
        if extra.exists():
            header += f'read_lef {extra}\n'
        header += f'read_liberty {slow}\n'
        if args.library == 'hs' and stage == 'route':
            fast = libroot / 'lib' / (scl + '__ff_n40C_1v95.lib')
            if args.repair_extracted:
                corners = [corner + '_' + rc for corner in ['ss', 'tt', 'ff'] for rc in ['min', 'nom', 'max']]
                model_files = {'ss': slow, 'ff': fast, 'tt': libroot / 'lib' / (scl + '__tt_025C_1v80.lib')}
                libs = 'define_corners ' + ' '.join(corners) + '\n'
                libs += ''.join(f'read_liberty -corner {corner} {model_files[corner.split("_")[0]]}\n' for corner in corners)
                header = header.replace(f'read_liberty {slow}\n', libs)
            else:
                header = header.replace(f'read_liberty {slow}\n',
                                        f'define_corners slow fast\nread_liberty -corner slow {slow}\nread_liberty -corner fast {fast}\n')
        sdc = (FLOW / 'constraints.tcl').read_text().replace('@CLOCK_PIN@', mapping['clock'] + '/Q')
        (root / 'constraints.tcl').write_text(sdc)
        common = f'source {root}/constraints.tcl\nset_wire_rc -signal -layer met2\nset_wire_rc -clock -layer met3\nset_dont_use [get_lib_cells {{*probe* *lpflow*}}]\n'
        checks = '''puts "SETUP_AND_RECOVERY_SCREEN"
report_checks -path_delay max -group_path_count 10 -slack_max 100 -digits 6 -fields {slew capacitance fanout} -format full_clock_expanded
puts "HOLD_AND_REMOVAL_SCREEN"
report_checks -path_delay min -group_path_count 10 -slack_max 100 -digits 6 -fields {slew capacitance fanout} -format full_clock_expanded
report_check_types -max_slew -max_capacitance -min_pulse_width -violators
check_setup -verbose
check_placement -verbose
'''
        if stage == 'place':
            site = 'unithd' if args.library == 'hd' else 'unit'
            body = f'read_verilog {root}/mapped.v\nlink_design IntegerPLL_AcquiringCore\ninitialize_floorplan -utilization 35 -aspect_ratio 1 -core_space 10 -site {site}\n' + common
            body += (FLOW / 'isolate.tcl').read_text().replace('@SCL@', scl).replace('@CLOCK_INST@', mapping['clock'])
            body += '\n'
            body += (FLOW / 'exports.tcl').read_text().replace('@SCL@', scl) + '\n'
            for i, inst in enumerate(sorted(set(mapping['resets'].values()))):
                body += f'isolate_driver {{{inst}}} reset_root_{i} {scl}__buf_2 {scl}__buf_16\n'
            body += f'set_dont_touch [get_cells {{{mapping["clock"]}}}]\n'
            body += f'''set_placement_padding -global -left 1 -right 1
make_tracks
place_pins -hor_layers met3 -ver_layers met4
global_placement -timing_driven -density 0.55
estimate_parasitics -placement
repair_design
estimate_parasitics -placement
repair_timing -setup -setup_margin 0.10 -max_iterations 100
detailed_placement
estimate_parasitics -placement
''' + checks + f'write_db {root}/placed.odb\nwrite_verilog {root}/placed.v\n'
        elif stage == 'cts':
            body = f'read_db {root}/placed.odb\n' + common
            body += f'unset_dont_touch [get_cells {{{mapping["clock"]}}}]\n'
            for inst in [mapping['clock'], *mapping['reload_controls']]:
                body += f'replace_cell {{{inst}}} {scl}__dfrtp_4\n'
            if args.library == 'hs':
                body += (FLOW / 'cluster_roots.tcl').read_text().replace('@SCL@', scl).replace('@CLOCK_INST@', mapping['clock']) + '\n'
            body += f'''detailed_placement
set cts_nets {{REFCLK PLLOUT fine_clock_input_out}}
foreach port [[ord::get_db_block] getBTerms] {{
    if {{[string range [$port getName] 0 4] eq {{BBPD[}}}} {{lappend cts_nets [[$port getNet] getName]}}
}}
# This pinned CTS parses whitespace rather than Tcl list syntax; join
# removes list braces around bus names while preserving literal brackets.
clock_tree_synthesis -clk_nets [join $cts_nets " "] -root_buf {scl}__clkbuf_16 -buf_list {{{scl}__clkbuf_2 {scl}__clkbuf_4 {scl}__clkbuf_8 {scl}__clkbuf_16}} -sink_clustering_enable -sink_clustering_size 8 -sink_clustering_max_diameter 30
detailed_placement
set_propagated_clock [all_clocks]
set_dont_touch [get_cells {{{mapping['clock']}}}]
estimate_parasitics -placement
repair_design
estimate_parasitics -placement
repair_timing -setup -setup_margin 0.10 -max_iterations 100
repair_timing -hold -hold_margin 0.05 -max_iterations 100
detailed_placement
estimate_parasitics -placement
''' + checks + f'write_db {root}/cts.odb\nwrite_verilog {root}/cts.v\n'
        elif stage == 'pdn':
            body = f'read_db {root}/cts.odb\n'
            body += (FLOW / 'pdn.tcl').read_text().replace('@SCL@', scl).replace('@ROOT@', str(root)).replace('@CLOCK_INST@', mapping['clock']).replace('@DECAP@', '3' if args.library == 'hd' else '4')
        elif stage == 'route':
            initial = root / 'initial_route'
            if args.repair_extracted:
                if initial.exists():
                    if (initial / 'route.odb').read_bytes() != (root / 'route.odb').read_bytes():
                        raise RuntimeError('Current route differs from archived baseline; refusing repeated repair')
                else:
                    initial.mkdir()
                    for source in [*root.glob('route.*'), root / 'assessment.json']:
                        if source.exists() and source.is_file():
                            shutil.copy2(source, initial / source.name)
                    shutil.copytree(root / 'reports_450', initial / 'reports_450')
                body = f'read_db {initial}/route.odb\n' + common
                body += 'set_propagated_clock [all_clocks]\n'
                if args.library == 'hs':
                    body += ''.join(f'read_spef -corner {corner} {initial}/route.{corner.split("_")[1]}.normalized.spef\n' for corner in corners)
                    body += 'remove_fillers\nunset_dont_touch [get_cells *]\n'
                    # Recovery repair is not covered by the resizer's setup
                    # optimizer. Strengthen its launch roots explicitly.
                    for inst in sorted(set(mapping['resets'].values())):
                        master = re.sub(r'_[124]$', '_4', mapped['cells'][inst]['type'])
                        body += f'replace_cell {{{inst}}} {master}\n'
                    for index in range(len(set(mapping['resets'].values()))):
                        body += f'replace_cell reset_root_{index}_input {scl}__buf_16\n'
                    previous = (initial / 'reports_450/ss_max_timing.log').read_text()
                    cells = {}
                    for path in previous.split('Startpoint:')[1:]:
                        if 'Path Type: max' not in path:
                            continue
                        for inst, master in re.findall(r' ([^\s]+)/[^\s]+ \((sky130_fd_sc_\w+)\)', path):
                            if master.endswith(('_1', '_2')) and '__clkbuf_' not in master:
                                cells[inst] = re.sub(r'_[12]$', '_4', master)
                    (root / 'extracted_cells.json').write_text(json.dumps(cells, indent=2) + '\n')
                    for inst, master in cells.items():
                        body += f'if {{[[ord::get_db] findMaster {master}] ne {{NULL}}}} {{replace_cell {{{inst}}} {master}}}\n'
                else:
                    body += f'read_spef {initial}/route.max.normalized.spef\nremove_fillers\nunset_dont_touch [get_cells *]\n'
                body += 'repair_design\nrepair_timing -setup -setup_margin 0.10 -max_iterations 100\nrepair_timing -hold -hold_margin 0.05 -max_iterations 100\ndetailed_placement\n'
                body += f'write_db {root}/extracted_repaired.odb\nwrite_verilog {root}/extracted_repaired.v\n'

                body += '''# Preserve supply special wires, but reroute every signal net.
foreach net [[ord::get_db_block] getNets] {
    if {[$net getWire] ne {NULL}} {odb::dbWire_destroy [$net getWire]}
}
'''
            elif args.repair_ports or args.repair_critical or args.repair_recovery:
                if args.repair_critical or args.repair_recovery:
                    assessment = json.loads((root / 'reports_450/assessment.json').read_text())
                    key = str((root / 'route.odb').relative_to(REPO))
                    if assessment['sha256'][key] != hashlib.sha256((root / 'route.odb').read_bytes()).hexdigest():
                        raise RuntimeError('Measured repair requires timing reports for the current route')
                before = root / ('before_recovery' if args.repair_recovery else 'before_critical' if args.repair_critical else 'before_ports')
                if before.exists():
                    if (before / 'route.odb').read_bytes() != (root / 'route.odb').read_bytes():
                        raise RuntimeError('Current route differs from saved port-repair baseline')
                else:
                    before.mkdir()
                    for source in root.glob('route.*'):
                        if source.is_file():
                            shutil.copy2(source, before / source.name)
                    for source in root.glob('reports_*'):
                        shutil.copytree(source, before / source.name)
                body = f'read_db {before}/route.odb\n' + common + 'remove_fillers\n'
                if not (args.repair_critical or args.repair_recovery):
                    body += (FLOW / 'exports.tcl').read_text().replace('@SCL@', scl) + '\n'
                if args.repair_critical:
                    selected = {}
                    for name in ['core.feedback_divider.gen_ratio_pipe.ratio_q',
                                 'core.feedback_divider.gen_registered_config.terminal_q',
                                 'core.feedback_divider.gen_registered_config.duty_q',
                                 'core.feedback_divider.counter']:
                        if name not in mapped['netnames']:
                            if name.endswith('.duty_q'):
                                continue  # Countdown implementation does not use duty_count.
                            raise RuntimeError(f'Missing required divider register bank: {name}')
                        for bit in mapped['netnames'][name]['bits']:
                            for inst, cell in mapped['cells'].items():
                                if cell['connections'].get('Q') == [bit]:
                                    selected[inst] = re.sub(r'_[124]$', '_4', cell['type'])
                    previous = (before / 'reports_450/ss_max_timing.log').read_text()
                    for path in previous.split('Startpoint:')[1:]:
                        if 'Path Group: PLLOUT\n' not in path or 'Path Type: max' not in path:
                            continue
                        for inst, master in re.findall(r' ([^\s]+)/[^\s]+ \((sky130_fd_sc_\w+)\)', path):
                            if master.endswith(('_1', '_2')) and '__clkbuf_' not in master:
                                selected[inst] = re.sub(r'_[12]$', '_4', master)
                    (root / 'critical_cells.json').write_text(json.dumps(selected, indent=2) + '\n')
                    for inst, master in selected.items():
                        body += f'if {{[[ord::get_db] findMaster {master}] ne {{NULL}}}} {{replace_cell {{{inst}}} {master}}}\n'
                    body += f'puts "CRITICAL_CELL_SCREEN selected={len(selected)}"\n'
                if args.repair_recovery:
                    selected = {inst: re.sub(r'_[124]$', '_4', mapped['cells'][inst]['type'])
                                for inst in set(mapping['resets'].values())}
                    previous = (before / 'reports_450/ss_max_timing.log').read_text()
                    for path in previous.split('Startpoint:')[1:]:
                        if 'Path Group: asynchronous\n' not in path or 'Path Type: max' not in path:
                            continue
                        for inst, master in re.findall(r' ([^\s]+)/[^\s]+ \((sky130_fd_sc_\w+)\)', path):
                            if inst.startswith('reset_root_') and inst.endswith('_input'):
                                selected[inst] = scl + '__buf_16'
                            elif master.endswith(('_1', '_2')) and '__clkbuf_' not in master:
                                selected[inst] = re.sub(r'_[12]$', '_4', master)
                    (root / 'recovery_cells.json').write_text(json.dumps(selected, indent=2) + '\n')
                    for inst, master in selected.items():
                        body += f'if {{[[ord::get_db] findMaster {master}] ne {{NULL}}}} {{replace_cell {{{inst}}} {master}}}\n'
                    body += f'puts "RECOVERY_CELL_SCREEN selected={len(selected)}"\n'
                if args.library == 'hs':
                    body += (FLOW / 'cluster_roots.tcl').read_text().replace('@SCL@', scl).replace('@CLOCK_INST@', mapping['clock']) + '\n'
                    if not (args.repair_critical or args.repair_recovery):
                        body += (FLOW / 'pulse_guards.tcl').read_text().replace('@SCL@', scl) + '\n'
                body += '''detailed_placement
foreach net [[ord::get_db_block] getNets] {
    if {[$net getWire] ne {NULL}} {odb::dbWire_destroy [$net getWire]}
}
'''
            else:
                body = f'read_db {root}/pdn.odb\n' + common
                body += 'remove_fillers\n'
                if args.library == 'hs':
                    body += (FLOW / 'pulse_guards.tcl').read_text().replace('@SCL@', scl) + '\n'
            body += f'''set_propagated_clock [all_clocks]
set_routing_layers -signal met1-met5 -clock met3-met5
set_global_routing_layer_adjustment met2 0.5
set_global_routing_layer_adjustment met3 0.5
global_route -verbose -guide_file {root}/route.guide -congestion_iterations 100
estimate_parasitics -global_routing
'''
            if not args.repair_extracted:
                body += f'''repair_design
estimate_parasitics -global_routing
repair_timing -setup -setup_margin 0.10 -max_iterations 100
# Protected reset drivers can also trigger RSZ-3009 with no eligible loads.
unset_dont_touch [get_cells *]
repair_timing -hold -hold_margin 0.05 -max_iterations 100
'''
            body += f'''set_dont_touch [get_cells {{{mapping['clock']}}}]
detailed_placement
filler_placement {{{scl}__fill_8 {scl}__fill_4 {scl}__fill_2 {scl}__fill_1}}
unset_dont_touch [get_cells *]
global_connect
set_dont_touch [get_cells {{fine_clock_input fine_signal_output reset_root_* pulse_guard_* {mapping['clock']}}}]
check_placement -verbose
global_route -verbose -guide_file {root}/route.guide -congestion_iterations 100
write_db {root}/global_route.odb
set_thread_count 2
detailed_route -output_drc {root}/route.drc -output_maze {root}/route.maze.log -output_guide_coverage {root}/route.coverage
write_db {root}/route.odb
write_def {root}/route.def
write_verilog {root}/route.v
'''
        elif stage == 'extract':
            for rc in ['nom', 'min', 'max']:
                recipe = root / ('extract_' + rc + '.tcl')
                recipe.write_text(header + f'read_db {root}/route.odb\n' + common + f'''define_process_corner -ext_model_index 0 RCX_{rc.upper()}
extract_parasitics -ext_model_file {pdk}/libs.tech/librelane/rules.openrcx.sky130A.{rc}.magic -corner 0
write_spef {root}/route.{rc}.spef
exit
''')
                run('openroad', ['-exit', recipe], root / ('extract_' + rc + '.log'))
                spef = root / ('route.' + rc + '.spef')
                lines = spef.read_text().splitlines()
                inside = False
                for i, line in enumerate(lines):
                    if line == '*NAME_MAP':
                        inside = True
                    elif line.startswith('*PORTS'):
                        inside = False
                    elif inside and ' clkbuf_' in line and 'BBPD' in line:
                        lines[i] = line.replace('\\[', '[').replace('\\]', ']')
                (root / ('route.' + rc + '.normalized.spef')).write_text('\n'.join(lines) + '\n')
            continue
        elif stage == 'report':
            reportroot = root / f'reports_{args.mode_mhz}'
            reportroot.mkdir(exist_ok=True)
            mode_sdc = sdc.replace('-period 2.222222', f'-period {1000 / args.mode_mhz:.9f}').replace('-divide_by 18', f'-divide_by {args.mode_mhz // 25}')
            mode_sdc = mode_sdc.replace('{0 1.111}', '{0 %.9f}' % (500 / args.mode_mhz))
            for constraints_file in ['cdc.tcl', 'receiver_resets.tcl']:
                mode_sdc = mode_sdc.replace(f'source [file join [file dirname [info script]] {constraints_file}]', f'source {root}/{constraints_file}')
            (reportroot / 'constraints.tcl').write_text(mode_sdc)
            mode_common = common.replace(f'source {root}/constraints.tcl', f'source {reportroot}/constraints.tcl')
            result = {'release_qualified': False, 'selected': False, 'mode_mhz': args.mode_mhz, 'timing_ns': {}, 'models': {}, 'gates': {}}
            for corner, pattern in [('tt', '*__tt_025C_1v80.lib'), ('ss', '*__ss_100C_1v60.lib'), ('ff', '*__ff_n40C_1v95.lib')]:
                models = list((libroot / 'lib').glob(pattern))
                if len(models) != 1:
                    raise RuntimeError(f'Missing corner model: {corner}')
                result['models'][corner] = str(models[0])
                result['timing_ns'][corner] = {}
                for rc in ['nom', 'min', 'max']:
                    recipe = reportroot / f'{corner}_{rc}_timing.tcl'
                    recipe.write_text(header.replace(str(slow), str(models[0])) + f'read_db {root}/route.odb\n' + mode_common + f'set_propagated_clock [all_clocks]\nread_spef {root}/route.{rc}.normalized.spef\nreport_parasitic_annotation -report_unannotated\n' + checks + 'exit\n')
                    log = reportroot / f'{corner}_{rc}_timing.log'
                    run('openroad', ['-exit', recipe], log)
                    text = log.read_text()
                    if 'STA-1648' in text or 'STA-1650' in text:
                        raise RuntimeError(f'SPEF name mismatch: {log}')
                    rows = {}
                    for block in text.split('Startpoint:')[1:]:
                        g = re.search(r'Path Group: ([^\n]+)', block)
                        t = re.search(r'Path Type: ([^\n]+)', block)
                        v = re.search(r'(-?\d+\.\d+)\s+slack \(', block)
                        if g and t and v:
                            key = t[1] + '/' + g[1]
                            rows[key] = min(rows.get(key, float(v[1])), float(v[1]))
                    result['timing_ns'][corner][rc] = rows
                    result['gates'][f'{corner}/{rc}'] = bool(rows) and all(v >= (0.10 if k.startswith('max/') else 0.05) for k, v in rows.items()) and '(VIOLATED)' not in text
            result['diagnostic_timing_pass'] = all(result['gates'].values())
            result['limitations'] = ['Only three supplied cell corners; 45-point qualification not established', 'CDC/bundle and interface loads remain diagnostic', 'Independent physical signoff required']
            result['sha256'] = {str(f.relative_to(REPO)): hashlib.sha256(f.read_bytes()).hexdigest()
                                for f in [root / 'route.odb', root / 'route.v', reportroot / 'constraints.tcl',
                                          root / 'cdc.tcl', root / 'receiver_resets.tcl',
                                          *reportroot.glob('*_timing.log'), *root.glob('route.*.normalized.spef'),
                                          *FLOW.glob('*.py'), *FLOW.glob('*.tcl')]
                                if f.is_file()}
            result['model_sha256'] = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in result['models'].values()}
            (reportroot / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
            if args.mode_mhz == 450:
                (root / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps({'diagnostic_timing_pass': result['diagnostic_timing_pass'], 'timing_ns': result['timing_ns']}))
            continue
        recipe = root / (stage + '.tcl')
        recipe.write_text(header + body + 'exit\n')
        run('openroad', ['-exit', recipe], root / (stage + '.log'))


if __name__ == '__main__':
    main()
