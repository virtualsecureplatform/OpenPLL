"""Share literal PDK calls while preserving all explicit capacitor cards."""
from decimal import Decimal, InvalidOperation
from prototype_native_literal_templates import factor as factor_dc, review


def factor(text):
    lines = text.splitlines()
    capacitors, filtered, names = {}, [], set()
    for i, line in enumerate(lines):
        fields = line.split()
        if fields and not fields[0].startswith(('*', '.')):
            name = fields[0].lower()
            if name in names:
                raise ValueError('duplicate source element name')
            names.add(name)
            if name.startswith('c'):
                try:
                    finite = len(fields) == 4 and Decimal(fields[3]).is_finite()
                except InvalidOperation:
                    finite = False
                if not finite:
                    raise ValueError('explicit finite constant two-terminal capacitor required')
                capacitors[i] = line
                continue
        filtered.append(line)
    generated, counts = factor_dc('\n'.join(filtered) + '\n')
    produced = generated.splitlines()
    # The DC producer adds definitions before its otherwise one-for-one root
    # lines. Reinsert C at the original positions in that unchanged root order.
    prefix, root = produced[:-len(filtered)], iter(produced[-len(filtered):])
    woven = [capacitors[i] if i in capacitors else next(root) for i in range(len(lines))]
    if next(root, None) is not None:
        raise ValueError('unexpected generated root lines')
    result = '\n'.join(prefix + woven) + '\n'
    review(text, result)
    return result, dict(**counts, explicit_capacitor_cards_preserved=len(capacitors))
