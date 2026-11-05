#!/usr/bin/env python3
"""Screen candidate-owned static power/IR/current with explicit assumptions."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re

from run import REPO, TOOLS, run

MODES = (100, 250, 300, 400, 450)
NETS = ('VDD', 'VSS')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resistance_models(text):
    if 'Resistances are in milliohms per square' not in text:
        raise RuntimeError('Unrecognized Magic resistance units')
    models = {}
    for corner, marker in [('nom', 'variants (),(orig),(si)'),
                           ('max', 'variants (hrhc),(hrlc)'),
                           ('min', 'variants (lrhc),(lrlc)')]:
        blocks = text.split(marker + '\n')
        if len(blocks) < 2:
            raise RuntimeError(f'Missing Magic resistance variant: {corner}')
        # Later variants contain capacitance, not this resistance table.
        matches = []
        for block in blocks[1:]:
            block = block.split('\nvariants ')[0]
            metal = {n: float(v) / 1000 for n, v in re.findall(
                r'^ resist \(all(m[1-5])\)/metal\d\s+(\d+)\s*$', block, re.M)}
            via = {n: float(v) / 1000 for n, v in re.findall(
                r'^ contact (mcon|m2c|m3c|via3|via4)\s+(\d+)\s*$', block, re.M)}
            if metal or via:
                matches.append((metal, via))
        if len(matches) != 1 or set(matches[0][0]) != {'m1', 'm2', 'm3', 'm4', 'm5'} or \
                set(matches[0][1]) != {'mcon', 'm2c', 'm3c', 'via3', 'via4'}:
            raise RuntimeError(f'Incomplete/ambiguous resistance table: {corner}')
        metal, via = matches[0]
        models[corner] = {
            'sheet_ohms': {'met' + k[1:]: v for k, v in metal.items()},
            'via_ohms': {dict(mcon='mcon', m2c='via', m3c='via2', via3='via3', via4='via4')[k]: v
                         for k, v in via.items()},
        }
    return models


def numeric(value):
    value = float(value)
    if not math.isfinite(value):
        raise RuntimeError('Nonfinite power-grid result')
    return value


def clock_periods(log, mode):
    rows = re.findall(r'^POWER_CLOCK_PERIOD (\S+) (\S+)$', log, re.M)
    periods = {name: numeric(value) for name, value in rows}
    expected = {'REFCLK': 40., 'PLLOUT': 1000. / mode, 'FINECLK': 40.,
                'EVENT_BBPD[0]': 40., 'EVENT_BBPD[1]': 40.}
    if len(rows) != len(expected) or set(periods) != set(expected) or any(
            value <= 0 or not math.isclose(value, expected[name], rel_tol=1e-5)
            for name, value in periods.items()):
        raise RuntimeError('Unresolved or incorrect power-analysis clock periods')
    return periods


def summarize(log, directory, supply):
    if re.search(r'\b(?:nan|inf)\b', log, re.I) or any(
            e in log for e in ('Error:', '[ERROR', 'zero resistance', 'STA-1648', 'STA-1650')):
        raise RuntimeError('Power, resistance or extracted annotation failed')
    total = re.findall(r'^Total\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+100', log, re.M)
    if len(total) != 1:
        raise RuntimeError('Missing total power report')
    power = dict(zip(('internal_w', 'switching_w', 'leakage_w', 'total_w'), map(numeric, total[0])))
    if any(v < 0 for v in power.values()) or not math.isclose(
            sum(power[k] for k in ('internal_w', 'switching_w', 'leakage_w')),
            power['total_w'], rel_tol=1e-6):
        raise RuntimeError('Invalid power components')
    rails, results = {}, {}
    for net in NETS:
        blocks = re.findall(r'########## IR report #+\n(.*?)(?=#+\n)', log, re.S)
        blocks = [b for b in blocks if re.search(r'^Net\s+: ' + net + r'$', b, re.M)]
        if len(blocks) != 1 or f'All shapes on net {net} are connected.' not in log:
            raise RuntimeError(f'Missing connected power-grid solve: {net}')
        drop = re.search(r'^Worstcase IR drop:\s+(\S+) V$', blocks[0], re.M)
        if not drop or numeric(drop[1]) < 0:
            raise RuntimeError(f'Invalid voltage drop: {net}')
        with (directory / f'{net}.em.csv').open() as stream:
            currents = [abs(numeric(row['Current'])) for row in csv.DictReader(stream)]
        with (directory / f'{net}.voltage.csv').open() as stream:
            voltages = {}
            for row in csv.DictReader(stream):
                value = numeric(row['Voltage'])
                if value < -1e-6 or value > supply + 1e-6:
                    raise RuntimeError(f'Invalid rail voltage: {net}')
                name = row['Instance']
                if name in voltages:
                    raise RuntimeError(f'Duplicate per-instance voltage: {net}/{name}')
                voltages[name] = value
        if not currents or not voltages:
            raise RuntimeError(f'Empty native current or voltage report: {net}')
        rails[net] = voltages
        results[net] = {'worst_drop_v': numeric(drop[1]), 'segments': len(currents),
                        'maximum_segment_current_a': max(currents),
                        'voltage_instances': len(voltages)}
    if set(rails['VDD']) != set(rails['VSS']):
        raise RuntimeError('Rail instance populations do not match')
    effective = {name: value - rails['VSS'][name] for name, value in rails['VDD'].items()}
    if min(effective.values()) <= 0:
        raise RuntimeError('Nonpositive effective instance supply')
    worst = min(effective, key=effective.get)
    return {'power': power, 'rails': results, 'minimum_effective_instance_supply_v': effective[worst],
            'worst_effective_supply_instance': worst}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--magic-tech', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--modes', type=int, choices=MODES, nargs='+', default=list(MODES))
    args = parser.parse_args()
    root, output = args.candidate.resolve(), args.output.resolve()
    if output == root or root in output.parents:
        parser.error('Output must be separate from the accepted candidate')
    modes = sorted(set(args.modes))
    tech = args.magic_tech.resolve()
    models = resistance_models(tech.read_text())
    inputs = {tech: sha(tech), Path(__file__).resolve(): sha(Path(__file__)),
              Path(__file__).with_name('run.py'): sha(Path(__file__).with_name('run.py')),
              Path(TOOLS['openroad']): sha(Path(TOOLS['openroad']))}
    for mode in modes:
        path = root / f'reports_{mode}/assessment.json'
        baseline = json.loads(path.read_text())
        inputs[path] = sha(path)
        for section in ('sha256', 'model_sha256'):
            for name, digest in baseline[section].items():
                path = Path(name)
                if not path.is_absolute():
                    path = root.parents[2] / path
                if sha(path) != digest:
                    raise RuntimeError(f'Stale baseline input: {path}')
                inputs[path] = digest
    output.mkdir(parents=True, exist_ok=True)
    receipt = output / 'assessment.json'
    receipt.unlink(missing_ok=True)
    results, artifacts = {}, []
    for mode in modes:
        for recipe in sorted((root / f'reports_{mode}').glob('*_timing.tcl')):
            name = recipe.stem.removesuffix('_timing')
            process, rc = name.split('_')
            if process not in ('ss', 'tt', 'ff') or rc not in models:
                raise RuntimeError(f'Unexpected native STA recipe: {recipe}')
            inputs[recipe] = sha(recipe)
            source = recipe.read_text()
            if source.count('\nreport_parasitic_annotation') != 1:
                raise RuntimeError('Unexpected STA recipe format')
            prefix = source.split('\nreport_parasitic_annotation')[0] + '\n'
            for path in re.findall(r'^(?:read_lef|read_liberty|read_db|read_spef|source) (\S+)$', prefix, re.M):
                inputs[Path(path)] = sha(Path(path))
            libpaths = re.findall(r'^read_liberty (\S+)$', prefix, re.M)
            if len(libpaths) != 1:
                raise RuntimeError('Expected one characterized library')
            library = Path(libpaths[0]).read_text()
            voltage = re.search(r'\bnom_voltage\s*:\s*([\d.]+)', library)
            if not voltage or float(voltage[1]) > 1.95 or 'time_unit : "1ns"' not in library:
                raise RuntimeError('Unexpected supply or activity time units')
            supply = float(voltage[1])
            directory = output / f'{mode}_{name}'
            directory.mkdir(exist_ok=True)
            for path in directory.glob('*.csv'):
                path.unlink()
            # Generated periods are lazily initialized by timing propagation.
            # A raw report_power otherwise sees FINECLK's initial zero period.
            timing = directory / 'initialization_timing.rpt'
            text = prefix + f'report_checks -path_delay max -group_path_count 1 > {{{timing}}}\n'
            for clock_name, period in {'REFCLK': 40., 'PLLOUT': 1000. / mode, 'FINECLK': 40.,
                                 'EVENT_BBPD[0]': 40., 'EVENT_BBPD[1]': 40.}.items():
                text += f'set c [get_clocks {{{clock_name}}}]\n'
                text += 'if {[llength $c] != 1} {error "missing power-analysis clock"}\n'
                text += 'set p [expr [[lindex $c 0] period]/[sta::time_ui_sta 1.0]]\n'
                text += f'if {{$p <= 0 || abs($p-{period:.12f}) > {period:.12f}*1e-5}} {{error "incorrect power-analysis clock"}}\n'
                text += f'puts "POWER_CLOCK_PERIOD {clock_name} $p"\n'
            text += f'set_power_activity -global -density {mode / 2000:.9f} -duty 0.5\n'
            text += 'report_units\nset tech [[ord::get_db] getTech]\nset block [ord::get_db_block]\n'
            for layer, ohms in models[rc]['sheet_ohms'].items():
                text += f'set l [$tech findLayer {layer}]\n'
                text += 'set w [expr double([$l getWidth])/[$block getDbUnitsPerMicron]]\n'
                text += f'set_layer_rc -layer {layer} -resistance [expr [sta::resistance_sta_ui {ohms}]/$w]\n'
            for via, ohms in models[rc]['via_ohms'].items():
                text += f'set_layer_rc -via {via} -resistance [sta::resistance_sta_ui {ohms}]\n'
            text += 'report_power -digits 9\n'
            text += f'set_pdnsim_net_voltage -net VDD -voltage {supply}\nset_pdnsim_net_voltage -net VSS -voltage 0\n'
            text += 'set_pdnsim_source_settings -bump_dx 140 -bump_dy 140 -bump_size 70 -bump_interval 1 -external_resistance 0\n'
            for net in NETS:
                text += f'analyze_power_grid -net {net} -source_type BUMPS -enable_em -em_outfile {{{directory}/{net}.em.csv}} -voltage_file {{{directory}/{net}.voltage.csv}} -error_file {{{directory}/{net}.errors.rpt}}\n'
            text += 'exit\n'
            tcl, log = directory / 'run.tcl', directory / 'run.log'
            tcl.write_text(text)
            run('openroad', ['-exit', tcl], log)
            periods = clock_periods(log.read_text(), mode)
            results[f'{mode}_{name}'] = summarize(log.read_text(), directory, supply)
            results[f'{mode}_{name}']['clock_periods_ns'] = periods
            results[f'{mode}_{name}']['supply_v'] = supply
            artifacts += [tcl, log, timing, *sorted(directory.glob('*.csv'))]
            print(json.dumps({'screen': f'{mode}_{name}', **results[f'{mode}_{name}']}), flush=True)
    expected = {f'{m}_{p}_{rc}' for m in modes for p in ('ss', 'tt', 'ff') for rc in models}
    if set(results) != expected:
        raise RuntimeError('Incomplete native power-grid matrix')
    for path, digest in inputs.items():
        if sha(path) != digest:
            raise RuntimeError(f'Input changed during analysis: {path}')
    receipt.write_text(json.dumps({
        'candidate': str(root), 'modes_mhz': modes, 'screens': len(results),
        'static_analysis_complete': True, 'em_signoff_pass': False, 'ir_signoff_pass': False,
        'release_qualified': False, 'selected': False,
        'assumptions': {'nonclock_transitions_per_cycle': .5, 'nonclock_duty': .5,
                        'source_type': 'BUMPS', 'bump_pitch_um': 140, 'bump_size_um': 70,
                        'bump_interval': 1, 'external_resistance_ohms': 0,
                        'grid_resistance': 'Pinned Magic nominal/minimum/maximum extraction variants'},
        'limitations': ['Uniform activity is not measured acquisition/tracking workload',
                        'Bump model is not a qualified package or enclosing supply network',
                        'Static analysis does not cover transient noise or analog macro power',
                        'Segment current is not an EM pass; temperature/lifetime and geometry checks remain',
                        'Missing exact required PVT models and voltage-aware timing remain open'],
        'resistance_models': models, 'results': results,
        'sha256': {str(p): h for p, h in inputs.items()},
        'artifact_sha256': {str(p): sha(p) for p in artifacts},
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
