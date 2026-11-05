"""Merge measured ordinary setup/hold repairs into a same-route electrical plan.

The output is an ECO proposal, never timing qualification. First-stage masters
and timing exceptions remain unchanged; all repairs require fresh routed checks.
"""
import argparse
import json
from pathlib import Path
import re
from common_v3 import save, sha, verify


def data_path(block):
    endpoint = re.search(r'^Endpoint: (\S+)', block, re.M)
    kind = re.search(r'^Path Type: (min|max)', block, re.M)
    slack = re.search(r'([-+0-9.eE]+)\s+slack \(VIOLATED\)', block)
    if not endpoint or not kind or not slack or 'data arrival time' not in block:
        raise ValueError('complete negative native timing path required')
    arrival = block.split('data arrival time', 1)[0]
    rows = re.findall(r'^\s*([-+0-9.eE]+)\s+[-+0-9.eE]+\s+[\^v]\s+(\S+)/(\w+)\s+\((\w+)\)', arrival, re.M)
    if not rows or rows[-1][1:3] != (endpoint[1], 'D') or float(slack[1]) >= 0:
        raise ValueError('ordinary D-pin path required; reset/clock repairs need separate review')
    return endpoint[1], kind[1], float(slack[1]), rows


def next_strength(master, available):
    family, strength = master.rsplit('_', 1)
    choices = [(int(m.rsplit('_', 1)[1]), m) for m in available
               if m.rsplit('_', 1)[0] == family and int(m.rsplit('_', 1)[1]) > int(strength)]
    return min(choices)[1] if choices else None


def run(plan, inventory, obligations, views, endpoints, output):
    pp = plan/'plan.json'; proposal = json.loads(pp.read_text()); verify(proposal['input_sha256'])
    ir = inventory/'assessment.json'; inv = json.loads(ir.read_text())
    authority = obligations/'assessment.json'; ob = json.loads(authority.read_text())
    vr = views/'assessment.json'; native = json.loads(vr.read_text())
    for record in (inv, ob, native):
        verify(record['input_sha256']); verify(record['artifacts'])
    graph = inventory/'routed.json'; chains_file = obligations/'obligations.json'
    if ob['input_sha256'].get(str(graph)) != sha(graph):
        raise ValueError('same routed obligations required')
    route_receipts = [Path(n) for n in inv['input_sha256'] if n.endswith('/assessment.json')
                      and json.loads(Path(n).read_text()).get('digital_routing_completed') is True]
    if len(route_receipts) != 1 or proposal['route_sha256'] != sha(route_receipts[0].parent/'route.odb'):
        raise ValueError('same-route electrical plan required')
    module = json.loads(graph.read_text())['modules']['IntegerPLL_ProgrammedCore']
    cells = {n.lstrip('\\'): c for n, c in module['cells'].items()}
    chains = json.loads(chains_file.read_text())['synchronizers']
    protected = {c['stages'][0]['routed_cell'].lstrip('\\') for c in chains}
    intentional = [c['stages'][0]['routed_cell'].lstrip('\\') for c in chains
                   if c['id'] == 'gen_feedback_tracking.release_pipe']
    if len(chains) != 13 or len(intentional) != 1:
        raise ValueError('reviewed synchronizer inventory required')
    libraries = [views/f'{c}_{edge}.lib' for c in ('tt','ff','ss','sf','fs') for edge in ('early','late')]
    available = set.intersection(*(set(re.findall(r'cell \(([^)]+)\)', p.read_text())) for p in libraries))
    targets = {t['capture_cell']: t for t in proposal['targets']}
    holds = {}; skipped = []; corners = set(); periods = set()
    inputs = {str(p): sha(p) for p in (pp, ir, authority, vr, graph, chains_file, *libraries, Path(__file__).resolve())}
    for folder in endpoints:
        receipt = folder/'assessment.json'; a = json.loads(receipt.read_text())
        verify(a['input_sha256']); verify(a['artifacts'])
        if a['input_sha256'].get(str(authority)) != sha(authority):
            raise ValueError('endpoint obligations differ')
        phases = [(Path(n), json.loads(Path(n).read_text())) for n in a['input_sha256'] if n.endswith('/assessment.json')]
        phases = [(p, r) for p, r in phases if r.get('conditional_experiment_only') is True]
        if len(phases) != 1 or not phases[0][1].get('physical_launch_clock_latency_retained'):
            raise ValueError('checked enabled-phase timing required')
        phase, r = phases[0]; corners.add(r['native_model_corner']); periods.add(r['source_clock_period_ns'])
        log = folder/'inventory.log'; text = log.read_text()
        section = text.split('ALL_FAILING_ENDPOINTS_BEGIN', 1)[1].split('ALL_FAILING_ENDPOINTS_END', 1)[0]
        for block in section.split('Startpoint: ')[1:]:
            endpoint, kind, slack, rows = data_path(block)
            if kind == 'min':
                if endpoint == intentional[0]:
                    skipped.append(dict(endpoint=endpoint, reason='reviewed_first_stage_aperture', slack_ns=slack)); continue
                if endpoint in protected or slack < -.06:
                    raise ValueError('hold repair exceeds bounded ordinary-data scope')
                holds[endpoint] = dict(capture_cell=endpoint, capture_master=cells[endpoint]['type'],
                                       capture_pin='D', buffers=2, observed_slack_ns=min(slack, holds.get(endpoint, {}).get('observed_slack_ns', 0)))
            else:
                for delay, name, pin, master in rows[:-1]:
                    if cells[name]['type'] != master:
                        raise ValueError('native path master differs from routed graph')
                    if cells[name]['port_directions'].get(pin) != 'output' or name in protected or float(delay) < .1:
                        continue
                    replacement = next_strength(master, available)
                    if replacement:
                        targets[name] = dict(action='resize', capture_cell=name, capture_master=master, replacement_master=replacement)
        inputs.update({str(p):sha(p) for p in (receipt, phase, log)})
    if corners != {'tt','ff','ss','sf','fs'} or len(endpoints) != 5 or len(periods) != 1:
        raise ValueError('five corners at one checked source period required')
    if protected & targets.keys() or protected & holds.keys() or proposal.get('short_data_targets'):
        raise ValueError('protected or duplicate existing data repairs')
    verify(inputs); output.mkdir(parents=True, exist_ok=False)
    proposal.update(input_sha256=inputs, targets=list(targets.values()), short_data_targets=list(holds.values()),
                    reviewed_aperture_paths=skipped, timing_repair_source_period_ns=periods.pop(),
                    independent_postroute_timing_recheck_required=True, timing_closure_claimed=False)
    save(output/'plan.json', proposal)
    print(json.dumps(dict(resizes=len(targets), ordinary_hold_targets=len(holds))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan','inventory','obligations','views','output'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--endpoints', required=True, action='append', type=Path)
    a = parser.parse_args()
    run(*(getattr(a, n).resolve() for n in ('plan','inventory','obligations','views')),
        [p.resolve() for p in a.endpoints], a.output.resolve())
