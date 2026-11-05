"""Attach only independently reported antenna pins to a same-route ECO plan."""
import argparse
import json
from pathlib import Path
import sys
from common_v3 import ROOT, save, sha, verify
sys.path.insert(0, str(ROOT/'verification/prototype400'))
from repair_measured_antennas_v2 import violation_targets


def run(plan, route, output):
    pp = plan/'plan.json'; p = json.loads(pp.read_text()); verify(p['input_sha256'])
    rr = route/'assessment.json'; r = json.loads(rr.read_text())
    pr = route/'signoff/assessment.json'; a = json.loads(pr.read_text())
    report = route/'signoff/antenna.rpt'
    verify(r['input_sha256']); verify(r['artifacts']); verify(a['sha256'])
    if (p['route_sha256'] != sha(route/'route.odb')
            or a['sha256'].get(str(route/'route.odb')) != sha(route/'route.odb')
            or a['sha256'].get(str(report)) != sha(report)
            or a['magic_drc_rectangles'] or a['power_pins_total'] <= 0
            or a['power_pins_total'] != a['power_pins_connected']):
        raise ValueError('same-route DRC/PG checked antenna evidence required')
    targets = violation_targets(report.read_text())
    if (not targets or len(targets) != a['antenna_pin_violations']
            or len({n for n, _, _ in targets}) != a['antenna_net_violations']):
        raise ValueError('complete nonempty native antenna target coverage required')
    if p.get('antenna_targets'):
        raise ValueError('existing diode proposal must remain immutable')
    inputs = dict(p['input_sha256'])
    inputs.update({str(f):sha(f) for f in (pp, rr, pr, report, Path(__file__).resolve(),
                  ROOT/'verification/prototype400/repair_measured_antennas_v2.py')})
    verify(inputs); output.mkdir(parents=True, exist_ok=False)
    p.update(input_sha256=inputs, antenna_targets=targets,
             measured_antenna_receiver_pins=len(targets),
             independent_postroute_antenna_recheck_required=True, antenna_closure_claimed=False)
    save(output/'plan.json', p)
    print(json.dumps(dict(measured_antenna_receiver_pins=len(targets))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan','route','output'): parser.add_argument('--'+name, required=True, type=Path)
    a = parser.parse_args(); run(a.plan.resolve(), a.route.resolve(), a.output.resolve())
