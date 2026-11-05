"""Read-only exhaustive failing-endpoint and explicit CDC interstage timing review."""
import argparse
import json
import os
from pathlib import Path
import re
import time

from common_v3 import save, sha, verify
from compiled_charge import execute
from resources import lease
from screen_prototype_decision_hold_phase_v3 import OPENROAD


def paths(text):
    result = []
    for block in text.split('Startpoint: ')[1:]:
        endpoint = re.search(r'^Endpoint: (\S+)', block, re.M)
        kind = re.search(r'^Path Type: (min|max)', block, re.M)
        slack = re.search(r'([-+0-9.eE]+)\s+slack \((?:VIOLATED|MET)\)', block)
        if not endpoint or not kind or not slack:
            raise ValueError('incomplete reported timing path')
        result.append(dict(startpoint=block.split()[0], endpoint=endpoint[1],
                           kind=kind[1], slack_ns=float(slack[1])))
    return result


def run(baseline, obligations, output):
    receipts = [baseline/'assessment.json', obligations/'assessment.json']
    records = [json.loads(p.read_text()) for p in receipts]
    for record in records:
        verify(record['artifacts'])
    original = baseline/'screen.tcl'
    if records[0]['input_sha256'].get(str(original)) != sha(original):
        raise ValueError('baseline timing script changed')
    inventory = obligations/'obligations.json'
    chains = json.loads(inventory.read_text())['synchronizers']
    if len(chains) != 13 or len({c['id'] for c in chains}) != 13:
        raise ValueError('expected thirteen unique synchronizers')
    queries = ['puts "ALL_FAILING_ENDPOINTS_BEGIN"',
               'report_checks -path_delay min_max -group_path_count 100000 -endpoint_path_count 1 -slack_max 0 -sort_by_slack -digits 6',
               'puts "ALL_FAILING_ENDPOINTS_END"']
    for index, chain in enumerate(chains):
        stages = chain['stages']
        if len(stages) != 2:
            raise ValueError('two-stage synchronizer required')
        source = stages[0]['routed_cell'].lstrip('\\')+'/Q'
        target = stages[1]['routed_cell'].lstrip('\\')+'/D'
        queries += [f'set launch [get_pins {{{source}}}]',
                    f'set capture [get_pins {{{target}}}]',
                    'if {[llength $launch] != 1 || [llength $capture] != 1} {error "interstage pin missing"}',
                    f'puts "INTERSTAGE_{index}_BEGIN"',
                    'report_checks -from $launch -to $capture -path_delay min_max -group_path_count 2 -endpoint_path_count 1 -digits 6',
                    f'puts "INTERSTAGE_{index}_END"']
    text = original.read_text()
    if text.count('\nexit\n') != 1:
        raise ValueError('unique exit required')
    output.mkdir(parents=True, exist_ok=False)
    script = output/'inventory.tcl'
    script.write_text(text.replace('\nexit\n', '\n'+'\n'.join(queries)+'\nexit\n'))
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    with lease(1, 4, deadline):
        execute([OPENROAD, '-exit', script], output/'inventory.log', deadline, 4)
    log = (output/'inventory.log').read_text()
    if re.search(r'\[ERROR|Error:|invalid command name|STA-(1648|1650)', log):
        raise ValueError('native timing error')
    def section(marker):
        return log.split(marker+'_BEGIN', 1)[1].split(marker+'_END', 1)[0]
    failures = paths(section('ALL_FAILING_ENDPOINTS'))
    interstage = []
    for index, chain in enumerate(chains):
        checked = paths(section(f'INTERSTAGE_{index}'))
        if sorted(p['kind'] for p in checked) != ['max', 'min']:
            raise ValueError('interstage min/max coverage missing')
        interstage.append(dict(id=chain['id'], paths=checked))
    report = output/'paths.json'
    save(report, dict(failing_endpoint_paths=failures, interstage=interstage))
    inputs = [*receipts, original, inventory, Path(__file__).resolve(), Path(OPENROAD)]
    save(output/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
         artifacts={str(p): sha(p) for p in (script, output/'inventory.log', report)},
         failing_endpoint_paths=len(failures), explicit_interstage_checks=len(interstage),
         interstage_hold_failures=[c['id'] for c in interstage if any(p['kind']=='min' and p['slack_ns']<0 for p in c['paths'])],
         conditional_enabled_mode_only=True, routed_database_modified=False,
         digital_timing_qualified=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'obligations', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.baseline.resolve(), args.obligations.resolve(), args.output.resolve())
