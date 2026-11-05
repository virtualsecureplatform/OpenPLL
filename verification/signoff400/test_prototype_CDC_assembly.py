import copy
import unittest
from bind_prototype_CDC_to_assembly import bind

SOURCE = '''.subckt ff D Q
.ends
.subckt buf A X
.ends
.subckt IntegerPLL_ProgrammedCore
Xfirst x a ff
Xbuffer a b buf
Xsecond b y ff
.ends
'''


def fixture():
    chain = dict(id='sync', role='control', cells=[])
    mapping = {}
    for name, master, input_pin, output_pin, pins in (
        ('first', 'ff', None, 'Q', {'Q':'net1'}),
        ('buffer', 'buf', 'A', 'X', {'A':'net1', 'X':'net2'}),
        ('second', 'ff', 'D', None, {'D':'net2'})):
        chain['cells'].append(dict(input_pin=input_pin, output_pin=output_pin,
            physical=dict(instance=name, master=master, pins={p:dict(net=n) for p,n in pins.items()})))
        mapping[name] = dict(master=master, extracted_instance=name)
    return [chain], mapping


class AssemblyCDCControls(unittest.TestCase):
    def test_buffered_chain_is_bound_completely(self):
        chains, mapping = fixture()
        r = bind(chains, mapping, SOURCE)
        self.assertEqual(r['physical_cells'], 3)
        self.assertEqual(r['distinct_interstage_conductors'], 2)

    def test_split_short_and_wrong_master_rejected(self):
        for text in (SOURCE.replace('Xbuffer a b', 'Xbuffer other b'),
                     SOURCE.replace('Xbuffer a b', 'Xbuffer a a').replace('Xsecond b', 'Xsecond a')):
            with self.assertRaises(ValueError):
                bind(*fixture(), text)
        chains, mapping = fixture()
        mapping['buffer']['master'] = 'ff'
        with self.assertRaises(ValueError):
            bind(chains, mapping, SOURCE)


if __name__ == '__main__':
    unittest.main()
