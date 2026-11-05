import unittest
from prototype_identity_wrapper import lift


class IdentityWrapper(unittest.TestCase):
    source = ('* native DC model\n.subckt Top A B\n'
              'Xflat0 A n B B sky130_fd_pr__nfet_01v8 w=1 l=0.15\n'
              'RparentWire0 n B 2\n.ends Top\n')

    def test_cards_and_node_labels_survive_exactly(self):
        body, count = lift(self.source, 'Xpll A B Top', ['Vbias0'])
        self.assertEqual(count, 2)
        self.assertEqual(body, self.source.replace('.subckt Top A B\n', '').replace('.ends Top\n', ''))

    def test_rejects_nonidentity_parameters_scoped_directives_and_collisions(self):
        for source, call, names in (
            (self.source, 'Xpll B A Top', []),
            (self.source, 'Xpll A B Top m=2', []),
            (self.source.replace('Top A B', 'Top A B params: m=1'), 'Xpll A B Top', []),
            (self.source.replace('RparentWire0 n B 2', '.param k=1'), 'Xpll A B Top', []),
            (self.source, 'Xpll A B Top', ['xFLAT0']),
            (self.source.replace('sky130_fd_pr__nfet_01v8', 'unreviewed'), 'Xpll A B Top', []),
        ):
            with self.assertRaises(ValueError):
                lift(source, call, names)


if __name__ == '__main__':
    unittest.main()
