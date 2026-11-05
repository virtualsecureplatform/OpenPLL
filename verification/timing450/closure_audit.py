#!/usr/bin/env python3
"""Fail closed on incomplete supplied-model timing or stale physical evidence."""
import json
from pathlib import Path
import re

from closure import CORNERS, REPO, sha
from run import run

MODES = (100, 250, 300, 400, 450)
GROUPS = ('PLLOUT', 'REFCLK', 'FINECLK', 'asynchronous', 'path delay', 'EVENT_BBPD[0]', 'EVENT_BBPD[1]')


def valid_matrix(result):
    if set(result.get('models', {})) != {'ss', 'tt', 'ff'}:
        return False
    if set(result.get('gates', {})) != {c.replace('_', '/') for c in CORNERS}:
        return False
    for corner in CORNERS:
        cell, rc = corner.split('_')
        rows = result.get('timing_ns', {}).get(cell, {}).get(rc, {})
        if set(rows) != {f'{kind}/{group}' for kind in ('max', 'min') for group in GROUPS}:
            return False
        if not all(value >= (.10 if key.startswith('max/') else .05) for key, value in rows.items()):
            return False
    return all(result['gates'].values()) and result.get('diagnostic_timing_pass') is True


def verify_hashes(result):
    for path, digest in result['sha256'].items():
        file = Path(path) if Path(path).is_absolute() else REPO / path
        if not file.exists() or sha(file) != digest:
            raise RuntimeError(f'Stale evidence: {file}')
    for path, digest in result.get('model_sha256', {}).items():
        if sha(Path(path)) != digest:
            raise RuntimeError(f'Stale model: {path}')


def annotation_failures(module, text, views=None):
    cells = {name.lstrip('\\'): cell for name, cell in module['cells'].items()}
    used = {bit for cell in cells.values() for pin, bits in cell['connections'].items()
            if cell['port_directions'].get(pin) == 'input' for bit in bits}
    used.update(bit for port in module['ports'].values() if port['direction'] == 'output' for bit in port['bits'])
    section = text.split('unannotated drivers.', 1)
    if len(section) != 2:
        # A completely annotated design is reported without an unannotated list.
        return [] if 'Found 0 unannotated drivers' in text else ['missing annotation report']
    section = section[1].split('SETUP_AND_RECOVERY_SCREEN', 1)[0]
    failures = []
    for line in section.splitlines():
        pin = line.strip()
        if not pin or '/' not in pin:
            continue
        name, terminal = pin.rsplit('/', 1)
        cell = cells.get(name)
        if cell is not None and '__conb_' in cell['type']:
            # Both tie outputs are static, including an omitted unused output.
            continue
        if cell is not None and terminal not in cell['connections']:
            direction = cell.get('port_directions', {}).get(terminal)
            if direction is None and views:
                direction = views.get(cell['type'], {}).get('ports', {}).get(terminal, {}).get('direction')
            if direction == 'output':
                # write_verilog omits open dummy outputs. Check the Liberty
                # view's direction before treating an absent connection as open.
                continue
        if cell is None or terminal not in cell['connections']:
            failures.append(pin)
        elif any(bit in used for bit in cell['connections'][terminal]):
            failures.append(pin)
        # Unconsumed CTS dummy outputs are allowed; their clock inputs are timed.
    return failures


def receiver_link_failures(mapped, physical):
    """Check topology separately: equivalence permits delays on CDC links."""
    cells = {name.lstrip('\\'): cell for name, cell in physical['cells'].items()}
    async_bits = {bit for net in mapped['netnames'].values()
                  if 'ASYNC_REG' in net.get('attributes', {}) for bit in net['bits']}
    drivers = {cell['connections']['Q'][0]: name.lstrip('\\')
               for name, cell in mapped['cells'].items() if 'Q' in cell['connections']}
    failures = []
    for name, cell in mapped['cells'].items():
        data = cell['connections'].get('D', [None])[0]
        output = cell['connections'].get('Q', [None])[0]
        if data not in async_bits or output not in async_bits:
            continue
        original_source = mapped['cells'].get(drivers.get(data), {})
        if cell['connections'].get('CLK') != original_source.get('connections', {}).get('CLK'):
            # An ASYNC_REG output can itself cross into a different domain.
            continue
        receiver = cells.get(name.lstrip('\\'), {})
        source = cells.get(drivers.get(data), {})
        actual_data = receiver.get('connections', {}).get('D')
        actual_output = source.get('connections', {}).get('Q')
        if not actual_data or not actual_output or actual_data != actual_output:
            failures.append(name.lstrip('\\') + '/D')
    return failures


