"""Validate the original or separately prepared100MHz withdrawal stimulus."""
import re
from decimal import Decimal


def validate_withdrawal(deck, mode_mhz, start_ns, *records):
    assert start_ns in (187.05, 207.05)
    assert start_ns == 187.05 or mode_mhz == 100
    pulse = re.search(r'^VCOMMAND COMMAND_RUN 0 PWL\(0 \{VDD\} ([0-9.]+)n \{VDD\} ([0-9.]+)n 0 ([0-9.]+)n 0 ([0-9.]+)n \{VDD\}\)$', deck, re.M)
    assert pulse
    start = Decimal(str(start_ns))
    assert tuple(map(Decimal, pulse.groups())) == tuple(start+offset for offset in
           (Decimal(0), Decimal('.02'), Decimal('1.50'), Decimal('1.52')))
    for record in records:
        if start_ns == 207.05:
            assert 'withdrawal_start_ns' in record
        if 'withdrawal_start_ns' in record:
            assert record['withdrawal_start_ns'] == start_ns
