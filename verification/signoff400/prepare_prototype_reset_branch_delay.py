"""Plan two characterized delay stages on the measured residual reset branch."""
import argparse
import json
from pathlib import Path
from common_v3 import save, sha, verify


def run(route, inventory, electrical, endpoints, output):
    receipt = inventory/'assessment.json'
    graph = inventory/'routed.json'
    inv = json.loads(receipt.read_text()); verify(inv['artifacts'])
    r = json.loads((route/'assessment.json').read_text()); verify(r['artifacts'])
    e = json.loads((electrical/'assessment.json').read_text()); verify(e['artifacts'])
    if not e['electrical_limits_passed'] or not e['all_five_corners_reviewed']:
        raise ValueError('all five electrical screens must pass')
    cells = {n.lstrip('\\'): c for n,c in json.loads(graph.read_text())['modules']['IntegerPLL_ProgrammedCore']['cells'].items()}
    driver = 'prototype_observed_load_followup_branch_0_16'
    if cells[driver]['type'] != 'sky130_fd_sc_hs__clkbuf_2':
        raise ValueError('measured branch master differs')
    bit = cells[driver]['connections']['X']
    sinks = {(n,p) for n,c in cells.items() for p,b in c['connections'].items()
             if b == bit and c['port_directions'].get(p) == 'input'}
    expected = {('$auto$ff.cc:337:slice$'+n,'RESET_B') for n in ('17237','17223','17225','17233')}
    if sinks != expected:
        raise ValueError('branch must exclusively drive the four measured reset endpoints')
    inputs = [route/'assessment.json', receipt, graph, electrical/'assessment.json',
              Path(__file__).resolve(), Path(__file__).with_name('common_v3.py')]
    corners = set()
    for directory in endpoints:
        report = directory/'assessment.json'; paths = directory/'paths.json'; log = directory/'inventory.log'
        a = json.loads(report.read_text()); verify(a['input_sha256']); verify(a['artifacts'])
        phase = next(Path(n) for n in a['input_sha256'] if n.endswith('/assessment.json') and 'enabled_hold' in n)
        ph = json.loads(phase.read_text())
        corner = ph['native_model_corner']
        if corner in corners or a['interstage_hold_failures'] or a['explicit_interstage_checks'] != 13:
            raise ValueError('complete distinct interstage review required')
        corners.add(corner)
        failures = json.loads(paths.read_text())['failing_endpoint_paths']
        remaining = [f for f in failures if f['endpoint'] != '$auto$ff.cc:337:slice$17893']
        want = expected if corner in ('ff','fs') else set()
        if {(f['endpoint'],'RESET_B') for f in remaining} != want:
            raise ValueError('unreviewed endpoint failure')
        for f in remaining:
            blocks = [b for b in log.read_text().split('Startpoint: ')[1:]
                      if b.startswith(f['startpoint']+'\n') and 'Endpoint: '+f['endpoint']+'\n' in b]
            if (f['kind'] != 'min' or f['startpoint'] != '$auto$ff.cc:337:slice$17896'
                    or not blocks or not all('removal check' in b and driver+'/X' in b and
                        f['endpoint']+'/RESET_B' in b for b in blocks)):
                raise ValueError('native path does not bind the measured branch and reset pin')
        inputs += [report, paths, log, phase]
    if corners != {'tt','ff','ss','sf','fs'}:
        raise ValueError('all five corners required')
    pins = {str(p):sha(p) for p in inputs}; verify(pins)
    output.mkdir(parents=True,exist_ok=False)
    save(output/'plan.json',dict(input_sha256=pins,route_sha256=sha(route/'route.odb'),
        targets=[],branches=[],short_data_targets=[dict(capture_cell=driver,
        capture_master='sky130_fd_sc_hs__clkbuf_2',capture_pin='A',buffers=2)],
        all_first_stage_synchronizer_masters_preserved=True,
        RTL_and_timing_exceptions_unchanged=True,release_ready=False))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('route','inventory','electrical','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--endpoints',type=Path,action='append',required=True)
    a=p.parse_args();run(a.route.resolve(),a.inventory.resolve(),a.electrical.resolve(),
                        [v.resolve() for v in a.endpoints],a.output.resolve())
