"""Read native original-node capacitance directly as double, not MagAtof float32."""


def transform(text):
    needle = 'node->capacitance += MagAtof(argv[3]);'
    if text.count(needle) != 1:
        raise ValueError('one opt-in original ground capacitance import required')
    return text.replace(needle, 'node->capacitance += atof(argv[3]);')
