"""Experimental export control: do not also ground explicit coupling capacitors."""


def transform(text):
    original = '''    if (ResOptionsFlags & ResOpt_Signal)
    {
        node1->capacitance += MagAtof(argv[COUPLEVALUE]);
        entry2 = HashFind(&ResNodeTable, argv[COUPLETERMINAL2]);
        node2 = ResExtInitNode(entry2);
        node2->capacitance += MagAtof(argv[COUPLEVALUE]);
        return 0;
    }
'''
    if text.count(original) != 1:
        raise ValueError('one unmodified signal coupling import required')
    return text.replace(original, '''    /* Experimental explicit-coupling export: coupling remains in the
     * ext2spice network, so do not add a duplicate substrate term here.
     * RC simplification/delay qualification requires separate validation.
     */
''')
