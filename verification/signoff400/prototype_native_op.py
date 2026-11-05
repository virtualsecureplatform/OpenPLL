"""Prepare and assess a DC-only assembled-model initialization control."""
import math


def reset_voltages():
    values = dict(VPWR=1.8, VPB=1.8, VGND=0., VNB=0.,
                  REFCLK=0., RESET_N=0., PLL_ENABLE=0., STARTUP_INCREASING=1.8)
    for name, width, value in (('STARTUP_COARSE', 6, 20), ('STARTUP_FINE', 8, 111), ('KI', 8, 1), ('KP', 5, 2)):
        for bit in range(width):
            values[name + '[' + str(bit) + ']'] = 1.8 if value & (1 << bit) else 0.
    return values


def dc_body(text):
    kept, capacitors = [], 0
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0][0].upper() == 'C':
            if len(fields) != 4:
                raise ValueError('only constant two-terminal capacitors may be opened for DC')
            if not math.isfinite(float(fields[3])):
                raise ValueError('finite explicit C required')
            capacitors += 1
        else:
            kept.append(line)
    return '\n'.join(kept) + '\n', capacitors


def read_operating_point(text):
    lines = text.splitlines()
    vi = next(i for i, line in enumerate(lines) if line.strip().lower() == 'variables:')
    di = next(i for i, line in enumerate(lines) if line.strip().lower() == 'values:')
    header = {line.split(':', 1)[0].strip().lower(): line.split(':', 1)[1].strip()
              for line in lines[:vi] if ':' in line}
    count = int(header['no. variables'])
    if header['plotname'].lower() != 'operating point' or header['flags'] != 'real' or int(header['no. points']) != 1:
        raise ValueError('one real native DC operating point required')
    variables = []
    for line in lines[vi + 1:di]:
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 3 or int(fields[0]) != len(variables):
            raise ValueError('ordered native operating-point variables required')
        variables.append(fields[1].lower())
    fields = ' '.join(lines[di + 1:]).split()
    if len(variables) != count or len(set(variables)) != count or len(fields) != count + 1 or fields[0] != '0':
        raise ValueError('complete single-point native values required')
    values = list(map(float, fields[1:]))
    if not all(math.isfinite(value) for value in values):
        raise ValueError('nonfinite native operating point')
    return dict(zip(variables, values))
