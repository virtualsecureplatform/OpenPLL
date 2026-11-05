import unittest
from prepare_prototype_context_domain_reference import partition, header


class DomainPartitionTests(unittest.TestCase):
    def test_shared_controls_remain_boundary_and_output_remains_unknown(self):
        private, cuts = partition({'core': ['control', 'out', 'g'],
                                   'receiver': ['out', 'clock', 'g'],
                                   'digital': ['control', 'clock', 'remote', 'g']},
                                  {'core', 'receiver'}, {'g'})
        self.assertEqual(private, {'out'})
        self.assertEqual(cuts, {'control', 'clock'})
        self.assertNotIn('remote', private | cuts)

    def test_many_ports_are_continued_without_changing_order(self):
        ports = ['n' + str(i) for i in range(45)]
        text = header('Model', ports)
        self.assertEqual(text.splitlines()[0], '.subckt Model')
        self.assertEqual([word for line in text.splitlines()[1:] for word in line.split()[1:]], ports)
        self.assertTrue(all(line.startswith('+ ') for line in text.splitlines()[1:]))


if __name__ == '__main__':
    unittest.main()
