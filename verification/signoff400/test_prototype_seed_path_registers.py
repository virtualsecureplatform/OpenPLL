import unittest
from measure_prototype_seed_load_paths_v2 import registers

class SeedPathRegisters(unittest.TestCase):
    def test_unused_alias_bits_are_excluded_but_real_state_is_retained(self):
        module=dict(netnames={'payload':dict(bits=[5,99,'0'])},cells={'\\ff':dict(connections={'Q':[5],'D':[6]})})
        self.assertEqual(registers(module,'payload'),['ff'])

    def test_consumed_bit_without_a_state_driver_is_rejected(self):
        module=dict(netnames={'payload':dict(bits=[5])},cells={'logic':dict(connections={'A':[5],'X':[6]})})
        with self.assertRaisesRegex(ValueError,'implemented state FF'):registers(module,'payload')

if __name__=='__main__':unittest.main()
