#!/usr/bin/env python3
"""Compare a fixed saved prefix of two Xyce ASCII RAW files, including live files.

Only fully read, finite, ordered samples count. This does not assess completion
of either simulation or numerical convergence. Saved grids must agree; this
tool does not interpolate between samples.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


class Prefix:
    def __init__(self, path):
        self.path = path
        self.stream = path.open()
        self.digest = hashlib.sha256()
        self.previous_time = None
        self.names = []
        try:
            header = {}
            for line in self.stream:
                if line.strip().lower() == 'variables:':
                    break
                key, separator, value = line.partition(':')
                if separator:
                    header[key.strip().lower()] = value.strip()
            else:
                raise ValueError('missing Variables header')
            if header.get('flags', '').lower() != 'real':
                raise ValueError('real ASCII RAW required')
            count = int(header['no. variables'])
            for line in self.stream:
                if line.strip().lower() == 'values:':
                    break
                fields = line.split()
                if len(fields) != 3 or int(fields[0]) != len(self.names):
                    raise ValueError('invalid variable inventory')
                self.names.append(fields[1].lower())
            else:
                raise ValueError('missing Values header')
            if (count < 2 or len(self.names) != count or self.names[0] != 'time'
                    or len(set(self.names)) != count):
                raise ValueError('unique ordered variables beginning with time required')
        except BaseException:
            self.stream.close()
            raise

    def fields(self):
        for line in self.stream:
            if line.strip():
                self.digest.update(line.encode())
                return line.split()
        raise ValueError('incomplete requested prefix: ' + str(self.path))

    def sample(self, index):
        fields = self.fields()
        if len(fields) != 2 or int(fields[0]) != index:
            raise ValueError('ordered sample indices required')
        values = [float(fields[1])]
        for _ in self.names[1:]:
            fields = self.fields()
            if len(fields) != 1:
                raise ValueError('incomplete sample or invalid scalar value')
            values.append(float(fields[0]))
        if not all(map(math.isfinite, values)):
            raise ValueError('nonfinite waveform value')
        t = values[0]
        if (index == 0 and t != 0) or (self.previous_time is not None and t <= self.previous_time):
            raise ValueError('strictly increasing time beginning at zero required')
        self.previous_time = t
        return values


def compare(reference, candidate, samples, time_tolerance, value_tolerance):
    streams = []
    try:
        streams = [Prefix(reference)]
        streams.append(Prefix(candidate))
        left, right = streams
        if left.names != right.names:
            raise ValueError('ordered variable inventories differ')
        dt = dv = 0.0
        worst = None
        for index in range(samples):
            a, b = left.sample(index), right.sample(index)
            dt = max(dt, abs(a[0] - b[0]))
            for column in range(1, len(a)):
                delta = abs(a[column] - b[column])
                if delta > dv:
                    dv = delta
                    worst = dict(sample=index, variable=left.names[column],
                                 reference_time_s=a[0], candidate_time_s=b[0])
        grid_pass = dt <= time_tolerance
        return dict(comparison_pass=grid_pass and dv <= value_tolerance,
                    complete_saved_samples_compared=samples,
                    observed_vectors=len(left.names) - 1,
                    reference_end_s=left.previous_time, candidate_end_s=right.previous_time,
                    max_saved_time_difference_s=dt,
                    saved_grid_within_tolerance=grid_pass,
                    max_saved_value_difference=dv if grid_pass else None,
                    worst_sample=worst if grid_pass else None,
                    time_tolerance_s=time_tolerance, value_tolerance=value_tolerance,
                    prefix_value_record_sha256={str(s.path): s.digest.hexdigest() for s in streams},
                    full_simulation_completion_assessed=False,
                    numerical_convergence_qualified=False, release_ready=False)
    finally:
        for stream in streams:
            stream.stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--samples', required=True, type=int)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--time-tolerance-s', default=1e-18, type=float)
    parser.add_argument('--value-tolerance', default=1e-6, type=float,
                        help='Absolute tolerance in native units; use matching vector types')
    args = parser.parse_args()
    if (args.samples < 2 or not math.isfinite(args.time_tolerance_s)
            or not math.isfinite(args.value_tolerance)
            or min(args.time_tolerance_s, args.value_tolerance) < 0):
        parser.error('at least two samples and finite nonnegative tolerances required')
    # Reserve a fresh assessment path before reading potentially large inputs.
    with args.output.open('x') as output:
        try:
            report = compare(args.reference.resolve(), args.candidate.resolve(), args.samples,
                             args.time_tolerance_s, args.value_tolerance)
        except Exception as error:
            report = dict(comparison_pass=False, reason=repr(error),
                          full_simulation_completion_assessed=False, release_ready=False)
        json.dump(report, output, indent=2)
        output.write('\n')
    print(json.dumps(report))
    return 0 if report['comparison_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
