"""Measure explicit worst electrical margins in the selected routed timing views.

This validates constrained slew/capacitance screening, not timing-model accuracy,
startup frequency coverage, unconstrained pins, or the complete physical gate.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import time

from common_v3 import save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute

OPENROAD = '/nix/store/qqz49dx8dpx4q9i5wriif091n7iaa0ld-openroad-2026-02-17/bin/openroad'
BEGIN = 'OPENPLL_ELECTRICAL_MARGIN_BEGIN'
END = 'OPENPLL_ELECTRICAL_MARGIN_END'
NUMBER = r'([-+0-9.eE]+)'


def margins(text):
    if text.splitlines().count(BEGIN) != 1 or text.splitlines().count(END) != 1:
        raise ValueError('one complete explicit electrical report required')
    if re.search(r'(?im)^.*(?:error|unrecognized|unknown command).*$', text):
        raise ValueError('native report contains an error')
    body = text.split(BEGIN+'\n', 1)[1].split(END, 1)[0]
    result = {}
    for heading, measurement, unit in [('max slew', 'slew', 'ns'), ('max capacitance', 'capacitance', 'pF')]:
        if body.splitlines().count(heading) != 1:
            raise ValueError('missing or duplicated electrical constraint section')
        pattern = (re.escape(heading)+r'\n\nPin ([^\n]+)\n'+re.escape(heading)+r' +'+NUMBER+
                   r'\n'+measurement+r' +'+NUMBER+r'\n-+\nSlack +'+NUMBER+r' \((MET|VIOLATED)\)')
        rows = re.findall(pattern, body)
        if len(rows) != 1:
            raise ValueError('explicit worst constrained pin and margin required')
        pin, limit, value, slack, status = rows[0]
        limit, value, slack = map(float, (limit, value, slack))
        if not all(math.isfinite(v) for v in (limit, value, slack)) or limit <= 0 or value < 0:
            raise ValueError('invalid electrical values')
        # STA stores these values in single precision; printed operands need not
        # subtract to its separately rounded printed slack. Allow four float32 ULPs.
        tolerance = max(3e-9, 4*2**-23*max(abs(limit), abs(value), abs(slack)))
        if abs((limit-value)-slack) > tolerance or (slack >= 0) != (status == 'MET'):
            raise ValueError('inconsistent electrical margin')
        result[measurement] = dict(worst_pin=pin, limit=limit, measured=value, slack=slack,
                                   unit=unit, subtraction_tolerance=tolerance, passed=status == 'MET')
    return result


def run(timing, image, output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {27})
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    save(output/'status.json', dict(state='measuring_explicit_electrical_margins', release_ready=False))
    try:
        pins = {str(p): sha(p) for p in [Path(OPENROAD), image, Path(__file__).resolve(),
                 Path(__file__).with_name('resources.py'), Path(__file__).with_name('compiled_charge_v2.py'),
                 Path(__file__).with_name('common_v3.py')]}
        results = {}; artifacts = {}; route_digests = set()
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+1800
        for directory in timing:
            receipt = directory/'assessment.json'; a = json.loads(receipt.read_text())
            verify(a['input_sha256']); verify(a['artifacts'])
            corner = a['native_model_corner']
            if corner in results or corner not in ('tt', 'ff', 'ss', 'sf', 'fs'):
                raise ValueError('distinct supported corner required')
            if a.get('clock_capacity_mhz') != 402.1 or not a.get('minmax_wire_RC_used'):
                raise ValueError('same 402.1 MHz min/max routed screening protocol required')
            route = {p:d for p,d in a['input_sha256'].items() if p.endswith('/route.odb')}
            if len(route) != 1: raise ValueError('one pinned routed database required')
            route_digests.add(next(iter(route.values())))
            old = directory/'fixed_divide16/screen.tcl'
            if a['artifacts'].get(str(old)) != sha(old): raise ValueError('unpinned original native script')
            prefix = old.read_text().split('report_parasitic_annotation', 1)
            if len(prefix) != 2 or 'report_check_types -max_slew -max_capacitance' not in prefix[1]:
                raise ValueError('explicit original electrical screening command required')
            pins.update({str(p): sha(p) for p in (receipt, old)})
            pins.update(a['input_sha256'])
            script = output/(corner+'.tcl')
            script.write_text(prefix[0]+f'puts {BEGIN}\nreport_check_types -max_slew -max_capacitance -verbose -digits 9 -no_line_splits\nputs {END}\nexit\n')
            pins[str(script)] = sha(script)
            log = output/(corner+'.log')
            with lease(1, 4, deadline):
                execute([OPENROAD, '-no_init', '-exit', script], log, deadline, 4)
            results[corner] = margins(log.read_text())
            artifacts[str(log)] = sha(log)
        if set(results) != {'tt', 'ff', 'ss', 'sf', 'fs'} or len(route_digests) != 1:
            raise ValueError('all five corners on the same routed database required')
        verify(pins); verify(artifacts)
        save(output/'assessment.json', dict(input_sha256=pins, artifacts=artifacts, results=results,
            explicit_worst_constrained_pin_report_complete=True,
            all_five_corner_constrained_electrical_margins_pass=all(v['passed'] for r in results.values() for v in r.values()),
            unconstrained_pin_coverage_qualified=False, native_timing_views_qualified=False,
            startup_frequency_range_qualified=False, physical_integrity_qualified=False, release_ready=False))
        save(output/'status.json', dict(state='explicit_electrical_margin_screen_complete', release_ready=False))
        print(json.dumps(results))
    except BaseException as error:
        save(output/'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--timing', type=Path, action='append', required=True)
    p.add_argument('--image', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run([p.resolve() for p in a.timing], a.image.resolve(), a.output.resolve())
