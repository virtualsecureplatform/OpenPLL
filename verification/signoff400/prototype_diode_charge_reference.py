"""Independent continuous depletion-charge integral for diode patch controls."""
import math


def charge_capacitance(voltage, zero_bias_capacitance, potential, grading, fit=0.5):
    values = (voltage, zero_bias_capacitance, potential, grading, fit)
    if (not all(math.isfinite(v) for v in values) or zero_bias_capacitance < 0
            or potential <= 0 or not 0 <= grading < 1 or not 0 < fit < 1):
        raise ValueError('finite supported junction parameters required')
    transition = fit * potential
    if voltage < transition:
        factor = 1 - voltage / potential
        q = potential * zero_bias_capacitance * (1 - factor ** (1 - grading)) / (1 - grading)
        return q, zero_bias_capacitance * factor ** (-grading)
    # Integrate the linear forward capacitance from its own transition charge.
    q0 = potential * zero_bias_capacitance * (1 - (1 - fit) ** (1 - grading)) / (1 - grading)
    c0 = zero_bias_capacitance * (1 - fit) ** (-grading)
    slope = zero_bias_capacitance * grading / potential * (1 - fit) ** (-1 - grading)
    delta = voltage - transition
    return q0 + c0 * delta + 0.5 * slope * delta * delta, c0 + slope * delta
