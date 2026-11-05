"""Compare pre-next-edge clock-train observations with all actual interstage budgets.

Clock-train dependence and continuous/statistical aperture tails remain unqualified.
"""
import argparse
import json
from pathlib import Path
from common_v3 import save, sha, verify
from screen_prototype_decision_hold_phase_v5 import fast_clock_period_ns

def budget_period(phase, record):
    constraints=phase.parent/'enabled_phase.sdc'
    if record['input_sha256'].get(str(constraints)) != sha(constraints):
        raise ValueError('budget clock constraints changed')
    period=fast_clock_period_ns(constraints.read_text())
    if record.get('source_clock_period_ns') != period:
        raise ValueError('budget receipt and source clock period differ')
    return constraints,period


def budget(section, source, destination, slack):
    paths = [p for p in section.split('Startpoint: ')[1:] if 'Path Type: max' in p]
    if len(paths) != 1 or not paths[0].startswith(source+'\n') or 'Endpoint: '+destination+'\n' not in paths[0]:
        raise ValueError('matching routed interstage setup path required')
    rows = [line.split() for line in paths[0].splitlines() if source+'/Q' in line.split()]
    if len(rows) != 1 or float(rows[0][0]) <= 0:
        raise ValueError('one positive source clock-to-Q arc required')
    return float(rows[0][0])+slack

def run(observed, obligations, endpoints, output):
    rr = observed/'assessment.json'; observation = json.loads(rr.read_text()); verify(observation['artifacts'])
    if not observation.get('clock_train_applied') or observation.get('clock_period_ns')!=2 or observation.get('clock_high_ns')!=1:
        raise ValueError('reviewed 500MHz one-ns-high clock-train observations required')
    if observation['unresolved_final_rail_cases']:
        raise ValueError('all sampled final observations must reach a rail')
    authority = obligations/'assessment.json'; o = json.loads(authority.read_text()); verify(o['artifacts'])
    detail = obligations/'obligations.json'; chains = json.loads(detail.read_text())['synchronizers']
    if len(chains) != 13 or len({c['id'] for c in chains}) != 13:
        raise ValueError('thirteen uniquely identified actual chains required')
    pins = {str(p):sha(p) for p in (rr, authority, detail, Path(__file__).resolve())}
    results = []; periods = set()
    for directory in endpoints:
        receipt = directory/'assessment.json'; a = json.loads(receipt.read_text()); verify(a['artifacts'])
        verify(a['input_sha256'])
        if a['input_sha256'].get(str(authority)) != sha(authority):
            raise ValueError('endpoint obligations differ')
        phases = []
        for name in a['input_sha256']:
            if not name.endswith('/assessment.json'):
                continue
            record = json.loads(Path(name).read_text())
            if (record.get('conditional_experiment_only') is True
                    and record.get('physical_launch_clock_latency_retained') is True
                    and record.get('native_model_corner') in ('tt','ff','ss','sf','fs')):
                phases.append((Path(name), record))
        if len(phases) != 1:
            raise ValueError('one hash-bound enabled-phase timing receipt required')
        phase, phase_record = phases[0]
        corner = phase_record['native_model_corner']
        constraints,period=budget_period(phase,phase_record)
        periods.add(period)
        pins[str(constraints)]=sha(constraints)
        paths = directory/'paths.json'; log = directory/'inventory.log'; text = log.read_text()
        inventory = json.loads(paths.read_text())['interstage']
        if {c['id'] for c in inventory} != {c['id'] for c in chains}:
            raise ValueError('chain inventory mismatch')
        for index, chain in enumerate(chains):
            selected = next(c for c in inventory if c['id'] == chain['id'])
            setup = [p for p in selected['paths'] if p['kind'] == 'max']
            source, destination = [stage['routed_cell'].lstrip('\\') for stage in chain['stages'][:2]]
            if len(setup) != 1 or setup[0]['startpoint'] != source or setup[0]['endpoint'] != destination:
                raise ValueError('actual stage identity mismatch')
            section = text.split(f'INTERSTAGE_{index}_BEGIN',1)[1].split(f'INTERSTAGE_{index}_END',1)[0]
            available = budget(section,source,destination,setup[0]['slack_ns'])
            tail = observation['observed_maximum_resolution_ns_by_corner'][corner]
            results.append(dict(corner=corner,chain_id=chain['id'],available_Q_resolution_time_ns=available,
                 observed_native_rail_resolution_ns=tail,clock_train_observation_margin_ns=available-tail))
        pins.update({str(p):sha(p) for p in (receipt, phase, paths, log)})
    if len(results) != 65 or len({(r['corner'],r['chain_id']) for r in results}) != 65:
        raise ValueError('five distinct corners by thirteen chains required')
    if len(periods)!=1:raise ValueError('one actual routed source clock period required')
    helper=Path(__file__).with_name('screen_prototype_decision_hold_phase_v5.py')
    pins[str(helper)]=sha(helper)
    verify(pins); output.mkdir(parents=True,exist_ok=False)
    report = output/'comparison.json'; save(report, results)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},
         compared_interstage_budgets=65,minimum_clock_train_observation_margin_ns=min(r['clock_train_observation_margin_ns'] for r in results),
         all_clock_train_observation_margins_positive=all(r['clock_train_observation_margin_ns']>0 for r in results),
         clock_train_observation_period_ns=2,clock_train_observation_high_ns=1,
         interstage_budget_source_clock_period_ns=periods.pop(),pre_next_edge_observations=True,all_clock_periods_and_duty_cycles_qualified=False,
         statistical_or_continuous_metastability_bound_proved=False,FIT_qualified=False,
         physical_CDC_qualified=False,release_ready=False))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('observed','obligations','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--endpoints',type=Path,action='append',required=True)
    args=parser.parse_args()
    run(args.observed.resolve(),args.obligations.resolve(),[p.resolve() for p in args.endpoints],args.output.resolve())
