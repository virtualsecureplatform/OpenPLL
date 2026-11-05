"""Compare defined frozen-RTL reset bits with native DC observations.

Midrail classification is a diagnostic logic check, not characterization of
valid output levels, noise margin, startup timing or transient behavior.
"""
import math


def compare(expected, values, supply_v):
    if not expected or not math.isfinite(supply_v) or supply_v <= 0:
        raise ValueError('defined reset bits and a finite positive supply required')
    if any(not isinstance(name, str) or not name or bit not in (0, 1)
           for name, bit in expected.items()):
        raise ValueError('named binary RTL reset expectations required')
    if len({name.lower() for name in expected}) != len(expected):
        raise ValueError('SPICE-case-independent root names must be unique')
    threshold = supply_v / 2
    observations, missing, mismatches = {}, [], []
    for name, bit in expected.items():
        value = values.get('v(' + name.lower() + ')', values.get(name.lower()))
        if value is None:
            missing.append(name)
            continue
        if not math.isfinite(value):
            raise ValueError('finite native root voltage required')
        logic = int(value > threshold) if value != threshold else None
        observations[name] = dict(expected=bit, observed=logic, voltage_v=value,
                                  distance_from_midrail_v=abs(value - threshold))
        if logic != bit:
            mismatches.append(name)
    return dict(all_defined_reset_bits_match=not missing and not mismatches,
                threshold_v=threshold, observations=observations,
                missing_root_observations=missing, mismatched_or_indeterminate_bits=mismatches,
                minimum_distance_from_midrail_v=min((r['distance_from_midrail_v']
                    for r in observations.values()), default=None),
                analog_noise_margin_qualified=False, transient_functionality_qualified=False)
