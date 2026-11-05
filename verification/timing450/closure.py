#!/usr/bin/env python3
"""Measured, reversible HS physical ECOs; never select a release candidate."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

FLOW = Path(__file__).resolve().parent
REPO = FLOW.parents[1]
CORNERS = [f'{cell}_{rc}' for cell in ('ss', 'tt', 'ff') for rc in ('min', 'nom', 'max')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def block(text, start):
    depth = 1
    for match in re.compile(r'[{}]').finditer(text, start):
        depth += 1 if match[0] == '{' else -1
        if not depth:
            return text[start:match.start()]
    raise ValueError('Unbalanced Liberty block')


def pin_caps(models):
    """Worst supplied input capacitance, with user-facing Liberty pF units."""
    result = {}
    for model in models.values():
        text = model.read_text()
        for match in re.finditer(r'\bcell\s*\(\s*"?([^"\s)]+)"?\s*\)\s*\{', text):
            cell = block(text, match.end())
            for pin in re.finditer(r'\bpin\s*\(\s*"?([^"\s)]+)"?\s*\)\s*\{', cell):
                body = block(cell, pin.end())
                cap = re.search(r'\bcapacitance\s*:\s*([\d.eE+-]+)', body)
                if cap:
                    key = match[1] + '/' + pin[1]
                    result[key] = max(result.get(key, 0), float(cap[1]))
    return result


def buffer_masters(model):
    text = model.read_text()
    result = []
    pattern = r'\bcell\s*\(\s*"?([^"\s)]+)"?\s*\)\s*\{'
    for match in re.finditer(pattern, text):
        cell = block(text, match.end())
        inputs, outputs = [], []
        for pin in re.finditer(r'\bpin\s*\(\s*"?([^"\s)]+)"?\s*\)\s*\{', cell):
            body = block(cell, pin.end())
            direction = re.search(r'\bdirection\s*:\s*"?(input|output)', body)
            function = re.search(r'\bfunction\s*:\s*"([^";]+)"', body)
            if direction and direction[1] == 'input':
                inputs.append(pin[1])
            elif direction and direction[1] == 'output':
                outputs.append(re.sub(r'[()\s]', '', function[1]) if function else None)
        if inputs == ['A'] and outputs == ['A']:
            result.append(match[1])
    if not result:
        raise RuntimeError(f'No noninverting buffer masters found in {model}')
    return result


def current_reports(root):
    report = root / 'reports_450/assessment.json'
    result = json.loads(report.read_text())
    for path, digest in result['sha256'].items():
        # The flow source has deliberately changed. Physical and timing inputs must not.
        file = REPO / path
        if file.parent == FLOW:
            continue
        if not file.exists() or sha(file) != digest:
            raise RuntimeError(f'Stale closure input: {file}')
    for path, digest in result['model_sha256'].items():
        if sha(Path(path)) != digest:
            raise RuntimeError(f'Changed timing model: {path}')
    return result


def archive(root):
    parent = root / 'closure'
    parent.mkdir(exist_ok=True)
    iterations = sorted(parent.glob('iteration_*'))
    iteration = parent / f'iteration_{len(iterations):03d}'
    iteration.mkdir()
    snapshot = iteration / 'flow_snapshot'
    snapshot.mkdir()
    for file in [*FLOW.glob('*.py'), *FLOW.glob('*.tcl'), FLOW / 'Makefile']:
        shutil.copy2(file, snapshot / file.name)
    source = iteration / 'input'
    source.mkdir()
    for file in root.iterdir():
        if file.name in ('closure', 'initial_route', 'before_critical', 'before_ports', 'before_recovery'):
            continue
        if file.is_file() and ((file.name.startswith('route.') or file.name in ('physical_assessment.json', 'physical_gate_raw.json', 'assessment.json', 'mapping.json', 'mapped.json', 'mapped.v', 'pre_map.v', 'source_manifest.json', 'receiver_resets.tcl', 'constraints.tcl', 'cdc.tcl'))):
            shutil.copy2(file, source / file.name)
        elif file.is_dir() and (file.name.startswith('reports_') or file.name == 'rtl_snapshot'):
            shutil.copytree(file, source / file.name)
    inputs = {str(p.relative_to(source)): sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
    (iteration / 'input_manifest.json').write_text(json.dumps(inputs, indent=2) + '\n')
    return iteration


def header(root, pdk, iteration, models):
    libroot = pdk / 'libs.ref/sky130_fd_sc_hs'
    text = f'read_lef {libroot}/techlef/sky130_fd_sc_hs__nom.tlef\nread_lef {libroot}/lef/sky130_fd_sc_hs.lef\n'
    text += 'define_corners ' + ' '.join(CORNERS) + '\n'
    # Give each corner its own library name; otherwise repeated Liberty reads
    # emit STA-1140 and make corner assignment ambiguous. Cell/timing data is unchanged.
    for corner in CORNERS:
        model = models[corner.split('_')[0]]
        renamed, count = re.subn(r'(\blibrary\s*\(\s*)"?[^"\s)]+"?', rf'\1"closure_{corner}"', model.read_text(), count=1)
        if count != 1:
            raise RuntimeError(f'Cannot identify Liberty library name: {model}')
        dest = iteration / f'{corner}.lib'
        dest.write_text(renamed)
        text += f'read_liberty -corner {corner} {dest}\n'
    text += f'read_db {root}/route.odb\nsource {root}/constraints.tcl\n'
    text += 'set_wire_rc -signal -layer met2\nset_wire_rc -clock -layer met3\nset_propagated_clock [all_clocks]\n'
    for corner in CORNERS:
        text += f'read_spef -corner {corner} {root}/route.{corner.split("_")[1]}.normalized.spef\n'
    return text


def protected_receivers(root):
    # A synchronized output may cross again into a different domain. Protect
    # the direct link inside each pair, while permitting repair before a
    # timed first-stage input in the next domain.
    return [receiver + '/D' for _, receiver in receiver_pairs(root)]


def async_cells(root):
    module = json.loads((root / 'mapped.json').read_text())['modules']['IntegerPLL_AcquiringCore']
    bits = {bit for net in module['netnames'].values() if 'ASYNC_REG' in net.get('attributes', {}) for bit in net['bits']}
    return [name for name, cell in module['cells'].items() if cell['connections'].get('Q', [None])[0] in bits]


def receiver_pairs(root):
    module = json.loads((root / 'mapped.json').read_text())['modules']['IntegerPLL_AcquiringCore']
    bits = {bit for net in module['netnames'].values() if 'ASYNC_REG' in net.get('attributes', {}) for bit in net['bits']}
    drivers = {cell['connections']['Q'][0]: name for name, cell in module['cells'].items()
               if 'Q' in cell['connections']}
    result = []
    for name, cell in module['cells'].items():
        data = cell['connections'].get('D', [None])[0]
        if data in bits and cell['connections'].get('Q', [None])[0] in bits:
            source = drivers.get(data)
            if source and cell['connections'].get('CLK') == module['cells'][source]['connections'].get('CLK'):
                result.append((source, name))
    return result


def decoder_outputs(root):
    """Resolve electrical violations by live net names, never generated instance IDs."""
    module = json.loads((root / 'physical_gate_raw.json').read_text())['modules']['IntegerPLL_AcquiringCore']
    cells = {name.lstrip('\\'): cell for name, cell in module['cells'].items()}
    drivers = {bit: name + '/' + pin for name, cell in cells.items()
               for pin, bits in cell['connections'].items() if cell['port_directions'].get(pin) == 'output' for bit in bits}
    result = set()
    for log in (root / 'reports_450').glob('*_timing.log'):
        for line in log.read_text().splitlines():
            if '(VIOLATED)' not in line:
                continue
            token = line.strip().split()[0]
            if '/' not in token:
                continue
            name, pin = token.rsplit('/', 1)
            if name not in cells or pin not in cells[name]['connections']:
                continue
            net = cells[name]['connections'][pin][0]
            source = drivers.get(net)
            if source:
                # Only combinational decoder data nets. Clock/reset nets are handled separately.
                source_cell = cells[source.rsplit('/', 1)[0]]
                if '__nand' in source_cell['type'] and not any(p in source_cell['connections'] for p in ('CLK', 'Q')):
                    result.add(source)
    return sorted(result)


def critical_launchers(root):
    """Worst supplied max-path launch FF for PLL setup and recovery."""
    worst = {}
    for log in (root / 'reports_450').glob('*_timing.log'):
        text = log.read_text().split('SETUP_AND_RECOVERY_SCREEN', 1)[-1]
        text = text.split('HOLD_AND_REMOVAL_SCREEN', 1)[0]
        for path in text.split('Startpoint:')[1:]:
            group = re.search(r'Path Group:\s*(PLLOUT|asynchronous)\n', path)
            slack = re.search(r'([+-]?[\d.]+)\s+slack \((?:MET|VIOLATED)\)', path)
            if not group or not slack or 'clocked by PLLOUT)' not in path:
                continue
            value = float(slack[1])
            if value < .10 and value < worst.get(group[1], (1e6, ''))[0]:
                worst[group[1]] = (value, path.splitlines()[0].strip())
    return sorted({name for _, name in worst.values()})


def route_script(root):
    return f'''# Reuse valid routing input; supplies retain their special wires.
if {{[info exists closure_place_inputs]}} {{
    closure_legalize_preserving $closure_place_inputs
}} else {{
    detailed_placement
}}
closure_align_clock_rows
if {{[info exists closure_wire_inputs]}} {{
    set cleared [closure_clear_changed_wires $closure_wire_inputs]
    set routing_journal [open $closure_routing_log w]
    foreach name $cleared {{puts $routing_journal [list cleared $name]}}
    close $routing_journal
}} else {{
    # Recovery from an ECO without a pre-change signature uses full routing.
    foreach net [[ord::get_db_block] getNets] {{
        if {{[$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}
    }}
}}
set_routing_layers -signal met1-met5 -clock met3-met5
set_global_routing_layer_adjustment met2 0.2
set_global_routing_layer_adjustment met3 0.2
global_route -verbose -guide_file {root}/route.guide -congestion_iterations 100
# Connect only new ECO supply pins. Existing protected instances retain their nets.
add_global_connection -net VDD -inst_pattern {{.*}} -pin_pattern {{^(VPWR|VPB)$}} -power
add_global_connection -net VSS -inst_pattern {{.*}} -pin_pattern {{^(VGND|VNB)$}} -ground
closure_connect_power
filler_placement {{sky130_fd_sc_hs__fill_8 sky130_fd_sc_hs__fill_4 sky130_fd_sc_hs__fill_2 sky130_fd_sc_hs__fill_1}}
closure_connect_power
check_placement -verbose
check_power_grid -net VDD -error_file {root}/closure_vdd_errors.rpt
check_power_grid -net VSS -error_file {root}/closure_vss_errors.rpt
global_route -verbose -guide_file {root}/route.guide -congestion_iterations 100
set_thread_count 8
detailed_route -droute_end_iter 32 -output_drc {root}/route.drc -output_maze {root}/route.maze.log -output_guide_coverage {root}/route.coverage
write_db {root}/route.odb
write_def {root}/route.def
write_verilog {root}/route.v
'''


def close(root, pdk, run):
    current_reports(root)
    libroot = pdk / 'libs.ref/sky130_fd_sc_hs/lib'
    models = {c: libroot / f'sky130_fd_sc_hs__{stem}.lib' for c, stem in
              [('ss', 'ss_100C_1v60'), ('tt', 'tt_025C_1v80'), ('ff', 'ff_n40C_1v95')]}
    caps = pin_caps(models)
    mapping = json.loads((root / 'mapping.json').read_text())
    # A failed topology/routing stage may have a fully checked sizing journal.
    # Replay only an identical physical/model parent, then recheck all corners.
    replay = None
    for previous in sorted((root / 'closure').glob('iteration_*')) if (root / 'closure').exists() else []:
        journal = previous / 'changes.txt'
        cfg = previous / 'configuration.json'
        if journal.exists() and cfg.exists() and not (previous / 'output_manifest.json').exists():
            inputs = json.loads((previous / 'input_manifest.json').read_text())
            old = json.loads(cfg.read_text())
            if inputs.get('route.odb') == sha(root / 'route.odb') and old['model_sha256'] == {str(p): sha(p) for p in models.values()}:
                replay = journal
    iteration = archive(root)
    topology = not (root / 'closure/topology_v2.json').exists()
    outputs = []
    electrical = sorted({line.strip().split()[0] for log in (root / 'reports_450').glob('*_timing.log')
                         for line in log.read_text().splitlines() if '(VIOLATED)' in line and '/' in line})
    config = {'topology': topology, 'routing_iteration_limit': 32, 'routing_capacity_reservation': {'met2': 0.2, 'met3': 0.2}, 'decoder_outputs': outputs, 'electrical_pins': electrical, 'replay': str(replay) if replay else None, 'corners': CORNERS,
              'protected_receivers': protected_receivers(root),
              'async_cells': async_cells(root),
              'receiver_pairs': receiver_pairs(root),
              'launch_cells': critical_launchers(root),
              'buffer_masters': buffer_masters(models['ss']),
              'model_sha256': {str(p): sha(p) for p in models.values()},
              'flow_sha256': {str(p): sha(p) for p in [FLOW / 'closure.py', FLOW / 'closure.tcl', FLOW / 'closure_hold.tcl', FLOW / 'closure_clone.tcl', FLOW / 'closure_cdc.tcl', FLOW / 'closure_placement.tcl', FLOW / 'closure_routing.tcl', FLOW / 'closure_launch.tcl', FLOW / 'run.py']}}
    (iteration / 'configuration.json').write_text(json.dumps(config, indent=2) + '\n')
    tcl = header(root, pdk, iteration, models)
    tcl += 'set closure_corners {' + ' '.join(CORNERS) + '}\n'
    tcl += 'set closure_clock {' + mapping['clock'] + '}\n'
    tcl += 'set closure_reset_sources {' + ' '.join(sorted(set(mapping['resets'].values()))) + '}\n'
    tcl += 'set closure_electrical_pins {' + ' '.join(electrical) + '}\n'
    tcl += 'set closure_decoder_outputs {' + ' '.join(outputs) + '}\n'
    tcl += 'set closure_buffer_masters {' + ' '.join(config['buffer_masters']) + '}\n'
    tcl += 'set closure_async_cells {' + ' '.join(config['async_cells']) + '}\n'
    tcl += 'set closure_launch_cells {' + ' '.join(config['launch_cells']) + '}\n'
    tcl += 'set closure_receiver_pairs {' + ' '.join('{' + ' '.join(pair) + '}' for pair in config['receiver_pairs']) + '}\n'
    tcl += 'set closure_protected_receivers {' + ' '.join(config['protected_receivers']) + '}\n'
    tcl += 'set closure_pin_caps [dict create ' + ' '.join('{' + k + '} ' + str(v) for k, v in caps.items()) + ']\n'
    tcl += f'set closure_journal [open {iteration}/changes.txt w]\nsource {iteration}/flow_snapshot/closure.tcl\n'
    tcl += f'source {iteration}/flow_snapshot/closure_routing.tcl\nset closure_routing_log {iteration}/routing_inputs.txt\n'
    tcl += 'set closure_wire_inputs [closure_wire_signatures]\nset closure_place_inputs [closure_place_signatures]\n'
    tcl += 'closure_protect_clocks\nremove_fillers\n'
    if replay:
        tcl += f'set replay [open {replay} r]\nset changed 0\nset replay_max [closure_slack max]\nset replay_min [closure_slack min]\n'
        tcl += '''while {[gets $replay row] >= 0} {
    if {[lindex $row 0] ne {resize}} {continue}
    lassign $row action name original replacement
    set inst [[ord::get_db_block] findInst $name]
    if {$inst eq {NULL} || [closure_protected $inst] || [[$inst getMaster] getName] ne $original} {error "invalid sizing replay $name"}
    unset_dont_touch [get_cells [list $name]]
    replace_cell [get_cells [list $name]] $replacement
    closure_log $row
    incr changed
}
close $replay
if {[closure_slack min] < min(0.05, $replay_min) - 0.000001 || [closure_slack max] < $replay_max - 0.000001} {error "sizing replay loses timing margin"}
closure_log [list replay_checked changes $changed setup [closure_slack max] hold [closure_slack min]]
'''
    else:
        tcl += 'set changed [closure_optimize]\n'
    tcl += f'source {iteration}/flow_snapshot/closure_hold.tcl\n'
    tcl += 'incr changed [closure_repair_min]\n'
    tcl += f'source {iteration}/flow_snapshot/closure_launch.tcl\nincr changed [closure_isolate_launch_clocks]\n'
    tcl += f'source {iteration}/flow_snapshot/closure_clone.tcl\nincr changed [closure_clone_drivers]\n'
    tcl += f'write_db {iteration}/sized.odb\nwrite_verilog {iteration}/sized.v\n'

    if topology:
        tcl += 'incr changed [closure_reset_banks]\n'
    tcl += f'source {iteration}/flow_snapshot/closure_cdc.tcl\nincr changed [closure_restore_receivers]\n'
    tcl += 'closure_find_electrical_drivers\nincr changed [closure_decoder_banks]\nincr changed [closure_repair_min]\n'
    tcl += f'source {iteration}/flow_snapshot/closure_placement.tcl\nincr changed [closure_localize]\n'
    tcl += f'write_db {iteration}/eco.odb\nwrite_verilog {iteration}/eco.v\nclose $closure_journal\n'
    tcl += f'if {{$changed == 0}} {{puts "CLOSURE_STALLED"; exit}}\n' + route_script(root) + 'exit\n'
    recipe = iteration / 'repair.tcl'
    recipe.write_text(tcl)
    run('openroad', ['-exit', recipe], iteration / 'repair.log')
    log = (iteration / 'repair.log').read_text()
    if '[ERROR' in log or 'STA-1140' in log or 'STA-1648' in log or 'STA-1650' in log:
        raise RuntimeError(f'Closure tool/model/parasitic error: {iteration}/repair.log')
    if 'CLOSURE_STALLED' in log:
        raise RuntimeError(f'No admissible repair; endpoints remain in {root}/reports_450')
    if topology:
        (root / 'closure/topology_v2.json').write_text(json.dumps(config, indent=2) + '\n')
    finish(root, pdk, iteration)


def finish(root, pdk, iteration):
    args = ['--library', 'hs', '--pdk-root', str(pdk.parent)]
    for stage in ('extract', 'report'):
        subprocess.run(['python3', str(FLOW / 'run.py'), *args, '--stage', stage], cwd=REPO, check=True)
    assessment = json.loads((root / 'assessment.json').read_text())
    shutil.copytree(root / 'reports_450', iteration / 'output_reports_450')
    (iteration / 'output_manifest.json').write_text(json.dumps({str(p): sha(p) for p in
        [root / 'route.odb', root / 'route.v', *root.glob('route.*.normalized.spef')]}, indent=2) + '\n')
    print(json.dumps({'iteration': str(iteration), 'diagnostic_timing_pass': assessment['diagnostic_timing_pass']}), flush=True)
    if not assessment['diagnostic_timing_pass']:
        print('Remaining violations require another measured closure iteration.', flush=True)


def repair_clock_roles(root, pdk, run):
    """No cell/placement changes: reroute misclassified local clock nets."""
    current_reports(root)
    libroot = pdk / 'libs.ref/sky130_fd_sc_hs/lib'
    models = {c: libroot / f'sky130_fd_sc_hs__{stem}.lib' for c, stem in
              [('ss', 'ss_100C_1v60'), ('tt', 'tt_025C_1v80'), ('ff', 'ff_n40C_1v95')]}
    iteration = archive(root)
    (iteration / 'configuration.json').write_text(json.dumps({
        'clock_roles_only': True, 'model_sha256': {str(p): sha(p) for p in models.values()},
        'flow_sha256': {str(FLOW / 'closure.py'): sha(FLOW / 'closure.py'),
                        str(FLOW / 'run.py'): sha(FLOW / 'run.py')}}, indent=2) + '\n')
    tcl = header(root, pdk, iteration, models)
    tcl += f'''set journal [open {iteration}/changes.txt w]
set changed 0
foreach inst [[ord::get_db_block] getInsts] {{
    if {{![regexp {{^closure_cdc_clock_[0-9]+$}} [$inst getName]]}} {{continue}}
    set net [[$inst findITerm X] getNet]
    if {{[$net getSigType] eq {{CLOCK}}}} {{continue}}
    puts $journal "clock_net_role [$net getName] CLOCK"
    $net setSigType CLOCK
    if {{[$net getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$net getWire]}}
    incr changed
}}
close $journal
if {{$changed == 0}} {{puts "CLOSURE_STALLED"; exit}}
write_db {iteration}/eco.odb
write_verilog {iteration}/eco.v
set_routing_layers -signal met1-met5 -clock met3-met5
set_global_routing_layer_adjustment met2 0.5
set_global_routing_layer_adjustment met3 0.5
global_route -verbose -guide_file {root}/route.guide -congestion_iterations 100
set_thread_count 8
detailed_route -output_drc {root}/route.drc -output_maze {root}/route.maze.log -output_guide_coverage {root}/route.coverage
write_db {root}/route.odb
write_def {root}/route.def
write_verilog {root}/route.v
exit
'''
    recipe = iteration / 'repair.tcl'
    recipe.write_text(tcl)
    run('openroad', ['-exit', recipe], iteration / 'repair.log')
    log = (iteration / 'repair.log').read_text()
    if any(token in log for token in ('[ERROR', 'STA-1140', 'STA-1648', 'STA-1650', 'CLOSURE_STALLED')):
        raise RuntimeError(f'Clock routing-role repair failed: {iteration}/repair.log')
    finish(root, pdk, iteration)