def clock_role_failures(module, rows):
    expected = {name.lstrip('\\') + '_out' for name in module['cells']
                if re.fullmatch(r'closure_(?:cdc|launch)_clock_\d+', name.lstrip('\\'))}
    roles = dict(line.split() for line in rows.splitlines() if line.strip())
    return sorted(name for name in expected if roles.get(name) != 'CLOCK')


def audit(root):
    physical = json.loads((root / 'physical_assessment.json').read_text())
    gate = json.loads((root / 'gate_assessment.json').read_text())
    signoff = json.loads((root / 'signoff/assessment.json').read_text())
    for result in (physical, gate, signoff):
        verify_hashes(result)
    views = json.loads((root / 'physical_gate_raw.json').read_text())['modules']
    module = views['IntegerPLL_AcquiringCore']
    clock_recipe = root / 'clock_roles.tcl'
    clock_rows = root / 'clock_roles.txt'
    clock_recipe.write_text(f'''read_db {root}/route.odb
set output [open {clock_rows} w]
foreach inst [[ord::get_db_block] getInsts] {{
    if {{![regexp {{^closure_(cdc|launch)_clock_[0-9]+$}} [$inst getName]]}} {{continue}}
    set net [[$inst findITerm X] getNet]
    puts $output "[$net getName] [$net getSigType]"
}}
close $output
exit
''')
    run('openroad', ['-exit', clock_recipe], root / 'clock_roles.log')
    clock_roles = clock_role_failures(module, clock_rows.read_text())
    mapped = json.loads((root / 'mapped.json').read_text())['modules']['IntegerPLL_AcquiringCore']
    receiver_links = receiver_link_failures(mapped, module)
    matrices = {}
    annotations = {}
    for mode in MODES:
        result = json.loads((root / f'reports_{mode}/assessment.json').read_text())
        verify_hashes(result)
        if result['mode_mhz'] != mode:
            raise RuntimeError(f'Wrong mode in reports_{mode}')
        matrices[str(mode)] = valid_matrix(result)
        annotations[str(mode)] = {log.name: annotation_failures(module, log.read_text(), views)
                                  for log in (root / f'reports_{mode}').glob('*_timing.log')}
    passed = (all(matrices.values()) and not receiver_links and not clock_roles
              and not any(errors for logs in annotations.values() for errors in logs.values())
              and physical['functional_equivalence_pass'] and gate['functional_pass']
              and signoff['magic_drc_rectangles'] == 0 and signoff['lvs_unique_match']
              and signoff['power_pins_total'] == signoff['power_pins_connected']
              and signoff['power_pins_total'] > 0 and not (root / 'route.drc').read_text().strip())
    result = {'supplied_model_closure_pass': passed, 'selected': False, 'release_qualified': False,
              'modes': matrices, 'unannotated_functional_pins': annotations,
              'changed_direct_receiver_links': receiver_links,
              'incorrect_local_clock_net_roles': clock_roles,
              'antenna_net_violations': signoff['antenna_net_violations'],
              'antenna_pin_violations': signoff['antenna_pin_violations'],
              'sha256': {str(p): sha(p) for p in [root / 'route.odb', root / 'route.v',
                         root / 'mapped.json', root / 'physical_gate_raw.json', clock_recipe, clock_rows, root / 'clock_roles.log',
                         root / 'physical_assessment.json', root / 'gate_assessment.json',
                         root / 'signoff/assessment.json', *root.glob('reports_*/assessment.json'), Path(__file__)]},
              'limitations': ['Supplied models only; missing PVT models, antenna, full KLayout/density/EM/IR and whole-PLL release gates remain']}
    (root / 'closure_assessment.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'supplied_model_closure_pass': passed, 'modes': matrices,
                      'unannotated_functional_pin_count': sum(len(errors) for logs in annotations.values() for errors in logs.values())}))
    return passed


if __name__ == '__main__':
    raise SystemExit(0 if audit(REPO / 'build/timing450/hs') else 1)
