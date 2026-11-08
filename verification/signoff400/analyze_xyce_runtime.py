#!/usr/bin/env python3
"""Extract native Xyce phase timings without treating partial logs as completed runs."""
import argparse
import json
from pathlib import Path
import re

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def analyze(path):
    text = Path(path).read_text()
    result = {
        'log': str(Path(path).resolve()),
        'normal_end_reported': '***** End of Xyce(TM) Simulation' in text,
        'step_limited': bool(re.search(r'Exit step\.', text, re.IGNORECASE)),
        'singular_matrix_warnings': text.count('Numerically singular matrix'),
        'umfpack_linear_failure_warnings': text.count('UMFPACK linear solve failed'),
        'phases': {},
        'umfpack_progress_snapshots': [],
        'umfpack_final_instances': [],
        'timestep_trace': [],
    }
    phase = None
    for line in text.splitlines():
        if 'OpenPLL timestep:' in line:
            fields = {key: float(value) for key, value in re.findall(
                r'(\w+)=(' + NUMBER + ')', line.split('OpenPLL timestep:', 1)[1])}
            if fields:
                result['timestep_trace'].append(fields)
        for marker, destination in [
                ('OpenPLL UMFPACK progress:', 'umfpack_progress_snapshots'),
                ('OpenPLL UMFPACK adapter:', 'umfpack_final_instances')]:
            if marker in line:
                fields = dict((key, int(value)) for key, value in
                              re.findall(r'(\w+)=(\d+)', line.split(marker, 1)[1]))
                if fields:
                    result[destination].append(fields)
        match = re.search(r'(DCOP|Transient Stepping) time:\s*(' + NUMBER + r') seconds', line)
        if match:
            phase = {'wall_s': float(match[2]), 'counters': {}}
            result['phases'][match[1]] = phase
        elif '***** Solution Summary' in line:
            phase = None
        elif phase is not None:
            match = re.match(r'\s*(Number[^:]+):\s*(\d+)\s*$', line)
            if match:
                phase['counters'][match[1].strip()] = int(match[2])
            match = re.match(r'\s*Total (Residual Load|Jacobian Load|Linear Solution) Time:\s*(' + NUMBER + r') seconds', line)
            if match:
                phase[match[1].lower().replace(' ', '_') + '_s'] = float(match[2])
        for label, key in [('Problem read in and set up time', 'setup_s'),
                           ('Total Elapsed Run Time', 'elapsed_s')]:
            match = re.search(re.escape(label) + r':\s*(' + NUMBER + r') seconds', line)
            if match:
                result[key] = float(match[1])
    for phase in result['phases'].values():
        if phase['wall_s'] > 0:
            phase['linear_solution_fraction'] = phase.get('linear_solution_s', 0) / phase['wall_s']
        solves = phase['counters'].get('Number Linear Solves', 0)
        if solves:
            phase['linear_solution_s_per_solve'] = phase.get('linear_solution_s', 0) / solves
    result['full_transient_completion_proven'] = False
    trace = result['timestep_trace']
    result['timestep_trace_summary'] = {
        'sampled_records': len(trace),
        'sampling_is_not_all_steps': True,
        'maximum_below_proposed_records': sum(
            row.get('maximum', float('inf')) < row.get('proposed', 0)
            for row in trace),
        'proposed_equals_current_records': sum(
            row.get('proposed') == row.get('step') for row in trace
            if 'proposed' in row and 'step' in row),
        'latest': trace[-1] if trace else None,
        'limiting_equation_identified': False,
    }
    # Progress counters are cumulative. Keep snapshots distinct from terminal
    # instance counters so callers cannot mistake their sum for completed work.
    result['latest_umfpack_progress'] = (result['umfpack_progress_snapshots'][-1]
                                         if result['umfpack_progress_snapshots'] else None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    text = json.dumps(analyze(args.log), indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
