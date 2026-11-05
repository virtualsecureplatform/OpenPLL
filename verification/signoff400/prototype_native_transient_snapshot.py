"""Strict streaming assessment of one real ASCII ngspice transient plot."""
import math


def nonempty(stream):
    for line in stream:
        if line.strip():
            return line.strip()
    raise ValueError('truncated native transient plot')


def read_snapshot(path, end_s, window_start_s, signals=()):
    if not (math.isfinite(end_s) and math.isfinite(window_start_s) and 0 <= window_start_s < end_s):
        raise ValueError('finite requested transient interval required')
    with open(path) as stream:
        header = {}
        while True:
            line = nonempty(stream)
            if line.lower() == 'variables:':
                break
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                if key in header:
                    raise ValueError('duplicate raw header field')
                header[key] = value.strip()
        if header.get('plotname', '').lower() != 'transient analysis' or header.get('flags') != 'real':
            raise ValueError('one real native transient plot required')
        count, points = int(header['no. variables']), int(header['no. points'])
        if count < 2 or points < 2:
            raise ValueError('complete sampled transient required')
        names, kinds = [], []
        for i in range(count):
            fields = nonempty(stream).split()
            if len(fields) != 3 or int(fields[0]) != i:
                raise ValueError('ordered native vector inventory required')
            names.append(fields[1].lower()); kinds.append(fields[2].lower())
        if names[0] != 'time' or kinds[0] != 'time' or len(set(names)) != count:
            raise ValueError('unique native vectors with time first required')
        if nonempty(stream).lower() != 'values:':
            raise ValueError('ASCII native values required')
        indices = {name: i for i, name in enumerate(names)}
        tracked = {name.lower(): indices[name.lower()] for name in signals}
        voltage_indices = [i for i, kind in enumerate(kinds) if kind == 'voltage']
        low, high = {}, {}
        ranges = {name: [math.inf, -math.inf] for name in tracked}
        previous, window_points, last = None, 0, None
        for point in range(points):
            fields = nonempty(stream).split()
            if len(fields) != 2 or int(fields[0]) != point:
                raise ValueError('ordered complete native sample indices required')
            values = [float(fields[1])]
            for _ in range(count - 1):
                fields = nonempty(stream).split()
                if len(fields) != 1:
                    raise ValueError('one real value per native vector required')
                values.append(float(fields[0]))
            if not all(math.isfinite(v) for v in values):
                raise ValueError('nonfinite native transient sample')
            time = values[0]
            if (previous is None and abs(time) > 1e-18) or (previous is not None and time <= previous):
                raise ValueError('strictly increasing native time from zero required')
            previous = time
            for name, index in tracked.items():
                ranges[name][0] = min(ranges[name][0], values[index])
                ranges[name][1] = max(ranges[name][1], values[index])
            if time >= window_start_s:
                window_points += 1
                for i in voltage_indices:
                    low[i] = min(low.get(i, values[i]), values[i])
                    high[i] = max(high.get(i, values[i]), values[i])
            last = values
        if any(line.strip() for line in stream):
            raise ValueError('unexpected trailing native plot or values')
    if abs(last[0] - end_s) > max(1e-18, end_s * 1e-12) or window_points < 2:
        raise ValueError('native plot does not cover requested end and trailing window')
    spans = {names[i]: high[i] - low[i] for i in voltage_indices}
    return dict(points=points, variables=count, end_s=last[0], last_values=dict(zip(names, last)),
                trailing_window_start_s=window_start_s, trailing_window_points=window_points,
                maximum_trailing_node_voltage_span_v=max(spans.values(), default=0.),
                maximum_span_node=max(spans, key=spans.get) if spans else None,
                tracked_full_interval_ranges=ranges, waveform_convergence_qualified=False,
                warm_restart_qualified=False)
