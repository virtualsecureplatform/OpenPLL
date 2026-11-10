"""Compare each native EXT wire branch with exported SPICE, without an error floor."""
import shlex
from collections import defaultdict
from fractions import Fraction as F
from audit_keeper_native_R_contraction import parse


def assess(ext_text, spice_text):
    expected = defaultdict(list)
    scale = F(1)
    for line in ext_text.splitlines():
        fields = shlex.split(line)
        if not fields:
            continue
        if fields[0] == 'scale':
            scale = F(int(fields[1]) or 1, 1000)
        elif fields[0] == 'resist':
            key = tuple(sorted(n.lower() for n in fields[1:3]))
            value = F(fields[3]) * scale
            if value < 0:
                raise ValueError('negative native wire resistance')
            expected[key].append(value)
    actual = defaultdict(list)
    for a, b, value in parse(spice_text)['resistors']:
        actual[tuple(sorted((a, b)))].append(value)
    failures = []
    matched = 0
    extra_ideal_aliases = 0
    for key in expected.keys() | actual.keys():
        before, after = sorted(expected[key]), sorted(actual[key])
        if not before and all(v == 0 for v in after):
            extra_ideal_aliases += len(after)
            continue
        if len(before) != len(after):
            failures.append(dict(nodes=key, reason='wire branch multiplicity changed',
                                 native_count=len(before), exported_count=len(after)))
            continue
        for old, new in zip(before, after):
            # Native EF stores milliohms as float32. The exporter then converts
            # to ohms in double and prints 17 digits. This conservative relative
            # bound covers those operations, and forces exact zero to stay zero.
            bound = abs(old) * F(1, 2**23)
            if abs(new - old) > bound:
                failures.append(dict(nodes=key, native_ohms_exact=str(old),
                     exported_ohms_exact=str(new), relative_bound_exact=str(bound)))
            matched += 1
    return dict(per_native_wire_resistance_values_verified=not failures,
                native_wire_branches=sum(map(len, expected.values())),
                matched_branches=matched, extra_ideal_alias_cards=extra_ideal_aliases,
                absolute_error_floor_used=False, failures=failures)
