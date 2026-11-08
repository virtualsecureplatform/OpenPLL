import unittest
from preserve_explicit_coupling import transform


class CouplingImport(unittest.TestCase):
    block = '''    if (ResOptionsFlags & ResOpt_Signal)
    {
        node1->capacitance += MagAtof(argv[COUPLEVALUE]);
        entry2 = HashFind(&ResNodeTable, argv[COUPLETERMINAL2]);
        node2 = ResExtInitNode(entry2);
        node2->capacitance += MagAtof(argv[COUPLEVALUE]);
        return 0;
    }
'''

    def test_only_duplicate_grounding_is_removed(self):
        tail = 'node1->cap_couple += MagAtof(argv[COUPLEVALUE]);\n'
        result = transform('prefix\n' + self.block + tail)
        self.assertTrue(result.startswith('prefix\n'))
        self.assertTrue(result.endswith(tail))
        self.assertNotIn('node1->capacitance +=', result)
        self.assertNotIn('node2->capacitance +=', result)

    def test_unexpected_or_repeated_block_rejected(self):
        for text in ['', self.block * 2, transform(self.block)]:
            with self.assertRaises(ValueError):
                transform(text)


if __name__ == '__main__':
    unittest.main()
