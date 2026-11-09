"""Strict selected-voltage reader for completed high-precision Xyce standard output.

Callers must establish native completion and pin the capture before reading it.
All columns are checked, including voltages not selected for downstream use.
"""
import math
from check_selected_boundary_waveforms import bind


def read_selected_standard(path, roles, end_time):
    if not math.isfinite(end_time) or end_time <= 0:
        raise ValueError('positive finite observation horizon required')
    if not roles:
        raise ValueError('at least one observed role required')
    rows=[]; previous=-1.; terminal=False
    with path.open() as stream:
        header=next(stream,'').split()
        if len(header)<3 or header[:2]!=['Index','TIME']:
            raise ValueError('standard Index/TIME header required')
        names=header[1:]
        binding=bind(list(dict.fromkeys(roles.values())),names)
        if not binding['all_bound']:
            raise ValueError('all physical voltages must bind uniquely')
        indices=[binding['bindings'][node]['index'] for node in roles.values()]
        for line in stream:
            if not line.strip():continue
            if terminal:raise ValueError('content after native terminal marker')
            if line.strip()=='End of Xyce(TM) Simulation':
                terminal=True;continue
            fields=line.split()
            if len(fields)!=len(header):raise ValueError('native standard row width mismatch')
            try:
                index=int(fields[0]);values=[float(v) for v in fields[1:]]
            except ValueError as error:
                raise ValueError('invalid native standard sample') from error
            if index!=len(rows) or not all(math.isfinite(v) for v in values):
                raise ValueError('invalid native standard index or nonfinite value')
            t=values[0]
            if t<=previous:raise ValueError('native standard timestamps must strictly increase')
            previous=t;rows.append([t]+[values[i] for i in indices])
    if not terminal or not rows or rows[0][0]!=0 or abs(rows[-1][0]-end_time)>1e-18:
        raise ValueError('incomplete native standard waveform')
    return rows
