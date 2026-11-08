"""Compare completed coupling-import RC controls after ideal wire-R contraction."""
from collections import Counter
from fractions import Fraction
from audit_keeper_native_R_contraction import compare, parse


def metrics(base_text, previous_text, candidate_text):
    old = compare(base_text, previous_text)
    new = compare(base_text, candidate_text)
    def resistor_inventory(text):
        return Counter((tuple(sorted((a, b))), value) for a, b, value in parse(text)['resistors'])
    def error(record):
        return sum((abs(Fraction(row['contracted_F_exact']) - Fraction(row['reference_F_exact'])) for row in record['C_pair_differences']), Fraction(0))
    return dict(previous_contraction=old, candidate_contraction=new,
                literal_named_R_network_unchanged=resistor_inventory(previous_text) == resistor_inventory(candidate_text),
                previous_total_absolute_contracted_C_error_F_exact=str(error(old)),
                candidate_total_absolute_contracted_C_error_F_exact=str(error(new)),
                ideal_R_contraction_is_static_only=True, coupling_placement_qualified=False,
                RC_simplification_qualified=False, dynamic_accuracy_qualified=False,
                native_simulation_allowed=False, model_qualified=False, release_ready=False)
